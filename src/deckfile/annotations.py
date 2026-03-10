from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from .series import AnnotationRequest, BarSeries, LineSeries, SeparatorRequest
    from .theme import Theme


def render_endpoints(
    ax: Axes,
    series: BarSeries | LineSeries,
    annotation: AnnotationRequest,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    """Render scatter dots, halos, and value labels at series endpoints."""
    x_data = np.asarray(series.x)
    y_data = np.asarray(series.y)
    color = series.color or theme.palette[palette_index % len(theme.palette)]

    n = len(x_data)
    if n == 0:
        return

    if annotation.which == "first_last":
        indices = [0, n - 1] if n > 1 else [0]
    elif annotation.which == "last":
        indices = [n - 1]
    elif annotation.which == "first":
        indices = [0]
    elif annotation.which == "all":
        indices = list(range(n))
    else:
        indices = [0, n - 1] if n > 1 else [0]

    for i in indices:
        # Scatter dot
        ax.scatter(
            x_data[i], y_data[i],
            color=color,
            s=theme.endpoint_size,
            zorder=7,
            edgecolors=theme.bg_color,
            linewidths=theme.endpoint_edge_width,
        )

        # Halo on last point
        if annotation.halo and i == n - 1:
            ax.scatter(
                x_data[i], y_data[i],
                color=color,
                s=theme.halo_size,
                zorder=6,
                alpha=theme.halo_alpha,
                edgecolors="none",
            )

        # Value label
        if annotation.formatter:
            label_text = annotation.formatter(float(y_data[i]))
        elif annotation.format:
            val = float(y_data[i])
            label_text = annotation.format.format(
                value=val,
                value_k=val / 1000,
                value_m=val / 1_000_000,
            )
        else:
            label_text = f"{y_data[i]:,.0f}"

        ax.annotate(
            label_text,
            (x_data[i], y_data[i]),
            textcoords="offset points",
            xytext=annotation.offset,
            fontsize=theme.annotation_size,
            fontweight=theme.annotation_weight,
            color=color,
            ha="center",
            va="bottom",
        )


def render_point_annotation(
    ax: Axes,
    ann: AnnotationRequest,
    theme: Theme,
) -> None:
    """Render a custom annotation at a specific point."""
    color = ann.color or theme.subtle_text
    fontsize = ann.fontsize or theme.annotation_size
    fontweight = ann.fontweight or "normal"

    if ann.dot:
        ax.scatter(
            ann.x, ann.y,
            color=color,
            s=theme.endpoint_size,
            zorder=7,
            edgecolors=theme.bg_color,
            linewidths=theme.endpoint_edge_width,
        )

    if ann.halo:
        ax.scatter(
            ann.x, ann.y,
            color=color,
            s=theme.halo_size,
            zorder=6,
            alpha=theme.halo_alpha,
            edgecolors="none",
        )

    ax.annotate(
        ann.text,
        (ann.x, ann.y),
        textcoords="offset points",
        xytext=ann.offset,
        fontsize=fontsize,
        fontweight=fontweight,
        color=color,
        ha=ann.ha,
        va=ann.va,
        alpha=ann.alpha,
    )


def render_separators(
    ax: Axes,
    separators: list[SeparatorRequest],
    theme: Theme,
) -> None:
    """Render vertical separator lines."""
    for sep in separators:
        ax.axvline(
            x=sep.x,
            color=sep.color or theme.separator,
            linewidth=sep.linewidth or theme.separator_linewidth,
            alpha=sep.alpha or theme.separator_alpha,
        )
