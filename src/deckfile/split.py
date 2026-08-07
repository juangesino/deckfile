"""Migrate a single-file deckfile into a multi-file project.

``deck split`` performs the mechanical part of adopting the project layout:
SQL comes out of YAML strings into real ``.sql`` files, and charts are grouped
into files by their name prefix.  What it deliberately does *not* do is invent
presets or ``extends`` relationships — deciding which charts are variations of
which is a judgement call, and a wrong guess is harder to unpick than the
duplication it replaced.  Run this first, then factor by hand with the
duplication now visible file by file.

Caveat worth knowing before running: YAML structural comments are not
preserved, because the file is re-emitted from parsed data.  Comments inside
SQL queries survive, since those move across as verbatim text.  The original
file is kept as ``<name>.bak`` regardless.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# A first-token group larger than this is split one level deeper, so a family
# of sixty charts does not simply become one four-thousand-line file.
_SUBGROUP_THRESHOLD = 12

# Groups smaller than this share a single file rather than each getting one.
_MIN_GROUP_SIZE = 2

_MISC_GROUP = "misc"

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe(name: str) -> str:
    """Make a name safe to use as a path component."""
    return _SAFE_NAME_RE.sub("_", name) or "unnamed"


# ═══════════════════════════════════════════════════════════════════════════════
# Grouping
# ═══════════════════════════════════════════════════════════════════════════════

def group_charts(charts: Dict[str, dict]) -> Dict[str, List[str]]:
    """Assign each chart to a file path, keyed by relative path without suffix.

    Charts are grouped by the first token of their name; a group that grows
    past the threshold is subdivided by the second token.  Names are the only
    signal available here, but in practice they already encode the grouping
    their author had in mind.
    """
    by_prefix: Dict[str, List[str]] = {}
    for name in charts:
        prefix = name.split("_")[0] if "_" in name else name
        by_prefix.setdefault(prefix, []).append(name)

    groups: Dict[str, List[str]] = {}

    for prefix, names in by_prefix.items():
        if len(names) < _MIN_GROUP_SIZE:
            groups.setdefault(_MISC_GROUP, []).extend(names)
            continue

        if len(names) <= _SUBGROUP_THRESHOLD:
            groups[_safe(prefix)] = names
            continue

        # Subdivide by the second token.
        by_second: Dict[str, List[str]] = {}
        for name in names:
            parts = name.split("_")
            second = parts[1] if len(parts) > 1 else "general"
            by_second.setdefault(second, []).append(name)

        for second, sub_names in by_second.items():
            if len(sub_names) < _MIN_GROUP_SIZE:
                groups.setdefault(f"{_safe(prefix)}/{_MISC_GROUP}", []).extend(sub_names)
            else:
                groups[f"{_safe(prefix)}/{_safe(second)}"] = sub_names

    return groups


# ═══════════════════════════════════════════════════════════════════════════════
# Source classification
# ═══════════════════════════════════════════════════════════════════════════════

def _inferred_type(sql: str, default_model_type: str) -> str:
    from .query import parse_refs

    return "dep" if parse_refs(sql) else default_model_type


def _comment_block(text: str) -> str:
    """Render a description as a leading SQL comment."""
    lines = str(text).rstrip().splitlines() or [""]
    return "\n".join(f"-- {line}".rstrip() for line in lines) + "\n\n"


def _split_source(name: str, spec: dict, default_model_type: str):
    """Return (sql_or_None, leftover_yaml_config_or_None) for one source.

    A source whose query moves to a ``.sql`` file keeps a YAML entry only when
    it carries configuration the file cannot express — a warehouse override,
    say, or a type that inference would get wrong.  A ``description`` is
    documentation rather than configuration, so it moves into the SQL file as
    a header comment where whoever edits the query will actually see it.
    """
    if not isinstance(spec, dict):
        return None, spec

    query = spec.get("query")
    src_type = spec.get("type")

    # Only warehouse-style and dep sources become .sql files; file/url/gsheet
    # sources are locations, not queries, and stay in YAML.
    if not query or src_type in ("file", "url", "gsheet"):
        return None, spec

    leftover = {
        k: v for k, v in spec.items() if k not in ("query", "type", "description")
    }

    if src_type != _inferred_type(query, default_model_type):
        leftover["type"] = src_type

    description = spec.get("description")
    sql = _comment_block(description) + query if description else query

    return sql, (leftover or None)


# ═══════════════════════════════════════════════════════════════════════════════
# Writing
# ═══════════════════════════════════════════════════════════════════════════════

def _dump(data: dict) -> str:
    return yaml.safe_dump(
        data, sort_keys=False, width=100, allow_unicode=True, default_flow_style=False
    )


def _existing_conflicts(target: Path) -> List[Path]:
    conflicts = []
    for sub in ("models", "charts"):
        directory = target / sub
        if directory.is_dir() and any(directory.rglob("*")):
            conflicts.append(directory)
    return conflicts


def split_project(
    yaml_path: str | Path,
    target: Optional[Path] = None,
    *,
    force: bool = False,
) -> None:
    """Split the deckfile at *yaml_path* into a multi-file project."""
    source_path = Path(yaml_path).expanduser().resolve()
    target = (target or source_path.parent).expanduser().resolve()

    with open(source_path) as f:
        config = yaml.safe_load(f) or {}

    if not isinstance(config, dict):
        raise ValueError(f"{source_path}: expected a mapping at the top level.")

    charts = config.get("charts") or {}
    sources = config.get("sources") or {}

    if not charts and not sources:
        raise ValueError(f"{source_path} defines no charts or sources; nothing to split.")

    conflicts = _existing_conflicts(target)
    if conflicts and not force:
        listed = ", ".join(str(c.relative_to(target)) for c in conflicts)
        raise ValueError(
            f"Refusing to overwrite existing content in: {listed}\n"
            f"This directory already looks like a split project. Re-run with "
            f"--force to overwrite, or pass -o to write somewhere new."
        )

    default_model_type = config.get("default_model_type", "snowflake")

    # ── Models ────────────────────────────────────────────────────────────────
    models_dir = target / "models"
    remaining_sources: Dict[str, dict] = {}
    written_models = 0

    for name, spec in sources.items():
        sql, leftover = _split_source(name, spec, default_model_type)
        if sql is not None:
            model_path = models_dir / f"{_safe(name)}.sql"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            text = sql if sql.endswith("\n") else sql + "\n"
            model_path.write_text(text)
            written_models += 1
        if leftover is not None:
            remaining_sources[name] = leftover

    # ── Charts ────────────────────────────────────────────────────────────────
    charts_dir = target / "charts"
    groups = group_charts(charts)

    for group, names in sorted(groups.items()):
        chart_file = charts_dir / f"{group}.yml"
        chart_file.parent.mkdir(parents=True, exist_ok=True)
        block = {"charts": {name: charts[name] for name in names}}
        chart_file.write_text(_dump(block))

    # ── Project file ──────────────────────────────────────────────────────────
    project: Dict[str, object] = {}
    for key in ("name", "default_model_type", "model_paths", "chart_paths", "vars"):
        if key in config:
            project[key] = config[key]
    if "defaults" in config:
        project["defaults"] = config["defaults"]
    if remaining_sources:
        project["sources"] = remaining_sources
    for key, value in config.items():
        if key not in project and key not in ("charts", "sources"):
            project[key] = value

    backup = source_path.with_suffix(source_path.suffix + ".bak")
    backup.write_text(source_path.read_text())

    project_path = target / source_path.name
    project_path.write_text(_dump(project))

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"Split {source_path.name} into {target}")
    print()
    print(f"  {project_path.name:<24} project settings"
          + (f" + {len(remaining_sources)} source(s)" if remaining_sources else ""))
    if written_models:
        print(f"  models/{'':<17} {written_models} SQL model(s)")
    print(f"  charts/{'':<17} {len(charts)} chart(s) in {len(groups)} file(s)")
    for group, names in sorted(groups.items()):
        print(f"    charts/{group}.yml".ljust(40) + f"{len(names)} chart(s)")
    print()
    print(f"  Original backed up to {backup.name}")
    print()
    print("  YAML comments were not carried over (SQL comments were).")
    print("  Verify with:  deck compile   then   deck build")
