"""Human-readable line and arrow styles → matplotlib equivalents.

YAML should read like English, so `dashed` beats `(0, (8, 4))` in a config
file. Anything unrecognized passes through untouched, which keeps raw
matplotlib values working for callers who want them.
"""

from __future__ import annotations

LINESTYLE_MAP = {
    "solid": "-",
    "dashed": (0, (8, 4)),
    "dotted": ":",
    "dashdot": "-.",
    "loosely_dashed": (0, (10, 8)),
    "densely_dashed": (0, (6, 2)),
    "loosely_dotted": (0, (1, 6)),
    "densely_dotted": (0, (1, 1)),
    "dashdotdot": (0, (6, 3, 1, 3, 1, 3)),
    "none": "",
}

# Friendly names for the arrow heads on a change bracket.
ARROWSTYLE_MAP = {
    "double": "<->",
    "both": "<->",
    "start": "<-",
    "from": "<-",
    "end": "->",
    "to": "->",
    "line": "-",
    "plain": "-",
    "none": "-",
    "bar": "|-|",
    "bracket": "|-|",
    "double_filled": "<|-|>",
    "start_filled": "<|-",
    "end_filled": "-|>",
}

# Arrow styles whose heads are sized with head_width / head_length.
_HEAD_SIZED = frozenset({"->", "<-", "<->", "-|>", "<|-", "<|-|>"})
# Arrow styles whose end caps are sized with widthA / widthB.
_BAR_SIZED = frozenset({"|-|"})


def resolve_linestyle(style):
    """Resolve a linestyle name, dash pattern, or raw matplotlib value.

    Accepts ``"dashed"``, a YAML dash pattern like ``[6, 3]`` (on/off lengths),
    an explicit ``[0, [6, 3]]`` offset form, or any matplotlib linestyle.
    """
    if style is None:
        return None

    if isinstance(style, (list, tuple)):
        seq = list(style)
        # (offset, (on, off, ...)) — already in matplotlib's own form
        if len(seq) == 2 and isinstance(seq[1], (list, tuple)):
            return (seq[0], tuple(seq[1]))
        return (0, tuple(seq))

    return LINESTYLE_MAP.get(style, style)


def resolve_arrowstyle(style, *, head_width=None, head_length=None):
    """Resolve an arrow style name and apply head sizing where supported.

    Sizing is skipped for styles that don't accept it (a plain ``-`` has no
    head) and for styles the caller already parameterized by hand.
    """
    resolved = ARROWSTYLE_MAP.get(style, style)

    if "," in resolved:  # caller supplied their own parameters
        return resolved

    params = []
    if resolved in _HEAD_SIZED:
        if head_width is not None:
            params.append(f"head_width={head_width}")
        if head_length is not None:
            params.append(f"head_length={head_length}")
    elif resolved in _BAR_SIZED and head_width is not None:
        params.append(f"widthA={head_width}")
        params.append(f"widthB={head_width}")

    return f"{resolved},{','.join(params)}" if params else resolved
