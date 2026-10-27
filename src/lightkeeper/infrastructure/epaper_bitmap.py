"""Draw rendered display lines as a 1-bit bitmap for an e-paper panel.

The groundwork for the Raspberry Pi display (FR-007): everything except the
SPI driver, which waits for the hardware. `panel_layout` decides where every
line, band and frame goes, in whole pixels; this module draws that plan with
the project's own 5x8 font (Keeper 5x8), scaled by whole numbers so every
pixel stays crisp on e-ink. The same plan, drawn by the JavaScript and C++
ports, must give the pixels `spec/panel_vectors.json` pins, so this file uses
integer arithmetic only.

Pure standard library (ADR-0005). Outputs: a PNG and a 1-bit BMP for
previews, exports and tests, the packed rows the pixel vectors hash, and a
packed buffer in the byte layout Waveshare's 2.9" driver sends to the panel.
The buffer layout follows Waveshare's published `getbuffer` and has not been
checked on a physical panel yet (GAP-001).
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime

from lightkeeper.infrastructure.font5x7 import GLYPH_WIDTH, glyph
from lightkeeper.infrastructure.panel_layout import (
    DASH_OFF,
    DASH_ON,
    DASHED,
    HATCH_PITCH,
    Box,
    PanelPlan,
    PlacedText,
    fit_scale,
    glyph_gap,
    plan_panel,
    text_width,
)

# Waveshare 2.9" panel, in landscape (how the lines read): the default profile.
DEFAULT_WIDTH = 296
DEFAULT_HEIGHT = 128

# fit_scale and text_width moved to panel_layout; they stay importable from here.
__all__ = [
    "DEFAULT_HEIGHT",
    "DEFAULT_WIDTH",
    "Bitmap",
    "draw_plan",
    "draw_text",
    "fit_scale",
    "render_bitmap",
    "stamp_text",
    "text_width",
]

# Each 0/1 pixel byte as the ASCII bit "0" or "1", ink as 1 or paper as 1.
_INK_IS_ONE = bytes(0x30 if value == 0 else 0x31 for value in range(256))
_PAPER_IS_ONE = bytes(0x31 if value == 0 else 0x30 for value in range(256))


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

    def fill(self, x: int, y: int, w: int, h: int, ink: bool = True) -> None:
        """Ink a rectangle (or clear it to paper), clipped to the panel."""
        left, right = max(0, x), min(self.width, x + w)
        if left >= right:
            return
        run = (b"\x01" if ink else b"\x00") * (right - left)
        for row in range(max(0, y), min(self.height, y + h)):
            start = row * self.width
            self.ink[start + left : start + right] = run

    def scaled(self, factor: int) -> Bitmap:
        """Enlarge by a whole number, nearest neighbour: each pixel becomes a square block."""
        if isinstance(factor, bool) or not isinstance(factor, int) or factor < 1:
            raise ValueError(f"scale must be a whole number of 1 or more, got {factor!r}")
        big = Bitmap(self.width * factor, self.height * factor)
        wide = bytearray(big.width)
        for y in range(self.height):
            row = self.ink[y * self.width : (y + 1) * self.width]
            for offset in range(factor):
                wide[offset::factor] = row
            for copy in range(factor):
                start = (y * factor + copy) * big.width
                big.ink[start : start + big.width] = wide
        return big

    def to_packed_rows(self) -> bytes:
        """Pack rows top to bottom, 1 = ink, eight pixels a byte, most significant bit first.

        Each row is padded with paper (0 bits) to a whole byte. The pixel
        vectors hash exactly these bytes with CRC-32.
        """
        return b"".join(_packed_rows(self, white_is_one=False))

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

    def to_bmp(self) -> bytes:
        """Encode as a 1-bit BMP: BITMAPINFOHEADER and a two-colour palette.

        Palette entry 0 is black and 1 is white, so a 1 bit is paper, as in
        the Waveshare buffer. Rows run bottom to top, each padded to 4 bytes.
        """
        stride = (self.width + 31) // 32 * 4
        packed = _packed_rows(self, white_is_one=True)
        pad = bytes(stride - (self.width + 7) // 8)
        pixels = b"".join(row + pad for row in reversed(packed))
        palette = b"\x00\x00\x00\x00" + b"\xff\xff\xff\x00"  # blue, green, red, reserved
        offset = 14 + 40 + len(palette)
        file_header = b"BM" + struct.pack("<IHHI", offset + len(pixels), 0, 0, offset)
        info = struct.pack(
            "<IiiHHIIiiII",
            40,  # header size
            self.width,
            self.height,  # positive: bottom-up rows
            1,  # planes
            1,  # bits per pixel
            0,  # no compression
            len(pixels),
            2835,  # 72 dpi, in pixels per metre
            2835,
            2,  # colours in the palette
            2,  # both matter
        )
        return file_header + info + palette + pixels

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
    """Pack each row as bytes, eight pixels per byte, most significant bit first.

    Padding bits past the last pixel are always 0.
    """
    stride = (bitmap.width + 7) // 8
    table = _PAPER_IS_ONE if white_is_one else _INK_IS_ONE
    pad = b"0" * (stride * 8 - bitmap.width)
    rows = []
    for y in range(bitmap.height):
        bits = bitmap.ink[y * bitmap.width : (y + 1) * bitmap.width].translate(table) + pad
        rows.append(int(bits, 2).to_bytes(stride, "big"))
    return rows


def draw_text(
    bitmap: Bitmap, text: str, x: int, y: int, scale: int, tall: int = 0, ink: bool = True
) -> None:
    """Draw `text` with its top-left corner at (x, y), in ink or (on a band) in paper.

    `tall`, when larger than `scale`, stretches the glyphs vertically: a long
    headline narrowed to fit the width keeps the height that marks it as the
    headline.
    """
    sy = max(scale, tall)
    for char in text:
        for row, cells in enumerate(glyph(char)):
            for col, cell in enumerate(cells):
                if cell == "#":
                    bitmap.fill(x + col * scale, y + row * sy, scale, sy, ink)
        x += GLYPH_WIDTH * scale + glyph_gap(scale)


def _draw_line(bitmap: Bitmap, line: PlacedText, ink: bool = True) -> None:
    draw_text(bitmap, line.text, line.x, line.y, line.scale, line.tall, ink)


def _draw_frame(bitmap: Bitmap, kind: str, box: Box, thickness: int) -> None:
    """Draw a ring `thickness` wide just inside `box`: hatched for STALE, else dashed.

    The hatch inks every pixel where x + y is a multiple of HATCH_PITCH (45
    degree lines). Dashes run DASH_ON pixels on and DASH_OFF off, counted
    from the ring's top-left corner along each side.
    """
    period = DASH_ON + DASH_OFF
    for y in range(box.y, box.y + box.h):
        across = y < box.y + thickness or y >= box.y + box.h - thickness
        columns = (
            range(box.x, box.x + box.w)
            if across
            else [
                *range(box.x, box.x + thickness),
                *range(box.x + box.w - thickness, box.x + box.w),
            ]
        )
        for x in columns:
            if kind == DASHED:
                along = x - box.x if across else y - box.y
                on = along % period < DASH_ON
            else:
                on = (x + y) % HATCH_PITCH == 0
            if on:
                bitmap.ink[y * bitmap.width + x] = 1


def draw_plan(plan: PanelPlan) -> Bitmap:
    """Draw a layout plan: band, headline, rule, strike, lines, stamp, then the frame.

    Only the headline on an ink band clears pixels (its glyphs are paper);
    everything after it only adds ink, so the order is fixed for the ports.
    """
    bitmap = Bitmap(plan.width, plan.height)
    if plan.ink_band is not None:
        band = plan.ink_band
        bitmap.fill(band.x, band.y, band.w, band.h)
    _draw_line(bitmap, plan.headline, ink=plan.ink_band is None)
    for mark in (plan.rule, plan.strike):
        if mark is not None:
            bitmap.fill(mark.x, mark.y, mark.w, mark.h)
    for line in plan.lines:
        _draw_line(bitmap, line)
    if plan.stamp is not None:
        _draw_line(bitmap, plan.stamp)
    if plan.frame is not None:
        _draw_frame(bitmap, plan.frame.kind, plan.frame.box, plan.frame.thickness)
    return bitmap


def render_bitmap(
    lines: list[str],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    stamp: str | None = None,
) -> Bitmap:
    """Return a bitmap showing `lines` the way the panel should.

    `stamp` is opt-in: an `HH:MM` (see `stamp_text`) drawn small at the right
    of the age row, so a panel or exported image that stopped updating shows
    when it was drawn.
    """
    return draw_plan(plan_panel(lines, width, height, stamp))


def stamp_text(moment: datetime) -> str:
    """Return the stamp for an image drawn at `moment`: local 24-hour `HH:MM`.

    This is the time the image was drawn, not the time of the reading: a
    reader compares it with the clock to see that a panel or an exported image
    stopped updating (proposed HAZ-014). How old the reading is stays the age
    line's job. A naive `moment` is taken as local time already.
    """
    return moment.astimezone().strftime("%H:%M")
