from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Branding:
    """Optional branding elements overlaid on charts."""

    logo_path: Optional[str] = None
    logo_zoom: float = 0.18
    logo_position: tuple[float, float] = (-0.02, 1.22)
    logo_alignment: tuple[float, float] = (1.0, 0.5)

    footer_text: Optional[str] = None
    footer_x: float = 0.89
    footer_y: float = -0.02
    footer_ha: str = "right"
    footer_va: str = "bottom"
    footer_alpha: float = 0.6

    @classmethod
    def none(cls) -> Branding:
        return cls()

    @classmethod
    def with_logo(cls, path: str, **kwargs) -> Branding:
        return cls(logo_path=path, **kwargs)

    @classmethod
    def with_footer(cls, text: str, **kwargs) -> Branding:
        return cls(footer_text=text, **kwargs)
