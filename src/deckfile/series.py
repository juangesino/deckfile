from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np


@dataclass
class BarSeries:
    x: np.ndarray
    y: np.ndarray
    color: Optional[str] = None
    alpha: Optional[float] = None
    width: Optional[float] = None
    label: Optional[str] = None
    zorder: int = 3
    corner_radius: Optional[float] = None


@dataclass
class StackedBarGroup:
    x: np.ndarray
    layers: dict[str, np.ndarray]
    colors: dict[str, str] = field(default_factory=dict)
    alphas: dict[str, float] = field(default_factory=dict)
    width: Optional[float] = None
    corner_radius: Optional[float] = None
    normalize: bool = False  # True → 100% stacked (each column sums to 100)


@dataclass
class StackedAreaGroup:
    x: np.ndarray
    layers: dict[str, np.ndarray]  # {label: values}, bottom-to-top
    colors: dict[str, str] = field(default_factory=dict)
    alphas: dict[str, float] = field(default_factory=dict)
    smooth: bool = True
    markers: bool = True
    normalize: bool = False  # True → 100% stacked (each x sums to 100)


@dataclass
class LineSeries:
    x: np.ndarray
    y: np.ndarray
    color: Optional[str] = None
    label: Optional[str] = None
    smooth: bool = True
    glow: bool = True
    fill: bool = False
    fill_alpha: Optional[float] = None
    subtle_bars: bool = False
    linewidth: Optional[float] = None
    linestyle: str = "-"
    alpha: float = 1.0


@dataclass
class ProjectionScenario:
    x_historical: np.ndarray
    y_historical: np.ndarray
    scenarios: dict[str, np.ndarray]
    x_projected: np.ndarray
    historical_color: Optional[str] = None
    historical_label: Optional[str] = None
    scenario_colors: dict[str, str] = field(default_factory=dict)
    scenario_styles: dict[str, str] = field(default_factory=dict)
    scenario_linewidths: dict[str, float] = field(default_factory=dict)
    scenario_alphas: dict[str, float] = field(default_factory=dict)
    fill_between: bool = True
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ComboItem:
    values: np.ndarray
    series_type: str           # "bar" or "line"
    axis: str = "left"         # "left" or "right"
    label: Optional[str] = None
    color: Optional[str] = None
    label_format: Optional[str] = None  # e.g. "{value:,.0f}" or "{value_k:,.1f}k"


@dataclass
class ComboGroup:
    x: np.ndarray
    items: list[ComboItem]


@dataclass
class AnnotationRequest:
    kind: str  # "endpoints" or "point"
    # For "endpoints":
    which: str = "first_last"
    format: Optional[str] = None
    formatter: Optional[Callable[[float], str]] = None
    halo: bool = True
    offset: tuple[float, float] = (0, 14)
    series_index: Optional[int] = None
    layer: Optional[str] = None  # target a specific layer in stacked groups
    # For "point":
    x: Optional[float] = None
    y: Optional[float] = None
    text: Optional[str] = None
    color: Optional[str] = None
    fontsize: Optional[float] = None
    fontweight: Optional[str] = None
    ha: str = "center"
    va: str = "bottom"
    dot: bool = False
    alpha: float = 1.0


@dataclass
class ChangeRequest:
    """A period-over-period delta bracket between two x positions.

    Draws horizontal guides at both values, a double-headed arrow spanning
    them, and a boxed label with the change (percent by default).

    Every styling field is optional and falls back to the theme. The master
    fields (``color``, ``linewidth``, ``linestyle``, ``alpha``) set all three
    elements at once; the per-element fields below override them.
    """

    # ── What is measured ──
    from_x: float
    to_x: float
    from_value: Optional[float] = None
    to_value: Optional[float] = None
    series_index: Optional[int] = None
    layer: Optional[str] = None

    # ── What the label says ──
    text: Optional[str] = None
    mode: str = "percent"  # "percent" | "absolute" | "multiple"
    format: Optional[str] = None

    # ── Where it sits ──
    at: Optional[float] = None  # explicit x for the arrow; default: right of both
    gap: float = 0.5            # distance from the rightmost point when `at` is None
    label_position: float = 0.5  # 0 = from_value, 1 = to_value
    label_offset: tuple[float, float] = (0, 0)

    # ── Master styling ──
    color: Optional[str] = None
    linewidth: Optional[float] = None
    linestyle: Optional[str] = None
    alpha: Optional[float] = None
    zorder: Optional[float] = None

    # ── Guides ──
    guides: bool | str = True  # True | False | "from" | "to" | "both" | "none"
    guide_color: Optional[str] = None
    guide_linewidth: Optional[float] = None
    guide_linestyle: Optional[str] = None
    guide_alpha: Optional[float] = None
    guide_capstyle: Optional[str] = None
    guide_overhang: Optional[float] = None
    guide_start_offset: Optional[float] = None  # None → the bar's half-width

    # ── Arrow ──
    arrow: bool = True
    arrow_style: Optional[str] = None
    arrow_color: Optional[str] = None
    arrow_linewidth: Optional[float] = None
    arrow_linestyle: Optional[str] = None
    arrow_alpha: Optional[float] = None
    arrow_scale: Optional[float] = None
    arrow_head_width: Optional[float] = None
    arrow_head_length: Optional[float] = None

    # ── Label ──
    fontsize: Optional[float] = None
    fontweight: Optional[str] = None
    fontstyle: Optional[str] = None
    fontfamily: Optional[str] = None
    label_color: Optional[str] = None
    label_alpha: Optional[float] = None
    label_rotation: Optional[float] = None
    label_ha: str = "center"
    label_va: str = "center"

    # ── Label box ──
    box: bool = True
    box_style: Optional[str] = None
    box_pad: Optional[float] = None
    box_rounding: Optional[float] = None
    box_facecolor: Optional[str] = None
    box_edgecolor: Optional[str] = None
    box_linewidth: Optional[float] = None
    box_linestyle: Optional[str] = None
    box_alpha: Optional[float] = None


@dataclass
class SeparatorRequest:
    x: float
    color: Optional[str] = None
    linewidth: Optional[float] = None
    alpha: Optional[float] = None


@dataclass
class XGroup:
    """One second-tier x-axis label spanning the ticks from ``start`` to ``end``."""

    label: str
    start: float
    end: float


@dataclass
class XGroupRequest:
    """A second tier of x-axis labels drawn under the tick labels.

    Each group prints its label centered under the run of ticks it spans, with
    an optional horizontal rule bracketing that run — the "Q1 Q2 Q3 Q4 / 2025"
    axis. ``None`` on any style field means "inherit from the theme".
    """

    groups: list[XGroup]
    fontsize: Optional[float] = None
    color: Optional[str] = None
    weight: Optional[str] = None
    rule: bool = True
    rule_color: Optional[str] = None
    rule_linewidth: Optional[float] = None
    rule_alpha: Optional[float] = None
    # Shrinks each rule inward from the edge of its band, in x-data units, so
    # adjacent groups read as separate brackets instead of one long line.
    inset: Optional[float] = None
    # Vertical spacing, in points: `pad` below the tick labels to the rule,
    # `gap` below the rule to the group label.
    pad: Optional[float] = None
    gap: Optional[float] = None
