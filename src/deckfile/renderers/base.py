from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from ..annotations import (
    render_bar_layer_labels,
    render_change,
    render_endpoints,
    render_point_annotation,
    render_separators,
    render_x_groups,
)
from ..formatters import get_formatter
from ..series import BarSeries, ComboGroup, LineSeries, ProjectionScenario, StackedAreaGroup, StackedBarGroup
from .area import render_stacked_area
from .bar import render_bar_series, render_stacked_bar
from .combo import render_combo
from .line import render_line_series
from .projection import render_projection
from .stacking import normalize_layers

if TYPE_CHECKING:
    from ..chart import Chart

matplotlib.use("Agg")


def build_figure(chart: Chart) -> tuple:
    """Build and return (fig, ax) with all series, annotations, and styling."""
    theme = chart._theme
    branding = chart._branding

    # 1. Apply rcParams
    plt.rcParams.update({
        "font.family": theme.font_family,
        "font.sans-serif": list(theme.font_sans_serif),
    })

    # 2. Create figure
    figsize = chart._figsize or (theme.figure_width, theme.figure_height)
    fig, ax = plt.subplots(figsize=figsize, facecolor=theme.bg_color)

    # 3. Style axes
    ax.set_facecolor(theme.bg_color)
    if theme.y_grid:
        ax.yaxis.grid(True, color=theme.grid_color, linewidth=theme.grid_linewidth)
    if theme.x_grid:
        ax.xaxis.grid(True, color=theme.grid_color, linewidth=theme.grid_linewidth)
    else:
        ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="y", labelsize=theme.axis_label_size, colors=theme.subtle_text, pad=8, length=0)
    ax.tick_params(axis="x", length=0, pad=10)

    # 4. Render series in order
    palette_counter = 0
    for series in chart._series:
        if isinstance(series, BarSeries):
            render_bar_series(ax, series, theme, palette_index=palette_counter)
            palette_counter += 1
        elif isinstance(series, StackedBarGroup):
            render_stacked_bar(ax, series, theme, palette_index=palette_counter)
            palette_counter += len(series.layers)
        elif isinstance(series, StackedAreaGroup):
            render_stacked_area(ax, series, theme, palette_index=palette_counter)
            palette_counter += len(series.layers)
        elif isinstance(series, LineSeries):
            render_line_series(ax, series, theme, palette_index=palette_counter)
            palette_counter += 1
        elif isinstance(series, ComboGroup):
            render_combo(ax, series, theme, chart, palette_index=palette_counter)
            palette_counter += len(series.items)
        elif isinstance(series, ProjectionScenario):
            render_projection(ax, series, theme, palette_index=palette_counter)
            palette_counter += 1 + len(series.scenarios)

    # 5. Separators
    render_separators(ax, chart._separators, theme)

    # 6. Annotations
    for ann in chart._annotations:
        if ann.kind == "endpoints":
            for i, series in enumerate(chart._series):
                if ann.series_index is not None and ann.series_index != i:
                    continue
                # Find the palette index for this series
                pi = 0
                for j, s in enumerate(chart._series):
                    if j == i:
                        break
                    if isinstance(s, (BarSeries, LineSeries)):
                        pi += 1
                    elif isinstance(s, (StackedBarGroup, StackedAreaGroup)):
                        pi += len(s.layers)
                    elif isinstance(s, ComboGroup):
                        pi += len(s.items)
                    elif isinstance(s, ProjectionScenario):
                        pi += 1 + len(s.scenarios)

                # Combo groups handle their own data labels in the renderer
                if isinstance(series, ComboGroup):
                    continue

                if isinstance(series, (BarSeries, LineSeries)):
                    render_endpoints(ax, series, ann, theme, palette_index=pi)
                elif isinstance(series, StackedBarGroup):
                    layer_names = list(series.layers.keys())
                    layer_values = [np.asarray(series.layers[k], dtype=float) for k in layer_names]
                    if series.normalize:
                        layer_values = normalize_layers(layer_values)

                    if ann.layer is not None:
                        # Target a single band: label its own value, not the
                        # column total (which on a normalized stack is always 100).
                        if ann.layer not in layer_names:
                            continue
                        li = layer_names.index(ann.layer)
                        bottoms = np.sum(layer_values[:li], axis=0) if li else np.zeros(len(series.x))
                        color = series.colors.get(
                            ann.layer,
                            theme.palette[(pi + li) % len(theme.palette)],
                        )
                        render_bar_layer_labels(
                            ax, series.x, bottoms, layer_values[li], ann, theme, color=color,
                        )
                    else:
                        totals = np.sum(layer_values, axis=0)
                        proxy = BarSeries(
                            x=series.x,
                            y=totals,
                            color=theme.brand,
                        )
                        render_endpoints(ax, proxy, ann, theme, palette_index=pi)
                elif isinstance(series, StackedAreaGroup):
                    layer_names = list(series.layers.keys())
                    layer_values = [np.asarray(series.layers[k], dtype=float) for k in layer_names]
                    if series.normalize:
                        layer_values = normalize_layers(layer_values)
                    # Cumulative tops per layer
                    cumulative = np.zeros(len(series.x), dtype=float)
                    layer_tops = {}
                    for li, name in enumerate(layer_names):
                        cumulative = cumulative + layer_values[li]
                        layer_tops[name] = cumulative.copy()
                    # Annotate specific layer boundary, or top of stack
                    if ann.layer is not None:
                        if ann.layer not in layer_tops:
                            continue
                        target_name = ann.layer
                        li = layer_names.index(target_name)
                    else:
                        target_name = layer_names[-1]
                        li = len(layer_names) - 1
                    proxy = LineSeries(
                        x=series.x,
                        y=layer_tops[target_name],
                        color=theme.brand,
                    )
                    render_endpoints(ax, proxy, ann, theme, palette_index=pi + li)
        elif ann.kind == "point":
            render_point_annotation(ax, ann, theme)

    # 6b. Change brackets
    change_x = _render_changes(ax, chart, theme)

    # 7. X-axis labels
    if chart._x_labels:
        x_positions = np.arange(len(chart._x_labels))
        ax.set_xticks(x_positions)
        ax.set_xticklabels(
            chart._x_labels,
            fontsize=getattr(chart, "_x_label_fontsize", None) or theme.tick_label_size,
            color=theme.subtle_text,
            ha="center",
        )

    # 8. Y-axis formatting
    if chart._y_format:
        ax.yaxis.set_major_formatter(get_formatter(chart._y_format))

    if chart._y_locator_step:
        ax.yaxis.set_major_locator(mticker.MultipleLocator(chart._y_locator_step))

    # Drop the tick numbers but keep the ticks themselves, so the grid lines
    # (and anything positioned against them) are unchanged.
    if getattr(chart, "_y_hidden", False):
        ax.tick_params(axis="y", labelleft=False)

    # 8b. Right y-axis formatting (combo charts)
    ax2 = chart._ax2
    if ax2 is not None:
        ax2.set_facecolor(theme.bg_color)
        for s in ax2.spines.values():
            s.set_visible(False)
        ax2.tick_params(axis="y", labelsize=theme.axis_label_size, colors=theme.subtle_text, pad=8, length=0)
        if theme.y_grid:
            ax2.yaxis.grid(False)  # avoid double grid lines

        if chart._y_format_right:
            ax2.yaxis.set_major_formatter(get_formatter(chart._y_format_right))
        if chart._y_locator_step_right:
            ax2.yaxis.set_major_locator(mticker.MultipleLocator(chart._y_locator_step_right))
        if getattr(chart, "_y_hidden_right", False):
            ax2.tick_params(axis="y", labelright=False)

    # 8c. Axis labels
    if chart._y_axis_label:
        ax.set_ylabel(chart._y_axis_label, fontsize=theme.axis_label_size, color=theme.subtle_text)
    if chart._y_axis_label_right and ax2 is not None:
        ax2.set_ylabel(chart._y_axis_label_right, fontsize=theme.axis_label_size, color=theme.subtle_text)
    if chart._x_axis_label:
        ax.set_xlabel(chart._x_axis_label, fontsize=theme.axis_label_size, color=theme.subtle_text)

    # 9. Axis limits
    if chart._y_lim:
        ax.set_ylim(*chart._y_lim)
    else:
        ax.set_ylim(0, None)
        ax.margins(y=0.08)

    if chart._x_lim:
        ax.set_xlim(*chart._x_lim)
    else:
        _auto_xlim(ax, chart._series, extra_x=change_x)

    # 9b. Right y-axis limits
    if ax2 is not None:
        if chart._y_lim_right:
            ax2.set_ylim(*chart._y_lim_right)
        else:
            ax2.set_ylim(0, None)
            ax2.margins(y=0.08)

    # 10. Legend
    _build_legend(ax, chart, theme)

    # 11. Title and subtitle
    has_logo = branding.logo_path is not None
    if has_logo:
        if chart._title:
            ax.text(
                0.0, 1.26, chart._title,
                transform=ax.transAxes,
                fontsize=theme.title_size,
                fontweight=theme.title_weight,
                color=theme.text_color,
                ha="left", va="top",
            )
        if chart._subtitle:
            ax.text(
                0.0, 1.17, chart._subtitle,
                transform=ax.transAxes,
                fontsize=theme.subtitle_size,
                color=theme.subtle_text,
                ha="left", va="top",
            )
    else:
        if chart._title:
            fig.text(
                theme.title_x, theme.title_y, chart._title,
                fontsize=theme.title_size,
                fontweight=theme.title_weight,
                color=theme.text_color,
                ha="left", va="top",
            )
        if chart._subtitle:
            fig.text(
                theme.title_x, theme.subtitle_y, chart._subtitle,
                fontsize=theme.subtitle_size,
                color=theme.subtle_text,
                ha="left", va="top",
            )

    # 12. Branding
    _render_branding(ax, fig, branding, theme)

    # 13. Layout
    has_dual_axis = chart._ax2 is not None
    margin_right = 0.88 if has_logo else (0.88 if has_dual_axis else theme.margin_right)
    plt.subplots_adjust(
        left=theme.margin_left,
        right=margin_right,
        top=theme.margin_top,
        bottom=theme.margin_bottom,
    )

    # 14. X-axis group labels — last, because they are positioned by measuring
    # the rendered tick labels, which needs the final limits and layout.
    render_x_groups(ax, chart._x_groups, theme)

    return fig, ax


