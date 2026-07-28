from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .rounded import apply_rounded_top_clip
from .stacking import normalize_layers

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..series import BarSeries, StackedBarGroup
    from ..theme import Theme


def render_bar_series(
    ax: Axes,
    series: BarSeries,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    color = series.color or theme.palette[palette_index % len(theme.palette)]
    alpha = series.alpha if series.alpha is not None else theme.bar_alpha
    width = series.width or theme.bar_width
    radius = series.corner_radius if series.corner_radius is not None else theme.bar_corner_radius

    container = ax.bar(
        series.x,
        series.y,
        width=width,
        color=color,
        alpha=alpha,
        label=series.label,
        zorder=series.zorder,
    )

    if radius and radius > 0:
        for rect in container:
            x0 = rect.get_x()
            w = rect.get_width()
            top = rect.get_y() + rect.get_height()
            if w <= 0 or rect.get_height() <= 0:
                continue
            apply_rounded_top_clip(
                ax, [rect], x0, x0 + w, top, radius,
                y_bottom=rect.get_y(),
            )


def render_stacked_bar(
    ax: Axes,
    group: StackedBarGroup,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    width = group.width or theme.bar_width
    radius = group.corner_radius if group.corner_radius is not None else theme.bar_corner_radius
    layer_names = list(group.layers.keys())
    layer_values = [np.asarray(group.layers[k], dtype=float) for k in layer_names]

    if group.normalize:
        layer_values = normalize_layers(layer_values)

    bottom = np.zeros(len(group.x), dtype=float)

    containers = []
    for i, label in enumerate(layer_names):
        values = layer_values[i]
        color = group.colors.get(label, theme.palette[(palette_index + i) % len(theme.palette)])
        alpha = group.alphas.get(label, 0.85 if i == 0 else 0.7)

        container = ax.bar(
            group.x,
            values,
            width=width,
            bottom=bottom,
            color=color,
            alpha=alpha,
            label=label,
            zorder=3,
        )
        containers.append(container)
        bottom = bottom + np.asarray(values, dtype=float)

    if not (radius and radius > 0):
        return

    # Clip every segment in a column to one rounded-top silhouette, so the whole
    # stack reads as a single bar with consistently rounded top corners.
    totals = bottom
    for col in range(len(group.x)):
        if totals[col] <= 0:
            continue
        ref = containers[0][col]
        x0 = ref.get_x()
        col_rects = [c[col] for c in containers]
        apply_rounded_top_clip(ax, col_rects, x0, x0 + ref.get_width(), totals[col], radius)
