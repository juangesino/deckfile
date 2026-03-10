from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from ..annotations import render_endpoints, render_point_annotation, render_separators
from ..formatters import get_formatter
from ..series import BarSeries, ComboGroup, LineSeries, ProjectionScenario, StackedAreaGroup, StackedBarGroup
from .area import render_stacked_area
from .bar import render_bar_series, render_stacked_bar
from .combo import render_combo
from .line import render_line_series
from .projection import render_projection

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
                    totals = np.sum(
                        [np.asarray(v, dtype=float) for v in series.layers.values()],
                        axis=0,
                    )
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
                        totals = np.sum(layer_values, axis=0)
                        totals = np.where(totals == 0, 1, totals)
                        layer_values = [(v / totals) * 100 for v in layer_values]
                    # Cumulative tops per layer
                    cumulative = np.zeros(len(series.x), dtype=float)
                    layer_tops = {}
                    for li, name in enumerate(layer_names):
                        cumulative = cumulative + layer_values[li]
                        layer_tops[name] = cumulative.copy()
                    # Annotate specific layer or top of stack
                    if ann.layer and ann.layer in layer_tops:
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
        _auto_xlim(ax, chart._series)

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

    return fig, ax


def _auto_xlim(ax, series_list):
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

    if all_x:
        ax.set_xlim(min(all_x) - 0.6, max(all_x) + 0.4)


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
