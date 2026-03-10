from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..interpolation import smooth_curve

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..series import StackedAreaGroup
    from ..theme import Theme


def render_stacked_area(
    ax: Axes,
    group: StackedAreaGroup,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    x = np.asarray(group.x, dtype=float)
    layer_names = list(group.layers.keys())
    layer_values = [np.asarray(group.layers[k], dtype=float) for k in layer_names]

    # Normalize to 100% if requested
    if group.normalize:
        totals = np.sum(layer_values, axis=0)
        totals = np.where(totals == 0, 1, totals)  # avoid division by zero
        layer_values = [(v / totals) * 100 for v in layer_values]

    # Build cumulative sums (bottom-up)
    cumulative = np.zeros(len(x), dtype=float)
    bottoms = []
    tops = []
    for values in layer_values:
        bottoms.append(cumulative.copy())
        cumulative = cumulative + values
        tops.append(cumulative.copy())

    # Render each layer
    for i, label in enumerate(layer_names):
        color = group.colors.get(label, theme.area_palette[(palette_index + i) % len(theme.area_palette)])
        alpha = group.alphas.get(label, 0.7)

        bottom = bottoms[i]
        top = tops[i]

        if group.smooth and len(x) >= 2:
            x_smooth, top_smooth = smooth_curve(
                x, top,
                num_points=theme.smooth_points,
                degree=theme.spline_degree,
            )
            _, bottom_smooth = smooth_curve(
                x, bottom,
                num_points=theme.smooth_points,
                degree=theme.spline_degree,
            )
            # Clamp smoothed values for normalized charts
            if group.normalize:
                top_smooth = np.clip(top_smooth, 0, 100)
                bottom_smooth = np.clip(bottom_smooth, 0, 100)
        else:
            x_smooth = x
            top_smooth = top
            bottom_smooth = bottom

        # Filled area
        ax.fill_between(
            x_smooth, bottom_smooth, top_smooth,
            color=color, alpha=alpha, linewidth=0,
            label=label,
        )

        # Top edge line
        ax.plot(
            x_smooth, top_smooth,
            color=color, linewidth=1.5, alpha=min(alpha + 0.2, 1.0),
            zorder=4,
        )

        # Markers at real data points
        if group.markers:
            ax.scatter(
                x, top,
                color=color, s=20, zorder=5,
                edgecolors="white", linewidths=0.5,
            )
