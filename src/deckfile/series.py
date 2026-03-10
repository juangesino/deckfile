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


@dataclass
class StackedBarGroup:
    x: np.ndarray
    layers: dict[str, np.ndarray]
    colors: dict[str, str] = field(default_factory=dict)
    alphas: dict[str, float] = field(default_factory=dict)
    width: Optional[float] = None


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
class SeparatorRequest:
    x: float
    color: Optional[str] = None
    linewidth: Optional[float] = None
    alpha: Optional[float] = None
