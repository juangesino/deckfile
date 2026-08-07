"""Chart selection for ``deck build -s`` and ``deck list``.

Once a project has more charts than fit on a screen, naming them one at a time
stops working.  A selector picks a set:

``monthly_revenue``      one chart by name
``segment_country_*``    every chart matching a glob
``tag:segments``         every chart carrying a tag
``path:charts/segments`` every chart defined under a file or directory
``live+``                every chart downstream of a model, through ref()

Multiple selectors union.  A selector that matches nothing is an error — a
build that silently renders zero charts is worse than one that says why.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, Iterable, List, Set

from .project import Project
from .query import parse_refs


# ═══════════════════════════════════════════════════════════════════════════════
# Source graph
# ═══════════════════════════════════════════════════════════════════════════════

def chart_source_name(spec: dict) -> str | None:
    """The named source a chart reads from, or None if it is inline."""
    source = spec.get("source")
    return source if isinstance(source, str) else None


def build_dependents(sources: Dict[str, dict]) -> Dict[str, Set[str]]:
    """Map each source to the sources that reference it directly."""
    dependents: Dict[str, Set[str]] = {name: set() for name in sources}
    for name, spec in sources.items():
        if not isinstance(spec, dict) or spec.get("type") != "dep":
            continue
        for upstream in parse_refs(spec.get("query") or ""):
            if upstream in dependents:
                dependents[upstream].add(name)
    return dependents


def descendants(model: str, sources: Dict[str, dict]) -> Set[str]:
    """*model* plus every source that depends on it, directly or transitively."""
    dependents = build_dependents(sources)
    seen = {model}
    queue = [model]
    while queue:
        current = queue.pop()
        for child in dependents.get(current, ()):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return seen


# ═══════════════════════════════════════════════════════════════════════════════
# Selectors
# ═══════════════════════════════════════════════════════════════════════════════

def _select_tag(tag: str, project: Project) -> Set[str]:
    matched = set()
    for name, spec in project.charts.items():
        tags = spec.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        if tag in tags:
            matched.add(name)
    return matched


def _path_targets(raw: str, project: Project) -> List[Path]:
    """Candidate filesystem targets for a ``path:`` selector.

    ``path:charts/segments`` should work whether that names a directory or a
    ``segments.yml`` file, since which one it is depends on how the project
    happens to be organized.
    """
    base = (project.root / raw).resolve()
    candidates = [base]
    if base.suffix not in (".yml", ".yaml"):
        candidates.extend(base.with_suffix(suffix) for suffix in (".yml", ".yaml"))
    return candidates


def _select_path(raw: str, project: Project) -> Set[str]:
    targets = [p for p in _path_targets(raw, project) if p.exists()]
    if not targets:
        raise ValueError(
            f"Selector 'path:{raw}' does not match any file or directory "
            f"(looked for {raw}, {raw}.yml, and {raw}.yaml under "
            f"{project.root})."
        )

    matched = set()
    for name, defining_file in project.chart_files.items():
        if name not in project.charts:
            continue
        resolved = defining_file.resolve()
        if any(resolved == t or t in resolved.parents for t in targets):
            matched.add(name)
    return matched


def _select_downstream(model: str, project: Project) -> Set[str]:
    if model not in project.sources:
        available = ", ".join(sorted(project.sources)) or "none defined"
        raise ValueError(
            f"Unknown model '{model}' in selector '{model}+'. Available: {available}"
        )
    affected = descendants(model, project.sources)
    return {
        name
        for name, spec in project.charts.items()
        if chart_source_name(spec) in affected
    }


def _select_name(pattern: str, project: Project) -> Set[str]:
    if any(ch in pattern for ch in "*?["):
        return {name for name in project.charts if fnmatch.fnmatchcase(name, pattern)}
    return {pattern} if pattern in project.charts else set()


def _all_tags(project: Project) -> List[str]:
    tags: Set[str] = set()
    for spec in project.charts.values():
        value = spec.get("tags")
        if isinstance(value, str):
            tags.add(value)
        elif value:
            tags.update(value)
    return sorted(tags)


def _explain_miss(selector: str, project: Project) -> str:
    """Build a message that says why a selector matched nothing.

    Listing every chart in a project with a hundred of them is noise, so this
    suggests near matches and points at ``deck list`` for the rest.
    """
    import difflib

    from .project import abstract_names

    if selector in abstract_names(project):
        return (
            f"Selector '{selector}' matched no charts: it names an abstract "
            f"template, which exists to be extended and is never rendered."
        )

    lines = [f"Selector '{selector}' matched no charts."]

    if selector.startswith("tag:"):
        wanted = selector[4:]
        tags = _all_tags(project)
        close = difflib.get_close_matches(wanted, tags, n=5, cutoff=0.5)
        if close:
            lines.append(f"Did you mean: {', '.join('tag:' + t for t in close)}?")
        lines.append(f"Known tags: {', '.join(tags) if tags else 'none defined'}")
    else:
        close = difflib.get_close_matches(selector, list(project.charts), n=5, cutoff=0.5)
        if close:
            lines.append(f"Did you mean: {', '.join(close)}?")
        lines.append(f"The project defines {len(project.charts)} chart(s); "
                     f"run 'deck list' to see them.")

    return "\n".join(lines)


def select_charts(selectors: Iterable[str], project: Project) -> List[str]:
    """Resolve *selectors* to chart names, preserving definition order.

    Returning names in the order they were defined keeps build output stable
    and readable regardless of how the selectors were written.
    """
    selected: Set[str] = set()

    for selector in selectors:
        if selector.startswith("tag:"):
            matched = _select_tag(selector[4:], project)
        elif selector.startswith("path:"):
            matched = _select_path(selector[5:], project)
        elif selector.endswith("+") and len(selector) > 1:
            matched = _select_downstream(selector[:-1], project)
        else:
            matched = _select_name(selector, project)

        if not matched:
            raise ValueError(_explain_miss(selector, project))

        selected |= matched

    return [name for name in project.charts if name in selected]
