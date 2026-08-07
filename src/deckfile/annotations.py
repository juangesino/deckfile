from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .linestyles import resolve_arrowstyle, resolve_linestyle

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from .series import (
        AnnotationRequest,
        BarSeries,
        ChangeRequest,
        LineSeries,
        SeparatorRequest,
        XGroupRequest,
    )
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


def format_change(change: ChangeRequest, from_value: float, to_value: float) -> str:
    """Build the label text for a change bracket.

    Percent and multiple are undefined when the starting value is zero, so both
    fall back to the absolute delta rather than printing a meaningless number.
    """
    delta = to_value - from_value
    ratio_ok = from_value != 0
    percent = (delta / abs(from_value) * 100) if ratio_ok else float("nan")
    multiple = (to_value / from_value) if ratio_ok else float("nan")

    fmt = change.format
    if fmt is None:
        if change.mode == "multiple" and ratio_ok:
            fmt = "{multiple:,.1f}x"
        elif change.mode == "percent" and ratio_ok:
            fmt = "{percent:+,.0f}%"
        else:
            fmt = "{delta:+,.0f}"

    return fmt.format(
        percent=percent,
        delta=delta,
        delta_k=delta / 1000,
        delta_m=delta / 1_000_000,
        multiple=multiple,
        start=from_value,
        end=to_value,
        from_value=from_value,
        to_value=to_value,
    )


def _first(*values):
    """First non-None value — the styling precedence chain.

    Ordered most specific first: the annotation's per-element field, then its
    master field, then the theme's per-element field, then the theme's master.
    """
    for value in values:
        if value is not None:
            return value
    return None


def _guide_sides(guides) -> tuple[bool, bool]:
    """Resolve the `guides` flag to (draw_from, draw_to)."""
    if guides is True:
        return True, True
    if guides is False or guides is None:
        return False, False
    normalized = str(guides).lower()
    if normalized in ("none", "neither", "off"):
        return False, False
    if normalized in ("from", "start", "first"):
        return True, False
    if normalized in ("to", "end", "last"):
        return False, True
    return True, True


def _box_style(style: str, pad: float, rounding: float | None) -> str:
    """Assemble a matplotlib boxstyle string from its parts."""
    if "," in style:  # caller supplied their own parameters
        return style

    parts = [style, f"pad={pad}"]
    if rounding is not None:
        if style in ("round", "round4"):
            parts.append(f"rounding_size={rounding}")
        elif style in ("sawtooth", "roundtooth"):
            parts.append(f"tooth_size={rounding}")
    return ",".join(parts)


