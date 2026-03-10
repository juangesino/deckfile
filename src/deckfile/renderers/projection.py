from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.patheffects as pe
import numpy as np
from matplotlib.lines import Line2D

from ..interpolation import smooth_curve

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..series import ProjectionScenario
    from ..theme import Theme


# Default linestyle assignment: last scenario gets dashed, rest solid
_DEFAULT_DASHED = (0, (8, 4))


def render_projection(
    ax: Axes,
    proj: ProjectionScenario,
    theme: Theme,
    *,
    palette_index: int = 0,
) -> None:
    scenario_names = list(proj.scenarios.keys())
    n_scenarios = len(scenario_names)

    # ── Historical line ──
    hist_color = proj.historical_color or theme.text_color
    hist_label = proj.historical_label or "Actual"

    x_hist = np.asarray(proj.x_historical, dtype=float)
    y_hist = np.asarray(proj.y_historical, dtype=float)
    x_hist_s, y_hist_s = smooth_curve(x_hist, y_hist, theme.smooth_points, theme.spline_degree)

    ax.plot(
        x_hist_s, y_hist_s,
        color=hist_color,
        linewidth=theme.line_width - 0.5,
        zorder=5,
        path_effects=[pe.withStroke(linewidth=theme.glow_width - 2, foreground=hist_color, alpha=0.08)],
    )

    # ── Scenario lines ──
    # Auto-assign colors from palette if not provided
    default_colors = {}
    for i, name in enumerate(scenario_names):
        default_colors[name] = theme.palette[i % len(theme.palette)]

    # Auto-assign linestyles: last in list gets dashed
    default_styles: dict[str, object] = {}
    for i, name in enumerate(scenario_names):
        if i == n_scenarios - 1 and n_scenarios > 1:
            default_styles[name] = _DEFAULT_DASHED
        else:
            default_styles[name] = "-"

    # Auto-assign linewidths: first=thickest, decreasing
    default_widths: dict[str, float] = {}
    for i, name in enumerate(scenario_names):
        default_widths[name] = max(theme.line_width - i * 0.3, 1.5)

    # Build projection x-axis (overlap with last historical point for continuity)
    x_proj = np.asarray(proj.x_projected, dtype=float)

    smoothed_scenarios: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name in scenario_names:
        scenario_y = np.asarray(proj.scenarios[name], dtype=float)

        # Ensure continuity: prepend last historical point if x_proj
        # doesn't already start at that position
        if len(x_proj) > 0 and x_proj[0] == x_hist[-1]:
            # x_proj already includes the overlap point
            x_vals = x_proj
            y_vals = np.concatenate([[y_hist[-1]], scenario_y[1:]]) if len(scenario_y) == len(x_proj) else scenario_y
        else:
            # Prepend overlap point for continuity
            x_vals = np.concatenate([[x_hist[-1]], x_proj])
            y_vals = np.concatenate([[y_hist[-1]], scenario_y])

        x_s, y_s = smooth_curve(x_vals, y_vals, theme.smooth_points, theme.spline_degree)
        smoothed_scenarios[name] = (x_s, y_s)

    # Fill between outermost scenarios
    if proj.fill_between and n_scenarios >= 2:
        first_name = scenario_names[0]
        last_name = scenario_names[-1]
        x_s_first, y_s_first = smoothed_scenarios[first_name]
        x_s_last, y_s_last = smoothed_scenarios[last_name]
        ax.fill_between(x_s_first, y_s_last, y_s_first, color=theme.brand, alpha=0.06, linewidth=0)

        # If there's a middle scenario, fill between middle and first
        if n_scenarios >= 3:
            mid_name = scenario_names[n_scenarios // 2]
            _, y_s_mid = smoothed_scenarios[mid_name]
            ax.fill_between(x_s_first, y_s_first, y_s_mid, color=theme.brand, alpha=0.05, linewidth=0)

    # Draw scenario lines
    for name in scenario_names:
        color = proj.scenario_colors.get(name, default_colors[name])
        style = proj.scenario_styles.get(name, default_styles[name])
        lw = proj.scenario_linewidths.get(name, default_widths[name])
        alpha = proj.scenario_alphas.get(name, 1.0 if style == "-" else 0.85)
        display_label = proj.labels.get(name, name)

        x_s, y_s = smoothed_scenarios[name]

        path_effects = []
        if style == "-":
            path_effects = [pe.withStroke(linewidth=lw + 4, foreground=color, alpha=theme.glow_alpha)]

        ax.plot(
            x_s, y_s,
            color=color,
            linewidth=lw,
            linestyle=style,
            alpha=alpha,
            zorder=5,
            path_effects=path_effects if path_effects else None,
        )

    # ── Build legend handles ──
    handles = [
        Line2D([0], [0], color=hist_color, linewidth=theme.line_width - 0.5, label=hist_label),
    ]
    for name in scenario_names:
        color = proj.scenario_colors.get(name, default_colors[name])
        style = proj.scenario_styles.get(name, default_styles[name])
        lw = proj.scenario_linewidths.get(name, default_widths[name])
        alpha = proj.scenario_alphas.get(name, 1.0 if style == "-" else 0.85)
        display_label = proj.labels.get(name, name)
        handles.append(
            Line2D([0], [0], color=color, linewidth=lw, linestyle=style, alpha=alpha, label=display_label)
        )

    # Store handles on ax for the legend builder to pick up
    if not hasattr(ax, "_deckfile_legend_handles"):
        ax._deckfile_legend_handles = []
    ax._deckfile_legend_handles.extend(handles)
