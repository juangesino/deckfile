from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.patheffects as pe
import numpy as np

from ..interpolation import smooth_curve

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..series import LineSeries
    from ..theme import Theme


def render_line_series(
    ax: Axes,
    series: LineSeries,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    color = series.color or theme.palette[palette_index % len(theme.palette)]
    linewidth = series.linewidth or theme.line_width

    x_plot = np.asarray(series.x, dtype=float)
    y_plot = np.asarray(series.y, dtype=float)

    # Smooth interpolation
    if series.smooth and len(x_plot) >= 2:
        x_plot, y_plot = smooth_curve(
            x_plot, y_plot,
            num_points=theme.smooth_points,
            degree=theme.spline_degree,
        )

    # Fill under curve
    if series.fill:
        fill_alpha = series.fill_alpha if series.fill_alpha is not None else theme.fill_alpha
        ax.fill_between(x_plot, 0, y_plot, color=color, alpha=fill_alpha, linewidth=0)

    # Subtle background bars at data points
    if series.subtle_bars:
        ax.bar(
            series.x, series.y,
            width=theme.subtle_bar_width,
            color=color,
            alpha=theme.subtle_bar_alpha,
            zorder=2,
        )

    # Main line
    path_effects = []
    if series.glow:
        path_effects = [pe.withStroke(linewidth=theme.glow_width, foreground=color, alpha=theme.glow_alpha)]

    ax.plot(
        x_plot, y_plot,
        color=color,
        linewidth=linewidth,
        linestyle=series.linestyle,
        alpha=series.alpha,
        label=series.label,
        zorder=5,
        path_effects=path_effects if path_effects else None,
    )
