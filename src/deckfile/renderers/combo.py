from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..series import ComboGroup
    from ..theme import Theme


def render_combo(
    ax: Axes,
    group: ComboGroup,
    theme: Theme,
    chart,
    *,
    palette_index: int = 0,
) -> None:
    """Render a combo chart with bars and lines on dual y-axes."""
    # Create secondary axis if any item targets "right"
    has_right = any(item.axis == "right" for item in group.items)
    ax2 = None
    if has_right:
        ax2 = ax.twinx()
        chart._ax2 = ax2

    handles = []
    pi = palette_index

    for item in group.items:
        target_ax = ax2 if (item.axis == "right" and ax2 is not None) else ax
        color = item.color or theme.palette[pi % len(theme.palette)]

        if item.series_type == "bar":
            target_ax.bar(
                group.x,
                item.values,
                width=theme.bar_width,
                color=color,
                alpha=theme.bar_alpha,
                zorder=3,
            )
            handles.append(Patch(facecolor=color, alpha=theme.bar_alpha, label=item.label or ""))

        elif item.series_type == "line":
            target_ax.plot(
                group.x,
                item.values,
                color=color,
                linewidth=theme.line_width,
                zorder=5,
                marker="o",
                markersize=6,
                markerfacecolor=color,
                markeredgecolor=theme.bg_color,
                markeredgewidth=1.5,
            )
            handles.append(Line2D(
                [0], [0], color=color, linewidth=theme.line_width,
                marker="o", markersize=6,
                markerfacecolor=color, markeredgecolor=theme.bg_color,
                label=item.label or "",
            ))

        # Data labels — bars centered inside, lines above with background
        if item.label_format:
            for xi, val in zip(group.x, item.values):
                fval = float(val)
                text = item.label_format.format(
                    value=fval,
                    value_k=fval / 1000,
                    value_m=fval / 1_000_000,
                )
                if item.series_type == "bar":
                    target_ax.text(
                        xi, fval / 2,
                        text,
                        fontsize=theme.annotation_size - 1,
                        fontweight=theme.annotation_weight,
                        color=color,
                        ha="center",
                        va="center",
                        zorder=8,
                        bbox=dict(
                            boxstyle="round,pad=0.15",
                            facecolor=theme.bg_color,
                            edgecolor="none",
                            alpha=0.8,
                        ),
                    )
                else:
                    target_ax.annotate(
                        text,
                        (xi, fval),
                        textcoords="offset points",
                        xytext=(0, 12),
                        fontsize=theme.annotation_size,
                        fontweight=theme.annotation_weight,
                        color=color,
                        ha="center",
                        va="bottom",
                        zorder=10,
                        bbox=dict(
                            boxstyle="round,pad=0.15",
                            facecolor=theme.bg_color,
                            edgecolor="none",
                            alpha=0.85,
                        ),
                    )

        pi += 1

    # Store handles for legend builder
    if handles:
        if not hasattr(ax, "_deckfile_legend_handles"):
            ax._deckfile_legend_handles = []
        ax._deckfile_legend_handles.extend(handles)
