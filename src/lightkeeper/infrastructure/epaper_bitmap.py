"""Draw rendered display lines as a 1-bit bitmap for an e-paper panel.

The groundwork for the Raspberry Pi display (FR-007): everything except the
SPI driver, which waits for the hardware. The layout follows `svg_display`:
a large headline, then the other lines spread evenly below it, each line
shrunk until it fits the panel width. Glyphs come from the project's own
5x7 font, scaled by whole numbers so every pixel stays crisp on e-ink.

Pure standard library (ADR-0005). Two outputs: a PNG for previews and tests,
and a packed buffer in the byte layout Waveshare's 2.9" driver sends to the
panel. The buffer layout follows Waveshare's published `getbuffer` and has
not been checked on a physical panel yet (GAP-001).
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT, GLYPH_WIDTH, glyph

# Waveshare 2.9" panel, in landscape (how the lines read).
DEFAULT_WIDTH = 296
DEFAULT_HEIGHT = 128

HEADLINE_MAX_SCALE = 4
BODY_MAX_SCALE = 3


@dataclass
class Bitmap:
    """A 1-bit image: `ink[y * width + x]` is 1 where the panel is black."""

    width: int
    height: int
    ink: bytearray = field(default_factory=bytearray)

    def __post_init__(self) -> None:
        """Start blank (all paper) unless pixels were given."""
        if not self.ink:
            self.ink = bytearray(self.width * self.height)

    def is_ink(self, x: int, y: int) -> bool:
        """Report whether pixel (x, y) is black."""
        return bool(self.ink[y * self.width + x])

    def fill(self, x: int, y: int, w: int, h: int) -> None:
        """Ink a rectangle, clipped to the panel."""
        for row in range(max(0, y), min(self.height, y + h)):
            start = row * self.width
            for col in range(max(0, x), min(self.width, x + w)):
                self.ink[start + col] = 1

    def to_png(self) -> bytes:
        """Encode as a 1-bit grayscale PNG (black ink on white paper)."""
        raw = bytearray()
        for row in _packed_rows(self, white_is_one=True):
            raw.append(0)  # PNG filter type: none
            raw.extend(row)

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        header = struct.pack(">IIBBBBB", self.width, self.height, 1, 0, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )

    def to_epd_buffer(self) -> bytes:
        """Pack for the panel's native portrait orientation, 1 = white, MSB first.

        Matches Waveshare's `getbuffer` for a landscape image: rotate 90
        degrees counterclockwise, then pack each row to whole bytes.
        """
        rotated = Bitmap(self.height, self.width)
        for y in range(self.height):
            for x in range(self.width):
                if self.is_ink(x, y):
                    rotated.ink[(self.width - 1 - x) * rotated.width + y] = 1
        return b"".join(_packed_rows(rotated, white_is_one=True))


def _packed_rows(bitmap: Bitmap, white_is_one: bool) -> list[bytes]:
    """Each row as bytes, eight pixels per byte, most significant bit first."""
    rows = []
    for y in range(bitmap.height):
        row = bytearray((bitmap.width + 7) // 8)
        for x in range(bitmap.width):
            white = not bitmap.is_ink(x, y)
            if white == white_is_one:
                row[x // 8] |= 0x80 >> (x % 8)
        rows.append(bytes(row))
    return rows


def _gap(scale: int) -> int:
    """Space between characters: at least one pixel, wider at large sizes."""
    return max(1, scale // 2)


def text_width(text: str, scale: int) -> int:
    """Width in pixels of `text` drawn at `scale`."""
    if not text:
        return 0
    return len(text) * GLYPH_WIDTH * scale + (len(text) - 1) * _gap(scale)


def fit_scale(lines: list[str], usable_width: int, max_scale: int) -> int:
    """Largest whole-number scale (up to `max_scale`) at which every line fits."""
    for scale in range(max_scale, 1, -1):
        if all(text_width(line, scale) <= usable_width for line in lines):
            return scale
    return 1


def draw_text(bitmap: Bitmap, text: str, x: int, y: int, scale: int, tall: int = 0) -> None:
    """Draw `text` with its top-left corner at (x, y).

    `tall`, when larger than `scale`, stretches the glyphs vertically: a long
    headline narrowed to fit the width keeps the height that marks it as the
    headline.
    """
    sy = max(scale, tall)
    for char in text:
        for row, cells in enumerate(glyph(char)):
            for col, cell in enumerate(cells):
                if cell == "#":
                    bitmap.fill(x + col * scale, y + row * sy, scale, sy)
        x += GLYPH_WIDTH * scale + _gap(scale)


def render_bitmap(
    lines: list[str], width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> Bitmap:
    """Return a bitmap showing `lines` the way the panel should."""
    if width < 100 or height < 60:
        raise ValueError("panel must be at least 100x60 pixels")
    if not lines:
        raise ValueError("nothing to draw: lines is empty")

    margin = max(4, round(height * 0.06))
    usable_width = width - 2 * margin
    headline = lines[0]
    body = lines[1:]

    head_scale = fit_scale([headline], usable_width, HEADLINE_MAX_SCALE)
    # A headline squeezed narrower than the largest size is drawn one step
    # taller, so STALE - DO NOT TRUST never looks weaker than IN RANGE.
    head_tall = min(HEADLINE_MAX_SCALE, head_scale + 1)
    body_scale = fit_scale(body, usable_width, BODY_MAX_SCALE) if body else 1

    bitmap = Bitmap(width, height)
    draw_text(bitmap, headline, margin, margin, head_scale, tall=head_tall)

    # Spread the body lines evenly over the space below the headline, each
    # centered in its slot, the same way svg_display does.
    top = margin + GLYPH_HEIGHT * head_tall
    slot = (height - top - margin) / max(len(body), 1)
    line_height = GLYPH_HEIGHT * body_scale
    for index, line in enumerate(body):
        y = round(top + slot * index + (slot - line_height) / 2)
        draw_text(bitmap, line, margin, y, body_scale)
    return bitmap
