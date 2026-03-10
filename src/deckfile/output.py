from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from .theme import Theme


def save_figure(
    fig: Figure,
    path: str,
    theme: Theme,
    *,
    dpi: Optional[int] = None,
    transparent: bool = False,
) -> None:
    """Save figure to file. Format auto-detected from extension."""
    p = Path(path)
    ext = p.suffix.lower()

    save_kwargs = {
        "facecolor": "none" if transparent else theme.bg_color,
        "bbox_inches": "tight",
        "pad_inches": theme.pad_inches,
    }

    if ext in (".png", ".jpg", ".jpeg"):
        save_kwargs["dpi"] = dpi or theme.dpi

    fig.savefig(str(p), **save_kwargs)
