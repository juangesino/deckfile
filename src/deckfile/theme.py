from __future__ import annotations

from dataclasses import dataclass, asdict


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
