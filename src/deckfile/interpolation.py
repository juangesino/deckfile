from __future__ import annotations

import numpy as np
from scipy.interpolate import make_interp_spline


def smooth_curve(
    x: np.ndarray,
    y: np.ndarray,
    num_points: int = 200,
    degree: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Return smoothed (x, y) arrays using cubic spline interpolation.

    Falls back gracefully for small datasets:
    - 1 point: returns as-is
    - 2-3 points: reduces spline degree accordingly
    - 4+ points: uses cubic spline (k=3)
    """
    n = len(x)
    if n <= 1:
        return x.astype(float), y.astype(float)

    k = min(degree, n - 1)
    x_smooth = np.linspace(float(x.min()), float(x.max()), num_points)
    y_smooth = make_interp_spline(x, y, k=k)(x_smooth)
    return x_smooth, y_smooth
