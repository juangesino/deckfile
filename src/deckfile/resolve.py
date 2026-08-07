"""Composition primitives: deep merge, presets, extends, and vars.

A deckfile chart is rarely written from scratch — most of it repeats a shape
that other charts already have.  Three mechanisms let that shape be stated
once:

``presets``
    Named blocks of chart config that any chart can pull in by name.

``extends``
    Chart-to-chart inheritance.  A chart marked ``abstract: true`` exists
    only to be extended and is never rendered.

``vars``
    Project-level values interpolated into strings with ``{{ var('name') }}``,
    so a date range that appears in thirty subtitles is edited in one place.

Resolution order for a chart, later winning over earlier:

1. the fully-resolved chart it ``extends``
2. its ``preset`` blocks, in the order listed
3. its own keys

so a chart always has the last word over anything it inherited.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

# Keys that drive composition rather than describe a chart.  They are consumed
# during resolution and do not appear in the resolved output.
_CONTROL_KEYS = frozenset({"extends", "preset", "abstract"})

# List-valued keys that accumulate across a merge instead of replacing.  Tags
# are a set of labels, so a preset contributing one and the chart adding
# another should yield both.
_UNION_KEYS = frozenset({"tags"})


# ═══════════════════════════════════════════════════════════════════════════════
# Deep merge
# ═══════════════════════════════════════════════════════════════════════════════

def deep_merge(base: dict, override: dict) -> dict:
    """Merge *override* onto *base*, returning a new dict.

    Nested dicts merge recursively, so a chart can override ``y_format.step``
    without restating ``y_format.style``.  Lists replace wholesale — a partial
    merge of positional data (palettes, separator positions) would be more
    surprising than useful — except for the union keys, which accumulate.

    An explicit ``null`` in *override* deletes the inherited key, which is how
    a chart drops something like a ``y_lim`` it inherited from its parent.
    """
    result = dict(base)

    for key, value in override.items():
        if value is None:
            result.pop(key, None)
            continue

        existing = result.get(key)

        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing, value)
        elif key in _UNION_KEYS and isinstance(existing, list) and isinstance(value, list):
            merged = list(existing)
            merged.extend(v for v in value if v not in merged)
            result[key] = merged
        else:
            result[key] = value

    return result


def _as_list(value: Any, *, field: str = "value", where: str = "") -> List[str]:
    """Normalize a scalar-or-list field (``preset: a`` / ``preset: [a, b]``)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    context = f"{where}: " if where else ""
    raise ValueError(
        f"{context}'{field}' must be a name or a list of names, "
        f"got {type(value).__name__}."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Presets
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_preset(
    name: str,
    presets: Dict[str, dict],
    *,
    _stack: tuple[str, ...] = (),
) -> dict:
    """Return a preset with its own ``extends`` chain already folded in.

    Presets may extend other presets, so a project can layer a
    ``quarterly_timeseries`` on top of a generic ``timeseries``.
    """
    if name in _stack:
        cycle = " -> ".join([*_stack, name])
        raise ValueError(f"Circular preset inheritance: {cycle}")

    if name not in presets:
        available = ", ".join(sorted(presets)) or "none defined"
        raise ValueError(f"Unknown preset: '{name}'. Available presets: {available}")

    spec = presets[name]
    if not isinstance(spec, dict):
        raise ValueError(f"Preset '{name}' must be a mapping, got {type(spec).__name__}")

    where = f"Preset '{name}'"
    resolved: dict = {}
    for parent in _as_list(spec.get("extends"), field="extends", where=where):
        resolved = deep_merge(resolved, resolve_preset(parent, presets, _stack=(*_stack, name)))
    for parent in _as_list(spec.get("preset"), field="preset", where=where):
        resolved = deep_merge(resolved, resolve_preset(parent, presets, _stack=(*_stack, name)))

    own = {k: v for k, v in spec.items() if k not in _CONTROL_KEYS}
    return deep_merge(resolved, own)


# ═══════════════════════════════════════════════════════════════════════════════
# Charts
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_chart(
    name: str,
    charts: Dict[str, dict],
    presets: Dict[str, dict],
    *,
    _stack: tuple[str, ...] = (),
    _cache: Dict[str, dict] | None = None,
) -> dict:
    """Return a chart with its ``extends`` chain and presets folded in."""
    if _cache is not None and name in _cache:
        return _cache[name]

    if name in _stack:
        cycle = " -> ".join([*_stack, name])
        raise ValueError(f"Circular chart inheritance: {cycle}")

    if name not in charts:
        available = ", ".join(sorted(charts)) or "none defined"
        raise ValueError(
            f"Unknown chart: '{name}' referenced by extends. Available charts: {available}"
        )

    spec = charts[name]
    if not isinstance(spec, dict):
        raise ValueError(f"Chart '{name}' must be a mapping, got {type(spec).__name__}")

    where = f"Chart '{name}'"
    resolved: dict = {}

    for parent in _as_list(spec.get("extends"), field="extends", where=where):
        resolved = deep_merge(
            resolved,
            resolve_chart(parent, charts, presets, _stack=(*_stack, name), _cache=_cache),
        )

    for preset_name in _as_list(spec.get("preset"), field="preset", where=where):
        try:
            resolved = deep_merge(resolved, resolve_preset(preset_name, presets))
        except ValueError as e:
            raise ValueError(f"Chart '{name}': {e}") from e

    own = {k: v for k, v in spec.items() if k not in _CONTROL_KEYS}
    resolved = deep_merge(resolved, own)

    if _cache is not None:
        _cache[name] = resolved
    return resolved


def is_abstract(spec: dict) -> bool:
    """Whether a raw chart spec is a template that should never render."""
    return bool(spec.get("abstract"))


def resolve_charts(charts: Dict[str, dict], presets: Dict[str, dict]) -> Dict[str, dict]:
    """Resolve every concrete chart, dropping abstract templates.

    Abstract charts are still resolvable as parents — they are only excluded
    from the returned set, since they describe a shape rather than an output.
    """
    cache: Dict[str, dict] = {}
    return {
        name: resolve_chart(name, charts, presets, _cache=cache)
        for name, spec in charts.items()
        if not is_abstract(spec)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Vars
# ═══════════════════════════════════════════════════════════════════════════════

# {{ var('name') }} or {{ var("name", <default>) }}.  Single braces are left
# alone so Python format strings like '{value:,.0f}' pass through untouched.
_VAR_RE = re.compile(
    r"""\{\{\s*var\(\s*['"](?P<name>\w+)['"]\s*(?:,\s*(?P<default>.+?)\s*)?\)\s*\}\}""",
    re.VERBOSE,
)


def _parse_default(raw: str) -> Any:
    """Interpret a literal default written inside a ``var()`` call."""
    import yaml

    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def _lookup(name: str, default_raw: str | None, variables: Dict[str, Any], where: str) -> Any:
    if name in variables:
        return variables[name]
    if default_raw is not None:
        return _parse_default(default_raw)
    available = ", ".join(sorted(variables)) or "none defined"
    raise ValueError(
        f"Undefined var '{name}' used in {where}. "
        f"Define it under 'vars:' in deckfile.yaml, pass --var {name}=<value>, "
        f"or give it a default: {{{{ var('{name}', 'fallback') }}}}. "
        f"Available vars: {available}"
    )


def interpolate_string(text: str, variables: Dict[str, Any], where: str = "config") -> Any:
    """Substitute ``var()`` references in *text*.

    A string that is exactly one reference yields the variable's native type,
    so ``top: "{{ var('cap') }}"`` with ``cap: 1000`` produces the number
    1000 rather than the string "1000".  Anything else is substituted
    textually.
    """
    whole = _VAR_RE.fullmatch(text.strip())
    if whole:
        return _lookup(whole.group("name"), whole.group("default"), variables, where)

    def sub(match: re.Match) -> str:
        value = _lookup(match.group("name"), match.group("default"), variables, where)
        return str(value)

    return _VAR_RE.sub(sub, text)


def interpolate(node: Any, variables: Dict[str, Any], where: str = "config") -> Any:
    """Recursively interpolate ``var()`` references through a config tree."""
    if isinstance(node, str):
        return interpolate_string(node, variables, where)
    if isinstance(node, dict):
        return {k: interpolate(v, variables, where) for k, v in node.items()}
    if isinstance(node, list):
        return [interpolate(v, variables, where) for v in node]
    return node


def parse_cli_vars(pairs: Iterable[str]) -> Dict[str, Any]:
    """Parse ``--var name=value`` arguments into a dict.

    Values are read as YAML so numbers and booleans arrive typed, which keeps
    ``--var cap=1000`` usable in a numeric position.
    """
    import yaml

    variables: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --var '{pair}'. Expected the form name=value.")
        name, raw = pair.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid --var '{pair}'. Missing variable name.")
        try:
            variables[name] = yaml.safe_load(raw)
        except yaml.YAMLError:
            variables[name] = raw
    return variables
