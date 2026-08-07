"""Project loading: many files in, one resolved config out.

A deckfile project can be a single ``deckfile.yaml``, exactly as before, or a
directory tree where ``deckfile.yaml`` holds only project-level settings and
the actual work lives in separate files:

    deckfile.yaml          project settings: paths, vars, defaults, theme
    models/
      core/live.sql        a source; its name is the filename stem
      segments/country.sql
    charts/
      segments/country.yml charts:, presets:, and sources: blocks
      quarterly/growth.yml

Every ``*.yml`` under the chart paths contributes to one shared namespace, and
every ``*.sql`` under the model paths becomes a source.  Names must be unique
across the whole project; a collision is an error that names both files rather
than a silent last-one-wins.

Nothing here is required.  A project with no ``models/`` or ``charts/``
directory and no path settings behaves exactly like a pre-split deckfile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .resolve import interpolate, is_abstract, resolve_charts

# Conventional directories, used when the project file does not say otherwise.
DEFAULT_MODEL_PATHS = ("models",)
DEFAULT_CHART_PATHS = ("charts",)

# Blocks a chart file may contribute to the shared project namespace.
_MERGEABLE_BLOCKS = ("charts", "presets", "sources")

_YAML_SUFFIXES = (".yml", ".yaml")


@dataclass
class Project:
    """A fully loaded, fully resolved deckfile project."""

    path: Path
    """The project file (``deckfile.yaml``)."""

    root: Path
    """Directory containing the project file; all relative paths hang off it."""

    defaults: Dict[str, Any] = field(default_factory=dict)
    sources: Dict[str, dict] = field(default_factory=dict)
    charts: Dict[str, dict] = field(default_factory=dict)
    """Concrete charts, with presets, extends, and vars already applied."""

    raw_charts: Dict[str, dict] = field(default_factory=dict)
    """Charts as written, including abstract templates. Used for diagnostics."""

    presets: Dict[str, dict] = field(default_factory=dict)
    vars: Dict[str, Any] = field(default_factory=dict)

    chart_files: Dict[str, Path] = field(default_factory=dict)
    """Chart name -> the file that defined it, for ``path:`` selectors."""

    source_files: Dict[str, Path] = field(default_factory=dict)

    def as_config(self) -> dict:
        """Flatten back into the single-file config shape.

        This is what ``deck compile`` writes and what the build consumes, so
        the composition layer stays entirely upstream of chart rendering.
        """
        config: dict = {}
        if self.defaults:
            config["defaults"] = self.defaults
        if self.vars:
            config["vars"] = self.vars
        if self.sources:
            config["sources"] = self.sources
        if self.charts:
            config["charts"] = self.charts
        return config

    def relpath(self, path: Path) -> str:
        """Render *path* relative to the project root for user-facing messages."""
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path)


# ═══════════════════════════════════════════════════════════════════════════════
# File collection
# ═══════════════════════════════════════════════════════════════════════════════

def _read_yaml(path: Path) -> dict:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected a mapping at the top level, got {type(data).__name__}."
        )
    return data


def _resolve_search_paths(
    root: Path,
    configured: Optional[List[str]],
    conventional: tuple[str, ...],
) -> List[Path]:
    """Resolve configured search paths, or fall back to conventional dirs.

    Explicitly configured paths must exist — a typo there should fail loudly.
    Conventional paths are used only when they happen to be present, so a
    single-file project never has to create empty directories.
    """
    if configured is not None:
        if isinstance(configured, str):
            configured = [configured]
        resolved = []
        for entry in configured:
            candidate = (root / entry).resolve()
            if not candidate.is_dir():
                raise ValueError(
                    f"Configured path '{entry}' does not exist (looked in {candidate})."
                )
            resolved.append(candidate)
        return resolved

    return [(root / name).resolve() for name in conventional if (root / name).is_dir()]


def _collect_yaml_files(search_paths: List[Path], exclude: Path) -> List[Path]:
    """Every YAML file under *search_paths*, sorted for deterministic errors."""
    found: List[Path] = []
    seen: set[Path] = set()
    for base in search_paths:
        for suffix in _YAML_SUFFIXES:
            for candidate in base.rglob(f"*{suffix}"):
                resolved = candidate.resolve()
                if resolved == exclude or resolved in seen:
                    continue
                if any(part.startswith(".") for part in resolved.parts):
                    continue
                seen.add(resolved)
                found.append(resolved)
    return sorted(found)


def _collect_sql_files(search_paths: List[Path]) -> List[Path]:
    found: List[Path] = []
    seen: set[Path] = set()
    for base in search_paths:
        for candidate in base.rglob("*.sql"):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            if any(part.startswith(".") for part in resolved.parts):
                continue
            seen.add(resolved)
            found.append(resolved)
    return sorted(found)


# ═══════════════════════════════════════════════════════════════════════════════
# Namespace merging
# ═══════════════════════════════════════════════════════════════════════════════

def _merge_block(
    target: Dict[str, dict],
    origins: Dict[str, Path],
    incoming: Any,
    source_file: Path,
    block: str,
    root: Path,
) -> None:
    """Merge one file's block into the shared namespace, rejecting duplicates."""
    if incoming is None:
        return
    if not isinstance(incoming, dict):
        raise ValueError(
            f"{source_file}: '{block}:' must be a mapping of name -> definition, "
            f"got {type(incoming).__name__}."
        )

    for name, spec in incoming.items():
        if name in target:
            first = origins.get(name)
            first_label = _label(first, root) if first else "an earlier definition"
            raise ValueError(
                f"Duplicate {block[:-1]} name '{name}'.\n"
                f"  defined in: {first_label}\n"
                f"  also in:    {_label(source_file, root)}\n"
                f"Names must be unique across the whole project."
            )
        target[name] = spec
        origins[name] = source_file