def _series_xy(series, theme, layer=None):
    """Resolve a series to (x, y, axis, bar_half_width) for change lookups.

    ``layer`` names a stacked layer, a projection scenario, or a combo item;
    without it a stacked group resolves to its column totals. Returns None when
    the series has no series matching ``layer``.
    """
    if isinstance(series, BarSeries):
        half = (series.width or theme.bar_width) / 2
        return series.x, series.y, "left", half
    if isinstance(series, LineSeries):
        return series.x, series.y, "left", 0.0
    if isinstance(series, (StackedBarGroup, StackedAreaGroup)):
        names = list(series.layers.keys())
        values = [np.asarray(series.layers[k], dtype=float) for k in names]
        if series.normalize:
            values = normalize_layers(values)
        if layer is not None:
            if layer not in names:
                return None
            y = values[names.index(layer)]
        else:
            y = np.sum(values, axis=0)
        half = 0.0
        if isinstance(series, StackedBarGroup):
            half = (series.width or theme.bar_width) / 2
        return series.x, y, "left", half
    if isinstance(series, ComboGroup):
        for item in series.items:
            if layer is None or item.label == layer:
                half = theme.bar_width / 2 if item.series_type == "bar" else 0.0
                return series.x, np.asarray(item.values, dtype=float), item.axis, half
        return None
    if isinstance(series, ProjectionScenario):
        if layer is not None:
            if layer not in series.scenarios:
                return None
            return series.x_projected, np.asarray(series.scenarios[layer], dtype=float), "left", 0.0
        return series.x_historical, series.y_historical, "left", 0.0
    return None


