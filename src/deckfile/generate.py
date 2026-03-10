"""YAML-driven chart generator for deckfile.

Usage:
    deck build
    deck build deckfile.yaml
    deck build --select monthly_conversations
"""

from __future__ import annotations

import csv
import io
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .branding import Branding
from .chart import Chart
from .theme import Theme


# ── Linestyle mapping (human-readable → matplotlib) ─────────────────────────
_LINESTYLE_MAP = {
    "solid": "-",
    "dashed": (0, (8, 4)),
    "dotted": ":",
    "dashdot": "-.",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_source(source_spec, named_sources: dict) -> dict:
    """If source_spec is a string name, look it up; otherwise return as-is."""
    if isinstance(source_spec, str):
        if source_spec not in named_sources:
            raise ValueError(f"Unknown source: '{source_spec}'. Available: {list(named_sources.keys())}")
        return named_sources[source_spec]
    return source_spec


def _fetch_raw(source: dict) -> str:
    """Fetch raw CSV text from a URL, local file, or Google Sheet."""
    import urllib.error
    import urllib.request

    src_type = source["type"]

    timeout = source.get("timeout", 30)

    if src_type == "url":
        path = source["path"]
        try:
            with urllib.request.urlopen(path, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise ValueError(f"HTTP {e.code} fetching URL: {path}") from e
        except urllib.error.URLError as e:
            raise ValueError(f"Cannot reach URL: {path} ({e.reason})") from e
    elif src_type == "file":
        path = source["path"]
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Source file not found: {path}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading source file: {path}")
    elif src_type == "gsheet":
        url = source.get("url", "")
        try:
            from .gsheets import fetch_gsheet_csv

            return fetch_gsheet_csv(url, range=source.get("range"), timeout=timeout)
        except Exception as e:
            raise ValueError(f"Failed to fetch Google Sheet ({url}): {e}") from e
    else:
        raise ValueError(f"Unknown source type: '{src_type}'. Use 'url', 'file', or 'gsheet'.")


def load_data(source: dict, *, source_cache: Dict[str, List[dict]] | None = None,
              source_name: str | None = None) -> List[dict]:
    """Load CSV from URL or file path, return list of row dicts.

    If *source_cache* contains pre-resolved rows for *source_name*
    (e.g. from a ``type: dep`` resolution pass), those are returned
    directly.

    If the source contains a ``query`` key, the raw CSV is loaded into
    DuckDB as a table called ``source`` and the SQL query is executed
    against it.  The query results are returned instead of the raw rows.
    """
    if source_cache and source_name and source_name in source_cache:
        return source_cache[source_name]

    raw = _fetch_raw(source)

    query = source.get("query")
    if query:
        from .query import run_query

        return run_query(raw, query)

    reader = csv.DictReader(io.StringIO(raw))
    return list(reader)


def _rows_to_csv(rows: List[dict]) -> str:
    """Convert list of row dicts back to CSV text."""
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _topo_sort_sources(named_sources: dict) -> list[str]:
    """Return dep source names in topological execution order.

    Validates ref() targets exist, detects cycles, ensures query is present.
    """
    from .query import parse_refs

    deps_of: dict[str, list[str]] = {}
    for name, spec in named_sources.items():
        if spec.get("type") != "dep":
            continue
        query = spec.get("query")
        if not query:
            raise ValueError(f"Source '{name}' is type 'dep' but missing required 'query' key.")
        refs = parse_refs(query)
        for ref_name in refs:
            if ref_name not in named_sources:
                raise ValueError(
                    f"Source '{name}' references unknown source '{ref_name}'. "
                    f"Available: {list(named_sources.keys())}"
                )
            if ref_name == name:
                raise ValueError(f"Source '{name}' references itself.")
        deps_of[name] = refs

    if not deps_of:
        return []

    # Kahn's algorithm — only dep-to-dep edges affect ordering
    dep_names = set(deps_of.keys())
    in_degree = {n: 0 for n in dep_names}
    reverse_adj: dict[str, list[str]] = {n: [] for n in dep_names}

    for name, refs in deps_of.items():
        for ref_name in refs:
            if ref_name in dep_names:
                in_degree[name] += 1
                reverse_adj[ref_name].append(name)

    queue = [n for n in dep_names if in_degree[n] == 0]
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for dependent in reverse_adj[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(dep_names):
        remaining = dep_names - set(order)
        raise ValueError(f"Circular dependency among sources: {remaining}")

    return order


def _resolve_dep_sources(named_sources: dict) -> Dict[str, List[dict]]:
    """Pre-resolve all dep sources in dependency order.

    Returns a cache mapping source_name -> rows for every dep source.
    Non-dep sources referenced by dep sources are loaded and cached
    internally to avoid redundant fetches.
    """
    from .query import parse_refs, run_dep_query

    order = _topo_sort_sources(named_sources)
    if not order:
        return {}

    cache: Dict[str, List[dict]] = {}
    raw_cache: Dict[str, str] = {}

    def _get_csv(name: str) -> str:
        """Get CSV text for any source (dep or non-dep)."""
        if name in cache:
            return _rows_to_csv(cache[name])
        if name not in raw_cache:
            spec = named_sources[name]
            raw = _fetch_raw(spec)
            if spec.get("query"):
                from .query import run_query
                raw_cache[name] = _rows_to_csv(run_query(raw, spec["query"]))
            else:
                raw_cache[name] = raw
        return raw_cache[name]

    for dep_name in order:
        spec = named_sources[dep_name]
        refs = parse_refs(spec["query"])
        upstream = {ref_name: _get_csv(ref_name) for ref_name in refs}
        cache[dep_name] = run_dep_query(spec["query"], upstream)

    return cache


# ═══════════════════════════════════════════════════════════════════════════════
# Data transformation
# ═══════════════════════════════════════════════════════════════════════════════

def transform_data(rows: List[dict], transform: dict, columns: dict) -> List[dict]:
    """Apply transforms: date filtering, sorting."""
    if not transform:
        return rows

    x_date_col = columns.get("x_date")

    # Date range filter
    date_range = transform.get("date_range")
    if date_range and x_date_col:
        start = str(date_range.get("start", "0000-01-01"))
        end = str(date_range.get("end", "9999-12-31"))
        rows = [r for r in rows if start <= r[x_date_col][:10] <= end]

    # Sort — only auto-sort when the column looks like ISO dates (YYYY-MM-DD),
    # otherwise preserve the original data order.
    sort_flag = transform.get("sort")
    if sort_flag is None and x_date_col and rows:
        sample = str(rows[0][x_date_col])[:10]
        sort_flag = len(sample) == 10 and sample[4] == "-" and sample[7] == "-"
    if sort_flag and x_date_col:
        rows.sort(key=lambda r: r[x_date_col])

    return rows


def extract_y(rows: List[dict], col_name: str, divide_by: float = 1) -> list:
    """Extract numeric y-values from rows, optionally dividing."""
    values = []
    for i, row in enumerate(rows):
        try:
            raw = row[col_name]
        except KeyError:
            available = sorted(row.keys()) if row else []
            raise KeyError(
                f"Column '{col_name}' not found in row {i}. "
                f"Available columns: {available}"
            )
        try:
            values.append(float(raw) / divide_by)
        except (ValueError, TypeError):
            raise ValueError(
                f"Cannot convert '{raw}' to number in column '{col_name}' (row {i})"
            )
    return values


# ═══════════════════════════════════════════════════════════════════════════════
# X-axis labels
# ═══════════════════════════════════════════════════════════════════════════════

def build_x_labels(rows: List[dict], columns: dict, labels_spec: dict) -> list:
    """Generate x-axis labels based on mode."""
    if not labels_spec:
        return []

    mode = labels_spec.get("mode", "auto_date")

    if mode == "auto_date":
        x_date_col = columns.get("x_date")
        if not x_date_col:
            return []
        labels = []
        for row in rows:
            date_str = row[x_date_col][:10]  # "YYYY-MM-DD"
            year, month = int(date_str[:4]), int(date_str[5:7])
            if month == 1:
                labels.append(f"Jan\n'{str(year)[-2:]}")
            elif month == 7:
                labels.append("Jul")
            else:
                labels.append("")
        return labels

    elif mode == "column":
        col = labels_spec["column"]
        if rows and col not in rows[0]:
            available = sorted(rows[0].keys())
            raise KeyError(
                f"x_labels column '{col}' not found in data. "
                f"Available columns: {available}"
            )
        return [row[col] for row in rows]

    elif mode == "year_month":
        x_date_col = columns.get("x_date")
        if not x_date_col:
            return []
        labels = []
        for row in rows:
            date_str = row[x_date_col][:10]  # "YYYY-MM-DD"
            year, month = int(date_str[:4]), int(date_str[5:7])
            labels.append(f"{year}-{month}")
        return labels

    elif mode == "explicit":
        return labels_spec["values"]

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Type-specific chart builders
# ═══════════════════════════════════════════════════════════════════════════════

def _build_bar(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    y_vals = extract_y(rows, columns["y"], divide_by)
    chart.bar(x=list(range(len(y_vals))), y=y_vals, **params)


def _build_line(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    y_vals = extract_y(rows, columns["y"], divide_by)
    chart.line(x=list(range(len(y_vals))), y=y_vals, **params)


def _build_stacked_bar(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    layer_cols = columns["layers"]  # {"Customers": "customer_col", ...}
    layers = {}
    for label, col_name in layer_cols.items():
        layers[label] = extract_y(rows, col_name, divide_by)
    chart.stacked_bar(x=list(range(len(rows))), layers=layers, **params)


def _build_stacked_area(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    layer_cols = columns["layers"]  # {"Customer": "customer_col", ...}
    layers = {}
    for label, col_name in layer_cols.items():
        layers[label] = extract_y(rows, col_name, divide_by)
    chart.stacked_area(x=list(range(len(rows))), layers=layers, **params)


def _build_projection(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    x_date_col = columns.get("x_date")
    y_col = columns["y"]
    scenario_cols = columns["scenarios"]
    projection_start = str(columns["projection_start"])

    # Split historical vs projected
    hist_rows = [r for r in rows if r[x_date_col][:10] < projection_start]
    proj_rows = [r for r in rows if r[x_date_col][:10] >= projection_start]

    y_historical = extract_y(hist_rows, y_col, divide_by)
    x_historical = list(range(len(hist_rows)))

    x_projected = list(range(len(hist_rows) - 1, len(hist_rows) - 1 + len(proj_rows)))
    scenarios = {}
    for name, col in scenario_cols.items():
        scenarios[name] = extract_y(proj_rows, col, divide_by)

    # Map linestyle strings to matplotlib values
    if "scenario_styles" in params:
        params["scenario_styles"] = {
            k: _LINESTYLE_MAP.get(v, v)
            for k, v in params["scenario_styles"].items()
        }

    chart.projection(
        x_historical=x_historical,
        y_historical=y_historical,
        scenarios=scenarios,
        x_projected=x_projected,
        **params,
    )


def _build_combo(chart: Chart, rows: List[dict], columns: dict, params: dict, divide_by: float):
    from .series import ComboGroup, ComboItem

    series_spec = columns["series"]  # dict of {label: {column, type, axis, ...}}
    import numpy as np

    x = list(range(len(rows)))
    items = []
    for label, spec in series_spec.items():
        col = spec["column"]
        values = extract_y(rows, col, divide_by)
        items.append(ComboItem(
            values=np.asarray(values, dtype=float),
            series_type=spec.get("type", "bar"),
            axis=spec.get("axis", "left"),
            label=label,
            color=spec.get("color"),
            label_format=spec.get("label_format"),
        ))
    chart.combo(x=x, items=items)


# ═══════════════════════════════════════════════════════════════════════════════
# Annotations, separators, legend
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_annotations(chart: Chart, ann_spec: dict):
    if not ann_spec:
        return

    if "endpoints" in ann_spec:
        ep = dict(ann_spec["endpoints"])
        if "offset" in ep:
            ep["offset"] = tuple(ep["offset"])
        chart.annotate_endpoints(**ep)

    for pt in ann_spec.get("points", []):
        pt = dict(pt)
        if "offset" in pt:
            pt["offset"] = tuple(pt["offset"])
        chart.annotate_point(**pt)


def _apply_separators(chart: Chart, x_labels: list, sep_spec: dict, rows: List[dict], columns: dict):
    if not sep_spec:
        return

    if sep_spec.get("auto") and x_labels:
        trigger = sep_spec.get("trigger", "Jan")
        chart.auto_separators(x_labels, trigger=trigger)

    if sep_spec.get("auto_projection"):
        x_date_col = columns.get("x_date")
        projection_start = str(columns.get("projection_start", ""))
        if x_date_col and projection_start:
            for i, row in enumerate(rows):
                if row[x_date_col][:10] >= projection_start:
                    chart.separators([i - 0.5])
                    break

    if "positions" in sep_spec:
        chart.separators(sep_spec["positions"])


# ═══════════════════════════════════════════════════════════════════════════════
# Defaults resolution
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_defaults(config: dict):
    """Build Theme, Branding, output_dir, figsize from defaults block."""
    defaults = config.get("defaults", {})

    # Theme
    theme_overrides = defaults.get("theme", {})
    if "palette" in theme_overrides and isinstance(theme_overrides["palette"], list):
        theme_overrides["palette"] = tuple(theme_overrides["palette"])
    if "font_sans_serif" in theme_overrides and isinstance(theme_overrides["font_sans_serif"], list):
        theme_overrides["font_sans_serif"] = tuple(theme_overrides["font_sans_serif"])
    theme = Theme.default().replace(**theme_overrides) if theme_overrides else Theme.default()

    # Branding
    branding_spec = defaults.get("branding", {})
    if branding_spec:
        # Support nested logo:/footer: blocks by flattening to Branding fields
        flat = {}
        logo = branding_spec.get("logo")
        if isinstance(logo, dict):
            for k, v in logo.items():
                flat[f"logo_{k}"] = v
        footer = branding_spec.get("footer")
        if isinstance(footer, dict):
            for k, v in footer.items():
                flat[f"footer_{k}"] = v
        # Also pass through any already-flat keys (e.g. logo_path, footer_text)
        for k, v in branding_spec.items():
            if k not in ("logo", "footer"):
                flat[k] = v
        # Convert list positions to tuples
        for key in ("logo_position", "logo_alignment"):
            if key in flat and isinstance(flat[key], list):
                flat[key] = tuple(flat[key])
        branding = Branding(**flat)
    else:
        branding = Branding.none()

    output_dir = defaults.get("output_dir", ".")
    figsize_list = defaults.get("figsize")
    default_figsize = tuple(figsize_list) if figsize_list else None

    return theme, branding, output_dir, default_figsize


# ═══════════════════════════════════════════════════════════════════════════════
# Main orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

def build_chart(
    chart_name: str,
    chart_spec: dict,
    theme: Theme,
    branding: Branding,
    output_dir: str,
    default_figsize: Optional[tuple],
    named_sources: dict,
    source_cache: Dict[str, List[dict]] | None = None,
):
    """Full pipeline for a single chart definition."""
    print(f"  Building {chart_name}...", end=" ", flush=True)

    # 0. Validate required top-level keys
    if "source" not in chart_spec:
        raise ValueError(f"Chart '{chart_name}': missing required key 'source'")
    if "type" not in chart_spec:
        raise ValueError(f"Chart '{chart_name}': missing required key 'type'")

    # 1. Resolve source and load data
    src_ref = chart_spec["source"]
    source_name = src_ref if isinstance(src_ref, str) else None
    source = resolve_source(src_ref, named_sources)
    rows = load_data(source, source_cache=source_cache, source_name=source_name)

    # 1b. Validate columns exist in data
    columns = chart_spec.get("columns", {})
    chart_type = chart_spec["type"]
    if rows:
        available = set(rows[0].keys())

        # Validate scalar column references
        for key in ("x_date", "y"):
            col = columns.get(key)
            if col and col not in available:
                raise KeyError(
                    f"Chart '{chart_name}': column '{col}' (columns.{key}) "
                    f"not found in data. Available columns: {sorted(available)}"
                )

        # Validate y is present for types that need it
        if chart_type in ("bar", "line", "projection") and "y" not in columns:
            raise ValueError(
                f"Chart '{chart_name}': 'columns.y' is required for type '{chart_type}'"
            )

        # Validate stacked_bar / stacked_area layers
        if chart_type in ("stacked_bar", "stacked_area"):
            if "layers" not in columns:
                raise ValueError(
                    f"Chart '{chart_name}': 'columns.layers' is required for type '{chart_type}'"
                )
            for label, col_name in columns["layers"].items():
                if col_name not in available:
                    raise KeyError(
                        f"Chart '{chart_name}': layer column '{col_name}' (layers.{label}) "
                        f"not found in data. Available columns: {sorted(available)}"
                    )

        # Validate combo-specific columns
        if chart_type == "combo":
            if "series" not in columns:
                raise ValueError(
                    f"Chart '{chart_name}': 'columns.series' is required for type 'combo'"
                )
            for label, spec in columns["series"].items():
                col = spec.get("column")
                if col and col not in available:
                    raise KeyError(
                        f"Chart '{chart_name}': series column '{col}' (series.{label}) "
                        f"not found in data. Available columns: {sorted(available)}"
                    )

        # Validate projection-specific columns
        if chart_type == "projection":
            if "scenarios" not in columns:
                raise ValueError(
                    f"Chart '{chart_name}': 'columns.scenarios' is required for type 'projection'"
                )
            for name, col_name in columns["scenarios"].items():
                if col_name not in available:
                    raise KeyError(
                        f"Chart '{chart_name}': scenario column '{col_name}' (scenarios.{name}) "
                        f"not found in data. Available columns: {sorted(available)}"
                    )
            if "projection_start" not in columns:
                raise ValueError(
                    f"Chart '{chart_name}': 'columns.projection_start' is required for type 'projection'"
                )

    # 2. Transform data
    transform = chart_spec.get("transform", {})
    rows = transform_data(rows, transform, columns)
    divide_by = transform.get("divide_y", 1)

    if not rows:
        print("SKIPPED (no data after filtering)")
        return

    # 3. Build x-axis labels
    labels_spec = chart_spec.get("x_labels", {})
    x_labels = build_x_labels(rows, columns, labels_spec)

    # 4. Create Chart
    figsize_list = chart_spec.get("figsize")
    figsize = tuple(figsize_list) if figsize_list else default_figsize
    chart = Chart(
        title=chart_spec.get("title", ""),
        subtitle=chart_spec.get("subtitle", ""),
        theme=theme,
        branding=branding,
        figsize=figsize,
    )

    # 5. Dispatch to type-specific builder
    params = dict(chart_spec.get("params", {}))

    if chart_type == "bar":
        _build_bar(chart, rows, columns, params, divide_by)
    elif chart_type == "line":
        _build_line(chart, rows, columns, params, divide_by)
    elif chart_type == "stacked_bar":
        _build_stacked_bar(chart, rows, columns, params, divide_by)
    elif chart_type == "stacked_area":
        _build_stacked_area(chart, rows, columns, params, divide_by)
    elif chart_type == "projection":
        _build_projection(chart, rows, columns, params, divide_by)
    elif chart_type == "combo":
        _build_combo(chart, rows, columns, params, divide_by)
    else:
        raise ValueError(f"Unknown chart type: '{chart_type}'")

    # 6. X labels
    if x_labels:
        fontsize = labels_spec.get("fontsize")
        kwargs = {}
        if fontsize:
            kwargs["fontsize"] = fontsize
        chart.x_labels(x_labels, **kwargs)

    # 7. Y format
    y_fmt = chart_spec.get("y_format", {})
    if y_fmt:
        kwargs = {}
        if "step" in y_fmt:
            kwargs["step"] = y_fmt["step"]
        chart.y_format(y_fmt["style"], **kwargs)

    # 7b. Right y-axis format (combo charts)
    y_fmt_right = chart_spec.get("y_format_right", {})
    if y_fmt_right:
        kwargs = {}
        if "step" in y_fmt_right:
            kwargs["step"] = y_fmt_right["step"]
        chart.y_format_right(y_fmt_right["style"], **kwargs)

    # 7c. Axis labels
    axis_labels_spec = chart_spec.get("axis_labels", {})
    if axis_labels_spec:
        chart.axis_labels(**axis_labels_spec)

    # 8. Axis limits
    if "y_lim" in chart_spec:
        chart.y_lim(**chart_spec["y_lim"])
    if "x_lim" in chart_spec:
        chart.x_lim(**chart_spec["x_lim"])
    if "y_lim_right" in chart_spec:
        chart.y_lim_right(**chart_spec["y_lim_right"])

    # 9. Annotations
    _apply_annotations(chart, chart_spec.get("annotations", {}))

    # 10. Separators
    _apply_separators(chart, x_labels, chart_spec.get("separators", {}), rows, columns)

    # 11. Legend
    legend_spec = chart_spec.get("legend", {})
    if legend_spec:
        chart.legend(**legend_spec)

    # 12. Save
    output_filename = chart_spec.get("output", f"{chart_name}.png")
    output_path = os.path.join(output_dir, output_filename)

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    save_kwargs = {}
    if "dpi" in chart_spec:
        save_kwargs["dpi"] = chart_spec["dpi"]
    if "transparent" in chart_spec:
        save_kwargs["transparent"] = chart_spec["transparent"]

    chart.save(output_path, **save_kwargs)
    chart.close()
    print(f"OK -> {output_path}")


def load_config(yaml_path: str) -> dict:
    """Load and return the parsed YAML config."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def _archive_build(output_dir: str):
    """Copy all files in output_dir (except .archive/) into a timestamped archive folder."""
    output_path = Path(output_dir)
    archive_dir = output_path / ".archive"
    build_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    build_dir = archive_dir / build_id
    build_dir.mkdir(parents=True, exist_ok=True)

    for item in output_path.iterdir():
        if item.name == ".archive":
            continue
        dest = build_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    print(f"  Archived to {build_dir}/")


def build_all(yaml_path: str, select: Optional[list[str]] = None):
    """Load YAML config and generate charts."""
    print(f"Loading {yaml_path}")

    config = load_config(yaml_path)
    theme, branding, output_dir, default_figsize = resolve_defaults(config)
    named_sources = config.get("sources", {})
    source_cache = _resolve_dep_sources(named_sources)
    charts = config.get("charts", {})

    if not charts:
        print("No charts defined.")
        return

    # Filter to selected charts if specified
    if select:
        unknown = [s for s in select if s not in charts]
        if unknown:
            print(f"Unknown chart(s): {', '.join(unknown)}")
            print(f"Available: {', '.join(charts.keys())}")
            return
        charts = {k: v for k, v in charts.items() if k in select}

    # Clean output directory (preserve .archive/)
    output_path = Path(output_dir)
    if output_path.exists():
        for item in output_path.iterdir():
            if item.name == ".archive":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    print(f"Building {len(charts)} chart(s)...\n")

    for chart_name, chart_spec in charts.items():
        build_chart(
            chart_name, chart_spec,
            theme=theme,
            branding=branding,
            output_dir=output_dir,
            default_figsize=default_figsize,
            named_sources=named_sources,
            source_cache=source_cache,
        )

    # Archive the build
    _archive_build(output_dir)

    print(f"\nDone. {len(charts)} chart(s) written to {output_dir}/")


def list_charts(yaml_path: str):
    """List all charts defined in the config."""
    config = load_config(yaml_path)
    charts = config.get("charts", {})

    if not charts:
        print("No charts defined.")
        return

    for name, spec in charts.items():
        chart_type = spec.get("type", "?")
        title = spec.get("title", "")
        print(f"  {name}  ({chart_type})  {title}")
