from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from .series import AnnotationRequest, BarSeries, LineSeries, SeparatorRequest
    from .theme import Theme


def select_indices(which: str, n: int) -> list[int]:
    """Resolve an endpoint selector ("first_last", "last", ...) to indices."""
    if n == 0:
        return []
    if which == "last":
        return [n - 1]
    if which == "first":
        return [0]
    if which == "all":
        return list(range(n))
    # "first_last" and anything unrecognized
    return [0, n - 1] if n > 1 else [0]


def format_value(annotation: AnnotationRequest, value: float) -> str:
    """Format a value with the annotation's formatter / format string."""
    val = float(value)
    if annotation.formatter:
        return annotation.formatter(val)
    if annotation.format:
        return annotation.format.format(
            value=val,
            value_k=val / 1000,
            value_m=val / 1_000_000,
        )
    return f"{val:,.0f}"


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

    indices = select_indices(annotation.which, n)

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
        label_text = format_value(annotation, y_data[i])

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


def render_bar_layer_labels(
    ax: Axes,
    x: np.ndarray,
    bottoms: np.ndarray,
    values: np.ndarray,
    annotation: AnnotationRequest,
    theme: Theme,
    *,
    color: str,
) -> None:
    """Label one band of a stacked bar with its own value, centered in the band.

    Unlike line/area endpoints, a bar band is a solid rectangle: the number that
    matters is the band's own height, not the cumulative top (which on a
    normalized stack is just 100 in every column).
    """
    x_data = np.asarray(x, dtype=float)
    bottoms = np.asarray(bottoms, dtype=float)
    values = np.asarray(values, dtype=float)

    for i in select_indices(annotation.which, len(x_data)):
        val = float(values[i])
        if not np.isfinite(val) or val <= 0:
            continue

        ax.text(
            x_data[i],
            bottoms[i] + val / 2,
            format_value(annotation, val),
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
