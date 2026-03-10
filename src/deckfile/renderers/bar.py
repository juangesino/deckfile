from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

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

    ax.bar(
        series.x,
        series.y,
        width=width,
        color=color,
        alpha=alpha,
        label=series.label,
        zorder=series.zorder,
    )


def render_stacked_bar(
    ax: Axes,
    group: StackedBarGroup,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    width = group.width or theme.bar_width
    bottom = np.zeros(len(group.x), dtype=float)

    for i, (label, values) in enumerate(group.layers.items()):
        color = group.colors.get(label, theme.palette[(palette_index + i) % len(theme.palette)])
        alpha = group.alphas.get(label, 0.85 if i == 0 else 0.7)

        ax.bar(
            group.x,
            values,
            width=width,
            bottom=bottom,
            color=color,
            alpha=alpha,
            label=label,
            zorder=3,
        )
        bottom = bottom + np.asarray(values, dtype=float)
