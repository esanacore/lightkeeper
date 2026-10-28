"""Turn a 1-bit panel bitmap into P6 PPM bytes for a screen, tinted for the theme.

The desktop window (FR-018) shows the real panel pixels: the bitmap
`render_bitmap` draws, enlarged by a whole number with nearest-neighbour
sampling, so every panel pixel becomes a square block of screen pixels and
nothing is smoothed. A fractional zoom would have to blend neighbours, so it
is refused. Tk reads PPM from memory, so no image library is needed (ADR-0005).

Two tints, both from assets/brand/tokens.json: Paper and Ink by day, and Night
paper and Night ink in dark mode, so the window is never the brightest thing at
the bedside. A tint changes only the two colors, never which pixels are ink.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lightkeeper.infrastructure.epaper_bitmap import Bitmap

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


@dataclass(frozen=True)
class Tint:
    """The two colors a 1-bit bitmap is shown in, each as `#RRGGBB`."""

    paper: str
    ink: str

    def __post_init__(self) -> None:
        """Refuse anything but `#RRGGBB`, so a typo fails here and not as a wrong color."""
        for name, value in (("paper", self.paper), ("ink", self.ink)):
            if not _HEX.fullmatch(value):
                raise ValueError(f"{name} must be a color written #RRGGBB, got {value!r}")


# Paper and Ink (color.paper.light, color.ink.light).
LIGHT = Tint(paper="#E6E5DF", ink="#15171C")
# Night paper and Night ink (color.night-paper, color.night-ink).
DARK = Tint(paper="#1C1E22", ink="#B9B7AE")


def to_ppm(bitmap: Bitmap, zoom: int, tint: Tint = LIGHT) -> bytes:
    """Return `bitmap` as binary PPM (P6), each pixel a `zoom` x `zoom` block in `tint`.

    Paper pixels get `tint.paper` and ink pixels `tint.ink`. Raises ValueError
    for a zoom that is not a whole number of 1 or more.
    """
    if isinstance(zoom, bool) or not isinstance(zoom, int) or zoom < 1:
        raise ValueError(f"zoom must be a whole number of 1 or more, got {zoom!r}")
    big = bitmap.scaled(zoom)
    paper = bytes.fromhex(tint.paper[1:])
    ink = bytes.fromhex(tint.ink[1:])
    rgb = bytearray(3 * len(big.ink))
    for channel in range(3):
        # A pixel is ink when it is not 0, as Bitmap.is_ink reads it.
        table = bytes([paper[channel]]) + bytes([ink[channel]]) * 255
        rgb[channel::3] = big.ink.translate(table)
    header = f"P6\n{big.width} {big.height}\n255\n".encode("ascii")
    return header + bytes(rgb)