def render_change(
    ax: Axes,
    change: ChangeRequest,
    theme: Theme,
    *,
    from_x: float,
    to_x: float,
    from_value: float,
    to_value: float,
    arrow_x: float,
    bar_half_width: float = 0.0,
) -> None:
    """Draw a delta bracket: two guides, a span arrow, and a boxed label."""
    color = _first(change.color, theme.change_color)
    linewidth = _first(change.linewidth, theme.change_linewidth)
    linestyle = _first(change.linestyle, theme.change_linestyle)
    alpha = _first(change.alpha, theme.change_alpha)
    zorder = _first(change.zorder, theme.change_zorder)

    draw_from, draw_to = _guide_sides(change.guides)
    if draw_from or draw_to:
        overhang = _first(change.guide_overhang, theme.change_guide_overhang)
        inset = _first(change.guide_start_offset, bar_half_width)
        guide_kwargs = dict(
            color=_first(change.guide_color, change.color, theme.change_guide_color, color),
            linewidth=_first(
                change.guide_linewidth, change.linewidth,
                theme.change_guide_linewidth, linewidth,
            ),
            linestyle=resolve_linestyle(_first(
                change.guide_linestyle, change.linestyle,
                theme.change_guide_linestyle, linestyle,
            )),
            alpha=_first(change.guide_alpha, change.alpha, theme.change_guide_alpha, alpha),
            solid_capstyle=_first(change.guide_capstyle, theme.change_guide_capstyle),
            zorder=zorder,
        )

        sides = []
        if draw_from:
            sides.append((from_x, from_value))
        if draw_to:
            sides.append((to_x, to_value))

        for x, value in sides:
            # Start at the edge of the bar facing the arrow so the guide never
            # runs across the bar it is measuring.
            if arrow_x >= x:
                start, end = x + inset, arrow_x + overhang
            else:
                start, end = x - inset, arrow_x - overhang
            ax.plot([start, end], [value, value], **guide_kwargs)

    if change.arrow:
        arrowstyle = resolve_arrowstyle(
            _first(change.arrow_style, theme.change_arrow_style),
            head_width=_first(change.arrow_head_width, theme.change_arrow_head_width),
            head_length=_first(change.arrow_head_length, theme.change_arrow_head_length),
        )
        ax.annotate(
            "",
            xy=(arrow_x, to_value),
            xytext=(arrow_x, from_value),
            arrowprops=dict(
                arrowstyle=arrowstyle,
                color=_first(change.arrow_color, change.color, theme.change_arrow_color, color),
                linewidth=_first(
                    change.arrow_linewidth, change.linewidth,
                    theme.change_arrow_linewidth, linewidth,
                ),
                linestyle=resolve_linestyle(_first(
                    change.arrow_linestyle, change.linestyle,
                    theme.change_arrow_linestyle, linestyle,
                )),
                alpha=_first(change.arrow_alpha, change.alpha, theme.change_arrow_alpha, alpha),
                mutation_scale=_first(change.arrow_scale, theme.change_arrow_scale),
                shrinkA=0,
                shrinkB=0,
            ),
            zorder=zorder,
            annotation_clip=False,
        )

    label = change.text if change.text is not None else format_change(
        change, from_value, to_value,
    )
    if not label:
        return

    label_color = _first(change.label_color, change.color, theme.change_label_color, color)

    bbox = None
    if change.box:
        bbox = dict(
            boxstyle=_box_style(
                _first(change.box_style, theme.change_box_style),
                _first(change.box_pad, theme.change_box_pad),
                _first(change.box_rounding, theme.change_box_rounding),
            ),
            facecolor=_first(change.box_facecolor, theme.change_box_facecolor, theme.bg_color),
            edgecolor=_first(change.box_edgecolor, theme.change_box_edgecolor, label_color),
            linewidth=_first(
                change.box_linewidth, change.linewidth,
                theme.change_box_linewidth, linewidth,
            ),
            linestyle=resolve_linestyle(_first(
                change.box_linestyle, theme.change_box_linestyle, "solid",
            )),
            alpha=_first(change.box_alpha, theme.change_box_alpha),
        )

    label_y = from_value + (to_value - from_value) * change.label_position

    ax.annotate(
        label,
        (arrow_x, label_y),
        textcoords="offset points",
        xytext=change.label_offset,
        fontsize=_first(change.fontsize, theme.change_label_size),
        fontweight=_first(change.fontweight, theme.change_label_weight),
        fontstyle=_first(change.fontstyle, theme.change_label_style),
        fontfamily=_first(change.fontfamily, theme.change_label_family, theme.font_family),
        color=label_color,
        alpha=_first(change.label_alpha, change.alpha, theme.change_label_alpha, alpha),
        rotation=_first(change.label_rotation, theme.change_label_rotation),
        rotation_mode="anchor",
        ha=change.label_ha,
        va=change.label_va,
        zorder=zorder + 1,
        bbox=bbox,
        annotation_clip=False,
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


def _tick_label_drop(ax: Axes, theme: Theme) -> float:
    """Points between the axes bottom and the lowest x tick label.

    Measured rather than assumed, so a two-line tick label ("Jan\\n'25") pushes
    the group tier as far down as it needs to go. Falls back to an estimate if
    the backend won't hand us a renderer.
    """
    fig = ax.figure
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        axes_bottom = ax.get_window_extent(renderer).y0
        lowest = axes_bottom
        for label in ax.get_xticklabels():
            if not label.get_text() or not label.get_visible():
                continue
            lowest = min(lowest, label.get_window_extent(renderer).y0)
        drop = (axes_bottom - lowest) / fig.dpi * 72.0
    except Exception:
        drop = 0.0

    if drop > 0:
        return drop
    # No renderer, or nothing to measure: the tick pad plus one line of text.
    return 10.0 + theme.tick_label_size * 1.4


def render_x_groups(
    ax: Axes,
    request: XGroupRequest | None,
    theme: Theme,
) -> None:
    """Render a second tier of x-axis labels below the tick labels.

    Everything is anchored to the bottom of the axes with an offset in points,
    so the tier travels with the axes if the layout shifts, and is drawn
    unclipped — ``bbox_inches="tight"`` grows the saved image to include it.
    """
    if request is None or not request.groups:
        return

    from matplotlib.lines import Line2D
    from matplotlib.transforms import blended_transform_factory, offset_copy

    fig = ax.figure
    pad = request.pad if request.pad is not None else theme.x_group_rule_pad
    gap = request.gap if request.gap is not None else theme.x_group_label_gap
    inset = request.inset if request.inset is not None else theme.x_group_rule_inset

    rule_y = -(_tick_label_drop(ax, theme) + pad)
    label_y = rule_y - (gap if request.rule else 0.0)

    color = request.color or theme.x_group_label_color or theme.subtle_text
    fontsize = request.fontsize or theme.x_group_label_size or theme.tick_label_size
    weight = request.weight or theme.x_group_label_weight
    rule_color = request.rule_color or theme.x_group_rule_color or theme.separator
    rule_linewidth = (
        request.rule_linewidth
        if request.rule_linewidth is not None
        else theme.x_group_rule_linewidth
    )
    rule_alpha = (
        request.rule_alpha
        if request.rule_alpha is not None
        else theme.x_group_rule_alpha
    )

    # x in data coordinates, y pinned to the bottom of the axes.
    base = blended_transform_factory(ax.transData, ax.transAxes)
    rule_transform = offset_copy(base, fig=fig, y=rule_y, units="points")

    for group in request.groups:
        left = group.start - 0.5 + inset
        right = group.end + 0.5 - inset

        if request.rule and right > left:
            # add_artist, not ax.plot: the rule is decoration and must not
            # widen the data limits.
            rule = Line2D(
                [left, right], [0, 0],
                transform=rule_transform,
                color=rule_color,
                linewidth=rule_linewidth,
                alpha=rule_alpha,
                solid_capstyle="butt",
                zorder=4,
            )
            rule.set_clip_on(False)
            ax.add_artist(rule)

        ax.annotate(
            group.label,
            xy=((group.start + group.end) / 2, 0),
            xycoords=base,
            textcoords="offset points",
            xytext=(0, label_y),
            ha="center",
            va="top",
            fontsize=fontsize,
            fontweight=weight,
            color=color,
            annotation_clip=False,
        )