def _label(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL models
# ═══════════════════════════════════════════════════════════════════════════════

def _model_from_sql(
    path: Path,
    sql: str,
    yaml_spec: Optional[dict],
    default_type: str,
    root: Path,
) -> dict:
    """Build a source spec from a ``.sql`` file plus optional YAML config.

    The type is inferred from the SQL itself: a query with ``ref()`` calls is
    a ``dep`` model composed from other sources, and anything else is a
    warehouse query of whatever the project's default model type is.  An
    explicit ``type`` in a matching ``sources:`` entry always wins.
    """
    from .query import parse_refs

    spec: dict = dict(yaml_spec or {})

    if spec.get("query"):
        raise ValueError(
            f"Model '{path.stem}' has a query in two places.\n"
            f"  SQL file:     {_label(path, root)}\n"
            f"  sources entry with the same name also defines 'query'.\n"
            f"Keep the SQL in the .sql file and use the sources entry only for "
            f"configuration such as warehouse or role."
        )

    spec["query"] = sql
    spec.setdefault("type", "dep" if parse_refs(sql) else default_type)
    return spec


# ═══════════════════════════════════════════════════════════════════════════════
# Loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_project(
    yaml_path: str | Path,
    *,
    cli_vars: Optional[Dict[str, Any]] = None,
) -> Project:
    """Load a project file and everything it discovers into one resolved config."""
    project_path = Path(yaml_path).expanduser().resolve()
    root = project_path.parent

    config = _read_yaml(project_path)

    default_model_type = config.get("default_model_type", "snowflake")

    model_paths = _resolve_search_paths(
        root, config.get("model_paths"), DEFAULT_MODEL_PATHS
    )
    chart_paths = _resolve_search_paths(
        root, config.get("chart_paths"), DEFAULT_CHART_PATHS
    )

    # The project file contributes to the namespace first, so its definitions
    # are the ones named as "already defined" in a duplicate error.
    charts: Dict[str, dict] = {}
    presets: Dict[str, dict] = {}
    sources: Dict[str, dict] = {}
    chart_files: Dict[str, Path] = {}
    preset_files: Dict[str, Path] = {}
    source_files: Dict[str, Path] = {}

    origins = {"charts": chart_files, "presets": preset_files, "sources": source_files}
    targets = {"charts": charts, "presets": presets, "sources": sources}

    for block in _MERGEABLE_BLOCKS:
        _merge_block(
            targets[block], origins[block], config.get(block), project_path, block, root
        )

    for chart_file in _collect_yaml_files(chart_paths, exclude=project_path):
        data = _read_yaml(chart_file)
        unknown = set(data) - set(_MERGEABLE_BLOCKS)
        if unknown:
            raise ValueError(
                f"{_label(chart_file, root)}: unexpected top-level key(s) "
                f"{sorted(unknown)}. Chart files may define "
                f"{', '.join(_MERGEABLE_BLOCKS)}. Project-level settings such as "
                f"defaults and vars belong in {project_path.name}."
            )
        for block in _MERGEABLE_BLOCKS:
            _merge_block(
                targets[block], origins[block], data.get(block), chart_file, block, root
            )

    for sql_file in _collect_sql_files(model_paths):
        name = sql_file.stem
        sql = sql_file.read_text()
        existing_origin = source_files.get(name)
        if existing_origin is not None and existing_origin.suffix == ".sql":
            raise ValueError(
                f"Duplicate model name '{name}'.\n"
                f"  defined in: {_label(existing_origin, root)}\n"
                f"  also in:    {_label(sql_file, root)}\n"
                f"Model names come from the filename, so two files may not share "
                f"a stem even in different directories."
            )
        sources[name] = _model_from_sql(
            sql_file, sql, sources.get(name), default_model_type, root
        )
        source_files[name] = sql_file

    # Vars: project file first, CLI overrides last.
    variables: Dict[str, Any] = dict(config.get("vars") or {})
    if cli_vars:
        variables.update(cli_vars)

    # Always interpolate, even with no vars defined: a reference to a var that
    # does not exist is a mistake worth reporting, not something to pass
    # through as a literal.
    charts = {
        name: interpolate(spec, variables, f"chart '{name}'")
        for name, spec in charts.items()
    }
    presets = {
        name: interpolate(spec, variables, f"preset '{name}'")
        for name, spec in presets.items()
    }
    sources = {
        name: interpolate(spec, variables, f"source '{name}'")
        for name, spec in sources.items()
    }

    raw_charts = dict(charts)
    resolved_charts = resolve_charts(charts, presets)

    # Sources carry the project root so relative file paths resolve against
    # the deckfile rather than whatever directory `deck` was invoked from.
    for spec in sources.values():
        if isinstance(spec, dict):
            spec.setdefault("_root", str(root))

    return Project(
        path=project_path,
        root=root,
        defaults=config.get("defaults") or {},
        sources=sources,
        charts=resolved_charts,
        raw_charts=raw_charts,
        presets=presets,
        vars=variables,
        chart_files={
            name: path for name, path in chart_files.items() if name in raw_charts
        },
        source_files=source_files,
    )


def abstract_names(project: Project) -> List[str]:
    """Names of charts that exist only as templates."""
    return [name for name, spec in project.raw_charts.items() if is_abstract(spec)]
