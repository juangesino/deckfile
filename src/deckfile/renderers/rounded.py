from __future__ import annotations

import types
from typing import TYPE_CHECKING, Iterable

import numpy as np
from matplotlib.path import Path as MplPath
from matplotlib.transforms import IdentityTransform

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.patches import Rectangle

# Bezier constant for approximating a quarter circle with a cubic curve.
_KAPPA = 0.5522847498307936


def _rounded_rect_path(
    xl: float,
    xr: float,
    yb: float,
    yt: float,
    radius: float,
    *,
    round_top: bool = True,
    round_bottom: bool = False,
) -> MplPath:
    """Build a rectangle path with optionally rounded top and/or bottom corners.

    Corners are circular arcs of ``radius`` (same units as the coordinates),
    approximated with cubic Beziers. ``xl``/``xr`` are the left/right edges,
    ``yb``/``yt`` the bottom/top.
    """
    r = max(0.0, radius)
    k = r * _KAPPA

    verts: list[tuple[float, float]] = []
    codes: list[int] = []

    M, L, C = MplPath.MOVETO, MplPath.LINETO, MplPath.CURVE4

    # Start at bottom-left (inset if the bottom is rounded).
    if round_bottom and r > 0:
        verts.append((xl, yb + r)); codes.append(M)
    else:
        verts.append((xl, yb)); codes.append(M)

    # Up the left side and across the top.
    if round_top and r > 0:
        verts.append((xl, yt - r)); codes.append(L)
        # top-left corner: (xl, yt-r) -> (xl+r, yt)
        verts.append((xl, yt - r + k)); codes.append(C)
        verts.append((xl + r - k, yt)); codes.append(C)
        verts.append((xl + r, yt)); codes.append(C)
        verts.append((xr - r, yt)); codes.append(L)
        # top-right corner: (xr-r, yt) -> (xr, yt-r)
        verts.append((xr - r + k, yt)); codes.append(C)
        verts.append((xr, yt - r + k)); codes.append(C)
        verts.append((xr, yt - r)); codes.append(C)
    else:
        verts.append((xl, yt)); codes.append(L)
        verts.append((xr, yt)); codes.append(L)

    # Down the right side and across the bottom.
    if round_bottom and r > 0:
        verts.append((xr, yb + r)); codes.append(L)
        # bottom-right corner: (xr, yb+r) -> (xr-r, yb)
        verts.append((xr, yb + r - k)); codes.append(C)
        verts.append((xr - r + k, yb)); codes.append(C)
        verts.append((xr - r, yb)); codes.append(C)
        verts.append((xl + r, yb)); codes.append(L)
        # bottom-left corner: (xl+r, yb) -> (xl, yb+r)
        verts.append((xl + r - k, yb)); codes.append(C)
        verts.append((xl, yb + r - k)); codes.append(C)
        verts.append((xl, yb + r)); codes.append(C)
    else:
        verts.append((xr, yb)); codes.append(L)
        verts.append((xl, yb)); codes.append(L)

    verts.append(verts[0]); codes.append(MplPath.CLOSEPOLY)
    return MplPath(np.array(verts, dtype=float), codes)


def apply_rounded_top_clip(
    ax: Axes,
    rects: Iterable[Rectangle],
    x_left: float,
    x_right: float,
    y_top: float,
    radius_frac: float,
    *,
    y_bottom: float = 0.0,
    round_bottom: bool = False,
) -> None:
    """Clip ``rects`` to a shared rounded-top silhouette.

    All rectangles are clipped to a single rounded rectangle spanning the column
    (``x_left``..``x_right`` by ``y_bottom``..``y_top``, in data coordinates), so
    a stack of segments reads as one bar with rounded top corners. The bars stay
    visible and labelled, so autoscale and the legend are unaffected.

    The clip path is recomputed in display space at draw time, after the axes
    limits are final, which keeps the corners visually circular regardless of the
    x/y scale difference. ``radius_frac`` is a fraction of the bar's half-width
    (0 = square, 1 = radius equal to half the bar width).
    """
    geom = (float(x_left), float(x_right), float(y_bottom), float(y_top))
    for rect in rects:
        _wrap_rect_clip(ax, rect, geom, radius_frac, round_bottom)


def _wrap_rect_clip(ax, rect, geom, radius_frac, round_bottom) -> None:
    if getattr(rect, "_deckfile_rounded", False):
        return
    rect._deckfile_rounded = True
    orig_draw = rect.draw

    def _draw(self, renderer, *args, **kwargs):
        xl_d, xr_d, yb_d, yt_d = geom
        p0 = ax.transData.transform((xl_d, yb_d))
        p1 = ax.transData.transform((xr_d, yt_d))
        xl, yb = float(p0[0]), float(p0[1])
        xr, yt = float(p1[0]), float(p1[1])
        if xr < xl:
            xl, xr = xr, xl
        if yt < yb:
            yb, yt = yt, yb
        width = xr - xl
        height = yt - yb
        radius = radius_frac * (width / 2.0)
        radius = max(0.0, min(radius, height, width / 2.0))
        path = _rounded_rect_path(
            xl, xr, yb, yt, radius,
            round_top=True,
            round_bottom=round_bottom,
        )
        self.set_clip_path(path, IdentityTransform())
        orig_draw(renderer, *args, **kwargs)

    rect.draw = types.MethodType(_draw, rect)