def _resolve_x(x_arr, x):
    """Resolve a change endpoint: negative integers index back from the end."""
    x = float(x)
    if x < 0 and float(x).is_integer() and len(x_arr) >= abs(int(x)):
        return float(x_arr[int(x)])
    return x


def _value_at(x_arr, y_arr, x):
    """Value of a series at an x position — exact match, else interpolated."""
    exact = np.flatnonzero(np.isclose(x_arr, x))
    if exact.size:
        return float(y_arr[exact[0]])
    order = np.argsort(x_arr)
    return float(np.interp(x, np.asarray(x_arr)[order], np.asarray(y_arr)[order]))


def _render_changes(ax, chart, theme):
    """Render every change bracket; return the x positions of their arrows."""
    if not chart._changes:
        return []

    arrow_positions = []
    for change in chart._changes:
        target = None
        if change.series_index is not None:
            if change.series_index < len(chart._series):
                target = _series_xy(
                    chart._series[change.series_index], theme, change.layer
                )
        else:
            for series in chart._series:
                target = _series_xy(series, theme, change.layer)
                if target is not None:
                    break

        if target is None:
            # Nothing to measure — unless both values were given outright.
            if change.from_value is None or change.to_value is None:
                continue
            x_arr, y_arr, axis_name, half = np.asarray([]), np.asarray([]), "left", 0.0
        else:
            x_arr, y_arr, axis_name, half = target

        from_x = _resolve_x(x_arr, change.from_x)
        to_x = _resolve_x(x_arr, change.to_x)

        from_value = change.from_value
        to_value = change.to_value
        if len(x_arr):
            if from_value is None:
                from_value = _value_at(x_arr, y_arr, from_x)
            if to_value is None:
                to_value = _value_at(x_arr, y_arr, to_x)
        if from_value is None or to_value is None:
            continue

        arrow_x = change.at if change.at is not None else max(from_x, to_x) + change.gap
        arrow_positions.append(arrow_x)

        target_ax = chart._ax2 if (axis_name == "right" and chart._ax2 is not None) else ax
        render_change(
            target_ax, change, theme,
            from_x=from_x,
            to_x=to_x,
            from_value=float(from_value),
            to_value=float(to_value),
            arrow_x=arrow_x,
            bar_half_width=half,
        )

    return arrow_positions


