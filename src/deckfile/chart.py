from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

import numpy as np

from .branding import Branding
from .series import (
    AnnotationRequest,
    BarSeries,
    ChangeRequest,
    ComboGroup,
    ComboItem,
    LineSeries,
    ProjectionScenario,
    SeparatorRequest,
    StackedAreaGroup,
    StackedBarGroup,
    XGroup,
    XGroupRequest,
)
from .theme import Theme

Number = Union[int, float]
ArrayLike = Union[Sequence[Number], np.ndarray]


def _group_label(value) -> str:
    """Stringify a group value. A whole float prints as `2025`, not `2025.0`."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _resolve_x_groups(groups) -> list[XGroup]:
    """Normalize the two accepted `x_groups` forms into spans.

    Either one value per tick — runs of the same value collapse into a single
    span, blanks are dropped — or explicit ``(label, start, end)`` triples.
    """
    resolved: list[XGroup] = []
    items = list(groups or [])
    if not items:
        return resolved

    if isinstance(items[0], (tuple, list)):
        for item in items:
            label, start, end = item
            resolved.append(
                XGroup(label=_group_label(label), start=float(start), end=float(end))
            )
        return resolved

    values = [_group_label(v) for v in items]
    i = 0
    while i < len(values):
        if not values[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        resolved.append(XGroup(label=values[i], start=float(i), end=float(j)))
        i = j + 1
    return resolved


class Chart:
    """Builder-pattern chart constructor.

    Usage::

        chart = Chart(title="Monthly Calls", subtitle="May 2025 - Feb 2026")
        chart.bar(x=range(10), y=values)
        chart.x_labels(months)
        chart.y_format("K", step=10)
        chart.save("chart.png")
    """

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        theme: Optional[Theme] = None,
        branding: Optional[Branding] = None,
        figsize: Optional[tuple[float, float]] = None,
    ):
        self._title = title
        self._subtitle = subtitle
        self._theme = theme or Theme.default()
        self._branding = branding or Branding.none()
        self._figsize = figsize
        self._series: list = []
        self._annotations: list[AnnotationRequest] = []
        self._changes: list[ChangeRequest] = []
        self._separators: list[SeparatorRequest] = []
        self._x_labels: Optional[list[str]] = None
        self._x_label_fontsize: Optional[float] = None
        self._x_groups: Optional[XGroupRequest] = None
        self._y_format: Optional[str] = None
        self._y_locator_step: Optional[float] = None
        self._y_hidden: bool = False
        self._y_lim: Optional[tuple[Optional[float], Optional[float]]] = None
        self._x_lim: Optional[tuple[Optional[float], Optional[float]]] = None
        self._legend_loc: str = "upper left"
        self._legend_enabled: Optional[bool] = None
        self._fig = None
        self._ax = None
        self._ax2 = None
        self._y_format_right: Optional[str] = None
        self._y_locator_step_right: Optional[float] = None
        self._y_hidden_right: bool = False
        self._y_lim_right: Optional[tuple[Optional[float], Optional[float]]] = None
        self._y_axis_label: Optional[str] = None
        self._y_axis_label_right: Optional[str] = None
        self._x_axis_label: Optional[str] = None

    # ─── Data Methods ───────────────────────────────────────────────

    def bar(
        self,
        x: ArrayLike,
        y: ArrayLike,
        *,
        color: Optional[str] = None,
        alpha: Optional[float] = None,
        width: Optional[float] = None,
        label: Optional[str] = None,
        zorder: int = 3,
        corner_radius: Optional[float] = None,
    ) -> Chart:
        """Add a bar series.

        Args:
            corner_radius: Round the top corners. Fraction of the bar's
                half-width (0 = square, 1 = semicircular cap). Defaults to the
                theme's ``bar_corner_radius``.
        """
        self._series.append(BarSeries(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            color=color,
            alpha=alpha,
            width=width,
            label=label,
            zorder=zorder,
            corner_radius=corner_radius,
        ))
        return self

    def stacked_bar(
        self,
        x: ArrayLike,
        layers: dict[str, ArrayLike],
        *,
        colors: Optional[dict[str, str]] = None,
        alphas: Optional[dict[str, float]] = None,
        width: Optional[float] = None,
        corner_radius: Optional[float] = None,
        normalize: bool = False,
    ) -> Chart:
        """Add a stacked bar group.

        Args:
            x: Category positions.
            layers: Ordered dict of {label: values}. Bottom-to-top stacking.
            colors: Optional per-label color overrides.
            alphas: Optional per-label alpha overrides.
            corner_radius: Round the top corners of each stack. Fraction of the
                bar's half-width (0 = square, 1 = semicircular cap). Only the
                topmost non-zero segment in each column is rounded. Defaults to
                the theme's ``bar_corner_radius``.
            normalize: Normalize to 100% stacked.
        """
        self._series.append(StackedBarGroup(
            x=np.asarray(x, dtype=float),
            layers={k: np.asarray(v, dtype=float) for k, v in layers.items()},
            colors=colors or {},
            alphas=alphas or {},
            width=width,
            corner_radius=corner_radius,
            normalize=normalize,
        ))
        return self

    def stacked_area(
        self,
        x: ArrayLike,
        layers: dict[str, ArrayLike],
        *,
        colors: Optional[dict[str, str]] = None,
        alphas: Optional[dict[str, float]] = None,
        smooth: bool = True,
        markers: bool = True,
        normalize: bool = False,
    ) -> Chart:
        """Add a stacked area group.

        Args:
            x: X positions.
            layers: Ordered dict of {label: values}. Bottom-to-top stacking.
            colors: Optional per-label color overrides.
            alphas: Optional per-label alpha overrides.
            smooth: Apply cubic spline smoothing.
            markers: Show markers at data points.
            normalize: Normalize to 100% stacked.
        """
        self._series.append(StackedAreaGroup(
            x=np.asarray(x, dtype=float),
            layers={k: np.asarray(v, dtype=float) for k, v in layers.items()},
            colors=colors or {},
            alphas=alphas or {},
            smooth=smooth,
            markers=markers,
            normalize=normalize,
        ))
        return self

    def line(
        self,
        x: ArrayLike,
        y: ArrayLike,
        *,
        color: Optional[str] = None,
        label: Optional[str] = None,
        smooth: bool = True,
        glow: bool = True,
        fill: bool = False,
        fill_alpha: Optional[float] = None,
        subtle_bars: bool = False,
        linewidth: Optional[float] = None,
        linestyle: str = "-",
        alpha: float = 1.0,
    ) -> Chart:
        """Add a line series.

        Args:
            smooth: Apply cubic spline interpolation.
            glow: Apply glow path effect around the line.
            fill: Fill area between line and y=0.
            subtle_bars: Draw transparent bars behind the line.
            linestyle: Matplotlib linestyle string.
        """
        self._series.append(LineSeries(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            color=color,
            label=label,
            smooth=smooth,
            glow=glow,
            fill=fill,
            fill_alpha=fill_alpha,
            subtle_bars=subtle_bars,
            linewidth=linewidth,
            linestyle=linestyle,
            alpha=alpha,
        ))
        return self

    def projection(
        self,
        x_historical: ArrayLike,
        y_historical: ArrayLike,
        scenarios: dict[str, ArrayLike],
        x_projected: ArrayLike,
        *,
        historical_color: Optional[str] = None,
        historical_label: Optional[str] = None,
        scenario_colors: Optional[dict[str, str]] = None,
        scenario_styles: Optional[dict[str, str]] = None,
        scenario_linewidths: Optional[dict[str, float]] = None,
        scenario_alphas: Optional[dict[str, float]] = None,
        fill_between: bool = True,
        labels: Optional[dict[str, str]] = None,
    ) -> Chart:
        """Add a multi-scenario projection.

        Historical data is drawn as a solid dark line. Each scenario is a
        separate projection starting from the last historical point.

        Args:
            x_historical: X positions for historical data.
            y_historical: Y values for historical data.
            scenarios: Dict of {name: y_values} for each scenario.
            x_projected: X positions for projected data.
            historical_color: Color for historical line.
            scenario_colors: Per-scenario color overrides.
            scenario_styles: Per-scenario linestyle overrides.
            fill_between: Draw shaded fill between outer scenarios.
            labels: Display label overrides for legend.
        """
        self._series.append(ProjectionScenario(
            x_historical=np.asarray(x_historical, dtype=float),
            y_historical=np.asarray(y_historical, dtype=float),
            scenarios={k: np.asarray(v, dtype=float) for k, v in scenarios.items()},
            x_projected=np.asarray(x_projected, dtype=float),
            historical_color=historical_color,
            historical_label=historical_label,
            scenario_colors=scenario_colors or {},
            scenario_styles=scenario_styles or {},
            scenario_linewidths=scenario_linewidths or {},
            scenario_alphas=scenario_alphas or {},
            fill_between=fill_between,
            labels=labels or {},
        ))
        return self

    def combo(
        self,
        x: ArrayLike,
        items: list[ComboItem],
    ) -> Chart:
        """Add a combo group (bar + line on dual y-axes).

        Args:
            x: X positions shared by all items.
            items: List of ComboItem dataclasses (bar or line, left or right axis).
        """
        self._series.append(ComboGroup(
            x=np.asarray(x, dtype=float),
            items=items,
        ))
        return self

    def y_format_right(
        self,
        style: Optional[str] = None,
        *,
        step: Optional[float] = None,
        hidden: bool = False,
    ) -> Chart:
        """Configure right y-axis formatting.

        Args:
            style: See `y_format`. Optional when `hidden` is set.
            step: Major locator step size.
            hidden: Hide the right y-axis tick labels (grid lines stay).
        """
        self._y_format_right = style
        self._y_locator_step_right = step
        self._y_hidden_right = hidden
        return self

    def y_lim_right(
        self,
        bottom: Optional[float] = None,
        top: Optional[float] = None,
    ) -> Chart:
        """Set right y-axis limits."""
        self._y_lim_right = (bottom, top)
        return self

    def axis_labels(
        self,
        *,
        left: Optional[str] = None,
        right: Optional[str] = None,
        bottom: Optional[str] = None,
    ) -> Chart:
        """Set axis labels (USERS, MESSAGES, MONTH, etc.)."""
        self._y_axis_label = left
        self._y_axis_label_right = right
        self._x_axis_label = bottom
        return self

    # ─── Annotations ────────────────────────────────────────────────

    def annotate_endpoints(
        self,
        *,
        which: str = "first_last",
        format: Optional[str] = None,
        formatter: Optional[Callable[[float], str]] = None,
        halo: bool = True,
        offset: tuple[float, float] = (0, 14),
        series_index: Optional[int] = None,
        layer: Optional[str] = None,
    ) -> Chart:
        """Annotate endpoint values on line or bar series.

        Args:
            which: "first_last", "last", "first", or "all".
            format: Format string with {value} placeholder.
            formatter: Callable that takes a float, returns display string.
            halo: Draw halo circle on the last point.
            offset: Text offset from point in points.
            series_index: Apply only to Nth series (0-based), or all if None.
            layer: Target a specific layer in stacked groups. On a stacked bar
                this labels that band's own value, centered inside the band
                (without it, the column totals are labeled — always 100 on a
                normalized stack). On a stacked area it moves the endpoint onto
                that layer's boundary line. A name that matches no layer in a
                group annotates nothing for that group.
        """
        self._annotations.append(AnnotationRequest(
            kind="endpoints",
            which=which,
            format=format,
            formatter=formatter,
            halo=halo,
            offset=offset,
            series_index=series_index,
            layer=layer,
        ))
        return self

    def annotate_point(
        self,
        x: float,
        y: float,
        text: str,
        *,
        color: Optional[str] = None,
        fontsize: Optional[float] = None,
        fontweight: Optional[str] = None,
        offset: tuple[float, float] = (0, 14),
        ha: str = "center",
        va: str = "bottom",
        dot: bool = False,
        halo: bool = False,
        alpha: float = 1.0,
    ) -> Chart:
        """Annotate a specific point with custom text."""
        self._annotations.append(AnnotationRequest(
            kind="point",
            x=x, y=y, text=text,
            color=color, fontsize=fontsize, fontweight=fontweight,
            offset=offset, ha=ha, va=va,
            dot=dot, halo=halo, alpha=alpha,
        ))
        return self

    def annotate_change(
        self,
        from_x: float,
        to_x: float,
        *,
        from_value: Optional[float] = None,
        to_value: Optional[float] = None,
        series_index: Optional[int] = None,
        layer: Optional[str] = None,
        text: Optional[str] = None,
        mode: str = "percent",
        format: Optional[str] = None,
        at: Optional[float] = None,
        gap: float = 0.5,
        label_position: float = 0.5,
        label_offset: tuple[float, float] = (0, 0),
        color: Optional[str] = None,
        linewidth: Optional[float] = None,
        linestyle: Optional[str] = None,
        alpha: Optional[float] = None,
        zorder: Optional[float] = None,
        guides: Union[bool, str] = True,
        guide_color: Optional[str] = None,
        guide_linewidth: Optional[float] = None,
        guide_linestyle: Optional[str] = None,
        guide_alpha: Optional[float] = None,
        guide_capstyle: Optional[str] = None,
        guide_overhang: Optional[float] = None,
        guide_start_offset: Optional[float] = None,
        arrow: bool = True,
        arrow_style: Optional[str] = None,
        arrow_color: Optional[str] = None,
        arrow_linewidth: Optional[float] = None,
        arrow_linestyle: Optional[str] = None,
        arrow_alpha: Optional[float] = None,
        arrow_scale: Optional[float] = None,
        arrow_head_width: Optional[float] = None,
        arrow_head_length: Optional[float] = None,
        fontsize: Optional[float] = None,
        fontweight: Optional[str] = None,
        fontstyle: Optional[str] = None,
        fontfamily: Optional[str] = None,
        label_color: Optional[str] = None,
        label_alpha: Optional[float] = None,
        label_rotation: Optional[float] = None,
        label_ha: str = "center",
        label_va: str = "center",
        box: bool = True,
        box_style: Optional[str] = None,
        box_pad: Optional[float] = None,
        box_rounding: Optional[float] = None,
        box_facecolor: Optional[str] = None,
        box_edgecolor: Optional[str] = None,
        box_linewidth: Optional[float] = None,
        box_linestyle: Optional[str] = None,
        box_alpha: Optional[float] = None,
    ) -> Chart:
        """Bracket the change between two x positions.

        Draws a horizontal guide at each value, a double-headed arrow spanning
        them, and a boxed label with the change — the "we cut this by 75%"
        callout on an otherwise ordinary bar or line chart.

        Args:
            from_x: X position of the starting value. Negative counts back from
                the end of the series (-1 = last point).
            to_x: X position of the ending value. Negative counts back too.
            from_value: Override the value read from the data at ``from_x``.
            to_value: Override the value read from the data at ``to_x``.
            series_index: Read values from the Nth series (0-based). Defaults
                to the first series on the chart.
            layer: Read a specific layer of a stacked group (or a scenario of a
                projection, or a named item of a combo) instead of the total.
            text: Literal label, bypassing the computed change.
            mode: "percent" (default), "absolute", or "multiple". Percent and
                multiple fall back to the absolute delta when the starting
                value is zero.
            format: Format string overriding `mode`. Placeholders: {percent},
                {delta}, {delta_k}, {delta_m}, {multiple}, {start}, {end}.
            at: X position of the arrow. Defaults to `gap` past the rightmost
                of the two points, which puts it clear of the bars.
            gap: Distance from the rightmost point when `at` is not given.
            label_position: Where the label sits along the arrow, 0 (at
                `from_value`) to 1 (at `to_value`).
            label_offset: Extra label offset in points.
            color: Color for the whole bracket. The `guide_color`,
                `arrow_color`, and `label_color` arguments override it per
                element; everything unset falls back to the theme.
            linewidth: Line width for the whole bracket, overridable per
                element the same way.
            linestyle: "solid", "dashed", "dotted", "dashdot", their
                loosely_/densely_ variants, a dash pattern like (6, 3), or any
                matplotlib linestyle. Overridable per element.
            alpha: Opacity for the whole bracket, overridable per element.
            zorder: Draw order. The label sits one step above this.
            guides: Which horizontal guides to draw — True, False, "from",
                "to", or "both".
            guide_capstyle: "butt", "round", or "projecting".
            guide_overhang: How far the guides run past the arrow, in x-data
                units.
            guide_start_offset: Where a guide starts relative to its point.
                Defaults to the bar's half-width, so it clears the bar.
            arrow: Draw the arrow.
            arrow_style: "double" (default), "start", "end", "line", "bar",
                "double_filled", "start_filled", "end_filled", or any
                matplotlib arrowstyle.
            arrow_scale: Arrow head scale (matplotlib's mutation_scale).
            arrow_head_width: Head width, ignored by styles without heads. On
                the "bar" style it sets the cap width.
            arrow_head_length: Head length, ignored by styles without heads.
            fontstyle: "normal", "italic", or "oblique".
            fontfamily: Font family for the label.
            label_rotation: Label rotation in degrees.
            label_ha: Label horizontal alignment against the arrow.
            label_va: Label vertical alignment against the arrow.
            box: Draw the box around the label.
            box_style: "square" (default), "round", "round4", "sawtooth",
                "roundtooth", "circle", "larrow", "rarrow", or "darrow".
            box_pad: Padding inside the box.
            box_rounding: Corner radius for "round"/"round4", or tooth size for
                the tooth styles.
            box_facecolor: Box fill. Defaults to the chart background, which is
                what lets the label sit on top of the arrow.
            box_edgecolor: Box border color. Defaults to the label color.
        """
        self._changes.append(ChangeRequest(
            from_x=from_x,
            to_x=to_x,
            from_value=from_value,
            to_value=to_value,
            series_index=series_index,
            layer=layer,
            text=text,
            mode=mode,
            format=format,
            at=at,
            gap=gap,
            label_position=label_position,
            label_offset=label_offset,
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            alpha=alpha,
            zorder=zorder,
            guides=guides,
            guide_color=guide_color,
            guide_linewidth=guide_linewidth,
            guide_linestyle=guide_linestyle,
            guide_alpha=guide_alpha,
            guide_capstyle=guide_capstyle,
            guide_overhang=guide_overhang,
            guide_start_offset=guide_start_offset,
            arrow=arrow,
            arrow_style=arrow_style,
            arrow_color=arrow_color,
            arrow_linewidth=arrow_linewidth,
            arrow_linestyle=arrow_linestyle,
            arrow_alpha=arrow_alpha,
            arrow_scale=arrow_scale,
            arrow_head_width=arrow_head_width,
            arrow_head_length=arrow_head_length,
            fontsize=fontsize,
            fontweight=fontweight,
            fontstyle=fontstyle,
            fontfamily=fontfamily,
            label_color=label_color,
            label_alpha=label_alpha,
            label_rotation=label_rotation,
            label_ha=label_ha,
            label_va=label_va,
            box=box,
            box_style=box_style,
            box_pad=box_pad,
            box_rounding=box_rounding,
            box_facecolor=box_facecolor,
            box_edgecolor=box_edgecolor,
            box_linewidth=box_linewidth,
            box_linestyle=box_linestyle,
            box_alpha=box_alpha,
        ))
        return self

    def separators(
        self,
        positions: list[float],
        *,
        color: Optional[str] = None,
        linewidth: Optional[float] = None,
        alpha: Optional[float] = None,
    ) -> Chart:
        """Add vertical separator lines at specified x positions."""
        for pos in positions:
            self._separators.append(SeparatorRequest(
                x=pos, color=color, linewidth=linewidth, alpha=alpha,
            ))
        return self

    def auto_separators(
        self,
        labels: list[str],
        trigger: str = "Jan",
    ) -> Chart:
        """Add separators where a label starts with the trigger text.

        Useful for year boundaries in monthly data.
        """
        for i, label in enumerate(labels):
            if label.startswith(trigger) and i > 0:
                self._separators.append(SeparatorRequest(x=i - 0.5))
        return self

    # ─── Axis Configuration ─────────────────────────────────────────

    def x_labels(
        self,
        labels: list[str],
        *,
        fontsize: Optional[float] = None,
    ) -> Chart:
        """Set explicit x-axis tick labels."""
        self._x_labels = labels
        self._x_label_fontsize = fontsize
        return self

    def x_groups(
        self,
        groups: Sequence,
        *,
        fontsize: Optional[float] = None,
        color: Optional[str] = None,
        weight: Optional[str] = None,
        rule: bool = True,
        rule_color: Optional[str] = None,
        rule_linewidth: Optional[float] = None,
        rule_alpha: Optional[float] = None,
        inset: Optional[float] = None,
        pad: Optional[float] = None,
        gap: Optional[float] = None,
    ) -> Chart:
        """Add a second tier of x-axis labels under the tick labels.

        Turns a flat axis into a grouped one — ``Q1 Q2 Q3 Q4`` ticks with a
        ``2025`` label bracketing them::

            chart.x_labels(["Q1", "Q2", "Q3", "Q4", "Q1", "Q2"])
            chart.x_groups(["2025", "2025", "2025", "2025", "2026", "2026"])

        Args:
            groups: Either one value per tick — consecutive equal values
                collapse into one spanning label, and blank values are skipped
                — or explicit ``(label, start, end)`` triples, where start and
                end are x positions (tick indices).
            rule: Draw the horizontal rule bracketing each group.
            inset: Trim each end of the rule by this fraction of a tick band,
                so neighbouring groups read as separate brackets.
            pad: Points between the tick labels and the rule.
            gap: Points between the rule and the group label.
        """
        self._x_groups = XGroupRequest(
            groups=_resolve_x_groups(groups),
            fontsize=fontsize,
            color=color,
            weight=weight,
            rule=rule,
            rule_color=rule_color,
            rule_linewidth=rule_linewidth,
            rule_alpha=rule_alpha,
            inset=inset,
            pad=pad,
            gap=gap,
        )
        return self

    def y_format(
        self,
        style: Optional[str] = None,
        *,
        step: Optional[float] = None,
        hidden: bool = False,
    ) -> Chart:
        """Configure y-axis formatting.

        Args:
            style: "K", "M", "$K", "$M", "$K_raw", "$M_raw", "%", "number".
                Optional when `hidden` is set.
            step: Major locator step size.
            hidden: Hide the y-axis tick labels. Ticks, grid lines and limits
                are unaffected — only the numbers are dropped.
        """
        self._y_format = style
        self._y_locator_step = step
        self._y_hidden = hidden
        return self

    def y_lim(
        self,
        bottom: Optional[float] = None,
        top: Optional[float] = None,
    ) -> Chart:
        """Set y-axis limits."""
        self._y_lim = (bottom, top)
        return self

    def x_lim(
        self,
        left: Optional[float] = None,
        right: Optional[float] = None,
    ) -> Chart:
        """Set x-axis limits."""
        self._x_lim = (left, right)
        return self

    def legend(
        self,
        *,
        loc: str = "upper left",
        enabled: bool = True,
    ) -> Chart:
        """Configure legend behavior."""
        self._legend_loc = loc
        self._legend_enabled = enabled
        return self

    # ─── Output ─────────────────────────────────────────────────────

    def render(self) -> tuple:
        """Render and return (fig, ax) for further matplotlib customization."""
        from .renderers.base import build_figure

        self._fig, self._ax = build_figure(self)
        return self._fig, self._ax

    def save(
        self,
        path: str,
        *,
        dpi: Optional[int] = None,
        transparent: bool = False,
    ) -> Chart:
        """Render and save to file. Format inferred from extension."""
        if self._fig is None:
            self.render()
        from .output import save_figure

        save_figure(self._fig, path, self._theme, dpi=dpi, transparent=transparent)
        return self

    def show(self) -> Chart:
        """Render and display interactively."""
        if self._fig is None:
            self.render()
        import matplotlib.pyplot as plt

        plt.show()
        return self

    def close(self) -> None:
        """Close the figure and free memory."""
        if self._fig is not None:
            import matplotlib.pyplot as plt

            plt.close(self._fig)
            self._fig = None
            self._ax = None
