from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class Theme:
    """Immutable visual configuration for deckfile charts."""

    # ── Colors ──
    brand: str = "#3a58ed"
    bg_color: str = "#ffffff"
    text_color: str = "#1a1a2e"
    grid_color: str = "#e8ebf0"
    subtle_text: str = "#7c859b"
    separator: str = "#dde1e8"

    # Ordered color cycle for multi-series charts
    palette: tuple[str, ...] = (
        "#3a58ed",
        "#6478e8",
        "#94a3d8",
        "#b8c2f8",
        "#0d9488",
        "#d97706",
        "#1a1a2e",
    )
    area_palette: tuple[str, ...] = (
        "#3a58ed",
        "#c0cafc",
        "#0d9488",
        "#d97706",
        "#e85d75",
        "#34d399",
        "#f59e0b",
    )

    # ── Typography ──
    font_family: str = "sans-serif"
    font_sans_serif: tuple[str, ...] = (
        "SF Pro Display",
        "Helvetica Neue",
        "Arial",
        "sans-serif",
    )
    title_size: float = 24.0
    title_weight: str = "bold"
    subtitle_size: float = 12.5
    axis_label_size: float = 10.0
    tick_label_size: float = 9.5
    annotation_size: float = 10.0
    annotation_weight: str = "bold"
    footer_size: float = 8.5

    # ── Layout ──
    figure_width: float = 16.0
    figure_height: float = 8.5
    dpi: int = 200
    margin_left: float = 0.085
    margin_right: float = 0.95
    margin_top: float = 0.84
    margin_bottom: float = 0.10
    title_x: float = 0.085
    title_y: float = 0.95
    subtitle_y: float = 0.905
    pad_inches: float = 0.5

    # ── Grid ──
    grid_linewidth: float = 0.7
    y_grid: bool = True
    x_grid: bool = False

    # ── Line styling ──
    line_width: float = 3.0
    glow_width: float = 8.0
    glow_alpha: float = 0.10

    # ── Bar styling ──
    bar_width: float = 0.55
    bar_alpha: float = 0.7
    # Rounded bar corners. Fraction of the bar's half-width used as the corner
    # radius (0 = square, 1 = semicircular cap). Applies to bar / stacked_bar.
    bar_corner_radius: float = 0.0
    subtle_bar_width: float = 0.45
    subtle_bar_alpha: float = 0.12

    # ── Scatter endpoints ──
    endpoint_size: float = 50.0
    endpoint_edge_width: float = 1.5
    halo_size: float = 160.0
    halo_alpha: float = 0.10

    # ── Fill ──
    fill_alpha: float = 0.07

    # ── Separator ──
    separator_linewidth: float = 0.7
    separator_alpha: float = 0.6

    # ── X-axis group labels (the second tier under the tick labels) ──
    x_group_label_size: Optional[float] = None  # None → tick_label_size
    x_group_label_color: Optional[str] = None  # None → subtle_text
    x_group_label_weight: str = "normal"
    x_group_rule_color: Optional[str] = None  # None → separator
    x_group_rule_linewidth: float = 0.9
    x_group_rule_alpha: float = 1.0
    # Fraction of a tick band trimmed off each end of the rule, so neighbouring
    # groups read as separate brackets.
    x_group_rule_inset: float = 0.15
    # Vertical spacing in points: rule below the tick labels, label below the rule.
    x_group_rule_pad: float = 10.0
    x_group_label_gap: float = 7.0

    # ── Change bracket (period-over-period delta) ──
    # Master styling. Guides, arrow, and label inherit from these unless the
    # more specific parameter below is set (None everywhere means "inherit").
    change_color: str = "#1a1a2e"
    change_linewidth: float = 1.2
    change_linestyle: str = "solid"
    change_alpha: float = 1.0
    change_zorder: float = 9.0

    # Guides — the horizontal lines drawn at each value.
    change_guide_color: Optional[str] = None
    change_guide_linewidth: Optional[float] = None
    change_guide_linestyle: Optional[str] = None
    change_guide_alpha: Optional[float] = None
    change_guide_capstyle: str = "butt"
    # How far the guides run past the arrow, in x-data units.
    change_guide_overhang: float = 0.06

    # Arrow — the span between the two values.
    change_arrow_color: Optional[str] = None
    change_arrow_linewidth: Optional[float] = None
    change_arrow_linestyle: Optional[str] = None
    change_arrow_alpha: Optional[float] = None
    change_arrow_style: str = "double"
    change_arrow_scale: float = 20.0
    change_arrow_head_width: Optional[float] = None
    change_arrow_head_length: Optional[float] = None

    # Label
    change_label_size: float = 11.0
    change_label_weight: str = "bold"
    change_label_style: str = "normal"
    change_label_family: Optional[str] = None
    change_label_color: Optional[str] = None
    change_label_alpha: Optional[float] = None
    change_label_rotation: float = 0.0

    # Label box
    change_box_style: str = "square"
    change_box_pad: float = 0.5
    change_box_rounding: Optional[float] = None
    change_box_facecolor: Optional[str] = None  # None → the chart background
    change_box_edgecolor: Optional[str] = None  # None → the label color
    change_box_linewidth: Optional[float] = None
    change_box_linestyle: Optional[str] = None
    change_box_alpha: Optional[float] = None

    # ── Legend ──
    legend_fontsize: float = 10.5
    legend_frameon: bool = True
    legend_fancybox: bool = True
    legend_borderpad: float = 0.9
    legend_labelspacing: float = 0.65
    legend_handlelength: float = 2.8
    legend_linewidth: float = 0.6
    legend_alpha: float = 0.95

    # ── Interpolation ──
    smooth_points: int = 200
    spline_degree: int = 3

    @classmethod
    def default(cls) -> Theme:
        return cls()

    def replace(self, **kwargs) -> Theme:
        """Return a new Theme with specified fields overridden."""
        current = asdict(self)
        current.update(kwargs)
        return Theme(**current)
