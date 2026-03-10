from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

import numpy as np

from .branding import Branding
from .series import (
    AnnotationRequest,
    BarSeries,
    ComboGroup,
    ComboItem,
    LineSeries,
    ProjectionScenario,
    SeparatorRequest,
    StackedAreaGroup,
    StackedBarGroup,
)
from .theme import Theme

Number = Union[int, float]
ArrayLike = Union[Sequence[Number], np.ndarray]


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
        self._separators: list[SeparatorRequest] = []
        self._x_labels: Optional[list[str]] = None
        self._x_label_fontsize: Optional[float] = None
        self._y_format: Optional[str] = None
        self._y_locator_step: Optional[float] = None
        self._y_lim: Optional[tuple[Optional[float], Optional[float]]] = None
        self._x_lim: Optional[tuple[Optional[float], Optional[float]]] = None
        self._legend_loc: str = "upper left"
        self._legend_enabled: Optional[bool] = None
        self._fig = None
        self._ax = None
        self._ax2 = None
        self._y_format_right: Optional[str] = None
        self._y_locator_step_right: Optional[float] = None
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
    ) -> Chart:
        """Add a bar series."""
        self._series.append(BarSeries(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            color=color,
            alpha=alpha,
            width=width,
            label=label,
            zorder=zorder,
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
    ) -> Chart:
        """Add a stacked bar group.

        Args:
            x: Category positions.
            layers: Ordered dict of {label: values}. Bottom-to-top stacking.
            colors: Optional per-label color overrides.
            alphas: Optional per-label alpha overrides.
        """
        self._series.append(StackedBarGroup(
            x=np.asarray(x, dtype=float),
            layers={k: np.asarray(v, dtype=float) for k, v in layers.items()},
            colors=colors or {},
            alphas=alphas or {},
            width=width,
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
        style: str,
        *,
        step: Optional[float] = None,
    ) -> Chart:
        """Configure right y-axis formatting."""
        self._y_format_right = style
        self._y_locator_step_right = step
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
            layer: Target a specific layer in stacked groups.
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

    def y_format(
        self,
        style: str,
        *,
        step: Optional[float] = None,
    ) -> Chart:
        """Configure y-axis formatting.

        Args:
            style: "K", "M", "$K", "$M", "$K_raw", "$M_raw", "%", "number".
            step: Major locator step size.
        """
        self._y_format = style
        self._y_locator_step = step
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