def _auto_xlim(ax, series_list, extra_x=None):
    """Compute sensible x-axis limits from all series data."""
    all_x = []
    for s in series_list:
        if isinstance(s, (BarSeries, LineSeries)):
            all_x.extend(s.x.tolist())
        elif isinstance(s, (StackedBarGroup, StackedAreaGroup)):
            all_x.extend(s.x.tolist())
        elif isinstance(s, ComboGroup):
            all_x.extend(s.x.tolist())
        elif isinstance(s, ProjectionScenario):
            all_x.extend(s.x_historical.tolist())
            all_x.extend(s.x_projected.tolist())

    if not all_x:
        return

    left, right = min(all_x) - 0.6, max(all_x) + 0.4

    # Keep anything drawn outside the data range (a change bracket sitting past
    # the last bar) inside the frame, without padding it as generously.
    if extra_x:
        left = min(left, min(extra_x) - 0.2)
        right = max(right, max(extra_x) + 0.2)

    ax.set_xlim(left, right)


def _build_legend(ax, chart, theme):
    """Build and style the legend if appropriate."""
    # Check for projection-specific handles first
    projection_handles = getattr(ax, "_deckfile_legend_handles", None)

    if chart._legend_enabled is False:
        return

    if projection_handles:
        legend = ax.legend(
            handles=projection_handles,
            loc=chart._legend_loc,
            fontsize=theme.legend_fontsize,
            frameon=theme.legend_frameon,
            fancybox=theme.legend_fancybox,
            borderpad=theme.legend_borderpad,
            labelspacing=theme.legend_labelspacing,
            handlelength=theme.legend_handlelength,
            edgecolor=theme.grid_color,
            facecolor=theme.bg_color,
        )
    else:
        # Collect handles from regular matplotlib artists
        handles, labels = ax.get_legend_handles_labels()
        if not handles:
            return
        if chart._legend_enabled is None and len(handles) <= 1:
            return

        legend = ax.legend(
            loc=chart._legend_loc,
            fontsize=theme.legend_fontsize,
            frameon=theme.legend_frameon,
            fancybox=theme.legend_fancybox,
            borderpad=theme.legend_borderpad,
            labelspacing=theme.legend_labelspacing,
            handlelength=theme.legend_handlelength,
            edgecolor=theme.grid_color,
            facecolor=theme.bg_color,
        )

    for t in legend.get_texts():
        t.set_color(theme.text_color)
    legend.get_frame().set_linewidth(theme.legend_linewidth)
    legend.get_frame().set_alpha(theme.legend_alpha)


def _darken_hex(color: str, factor: float = 0.6) -> str:
    """Return a darker version of a hex color (factor 0-1, lower = darker)."""
    c = color.lstrip("#")
    r, g, b = int(c[:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor), int(b * factor))


def _render_branding(ax, fig, branding, theme):
    """Render optional logo and footer text."""
    if branding.logo_path:
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage

        logo_path = Path(branding.logo_path)

        if logo_path.suffix.lower() == ".svg":
            try:
                import cairosvg
            except ImportError:
                raise ImportError(
                    "cairosvg is required for SVG logos. "
                    "Install with: pip install deckfile[svg]"
                )
            png_data = cairosvg.svg2png(url=str(logo_path), output_width=200)
            buf = io.BytesIO(png_data)
            logo_img = plt.imread(buf)
        else:
            logo_img = plt.imread(str(logo_path))

        logo_box = OffsetImage(logo_img, zoom=branding.logo_zoom)
        logo_ab = AnnotationBbox(
            logo_box,
            branding.logo_position,
            xycoords="axes fraction",
            box_alignment=branding.logo_alignment,
            frameon=False,
        )
        ax.add_artist(logo_ab)

    if branding.footer_text:
        fig.text(
            branding.footer_x,
            branding.footer_y,
            branding.footer_text,
            fontsize=theme.footer_size,
            color=theme.subtle_text,
            ha=branding.footer_ha,
            va=branding.footer_va,
            fontstyle="italic",
            alpha=branding.footer_alpha,
        )
