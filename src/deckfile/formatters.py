from __future__ import annotations

import matplotlib.ticker as mticker


_FORMATTERS = {
    "K": lambda v, _: f"{v / 1000:,.1f}M" if abs(v) >= 1000 else f"{v:,.0f}K",
    "M": lambda v, _: f"{v:,.1f}M",
    "$K": lambda v, _: f"${v / 1000:,.1f}M" if abs(v) >= 1000 else f"${v:,.0f}K",
    "$M": lambda v, _: f"${v:,.0f}M",
    "$K_raw": lambda v, _: f"${v / 1e3:,.0f}K",
    "$M_raw": lambda v, _: f"${v / 1e6:,.1f}M",
    "K_raw": lambda v, _: f"{v / 1e3:,.0f}k",
    "%": lambda v, _: f"{v:.0f}%",
    "number": lambda v, _: f"{v:,.0f}",
}


def get_formatter(style: str) -> mticker.FuncFormatter:
    """Return a y-axis FuncFormatter for the given style string.

    Styles:
        "K"      — 1,234K (values already in thousands)
        "M"      — 1.2M   (values already in millions)
        "$K"     — $1,234K (values already in thousands)
        "$M"     — $1,234M (values already in millions)
        "$K_raw" — $1,234K (divide raw values by 1e3)
        "$M_raw" — $1.2M   (divide raw values by 1e6)
        "%"      — 45%
        "number" — 1,234
    """
    if style not in _FORMATTERS:
        raise ValueError(
            f"Unknown y_format '{style}'. "
            f"Choose from: {', '.join(_FORMATTERS.keys())}"
        )
    return mticker.FuncFormatter(_FORMATTERS[style])
