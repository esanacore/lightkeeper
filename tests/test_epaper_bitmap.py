"""FR-007 groundwork: every display state rasterizes cleanly for a 2.9" e-paper panel.

The SPI driver waits for hardware (GAP-001); these tests pin everything up
to the bytes it will send.
"""

import json
import struct
import zlib
from pathlib import Path

import pytest

from lightkeeper.infrastructure import epaper_bitmap as eb
from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT, GLYPH_WIDTH, covered, glyph

VECTORS = json.loads((Path(__file__).parent.parent / "spec" / "display_vectors.json").read_text())[
    "cases"
]


def ink_rows(bitmap):
    """Indexes of rows that contain any ink."""
    return [
        y for y in range(bitmap.height) if any(bitmap.is_ink(x, y) for x in range(bitmap.width))
    ]


def test_fr007_font_covers_printable_ascii_in_a_fixed_grid():
    assert covered() == frozenset(chr(c) for c in range(32, 127))
    for char in covered():
        rows = glyph(char)
        assert len(rows) == GLYPH_HEIGHT, char
        assert all(len(r) == GLYPH_WIDTH and set(r) <= {".", "#"} for r in rows), char


def test_fr007_unknown_characters_draw_as_a_question_mark_not_a_blank():
    assert glyph("é") == glyph("?")
    assert glyph("\n") == glyph("?")


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr007_every_vector_fits_the_panel_with_real_glyphs(case):
    lines = case["lines"]
    assert all(char in covered() for line in lines for char in line)
    margin = max(4, round(eb.DEFAULT_HEIGHT * 0.06))
    usable = eb.DEFAULT_WIDTH - 2 * margin
    head = eb.fit_scale(lines[:1], usable, eb.HEADLINE_MAX_SCALE)
    assert eb.text_width(lines[0], head) <= usable
    if lines[1:]:
        body = eb.fit_scale(lines[1:], usable, eb.BODY_MAX_SCALE)
        assert body >= 2, "body text never drops to the smallest size"
        assert all(eb.text_width(line, body) <= usable for line in lines[1:])

    bitmap = eb.render_bitmap(lines)
    # Nothing touches the panel edge: the margin is clear on every side.
    for y in range(bitmap.height):
        for x in list(range(margin)) + list(range(bitmap.width - margin, bitmap.width)):
            assert not bitmap.is_ink(x, y)
    for x in range(bitmap.width):
        for y in list(range(margin)) + list(range(bitmap.height - margin, bitmap.height)):
            assert not bitmap.is_ink(x, y)


def test_fr007_a_long_headline_is_drawn_taller_than_the_body():
    stale = next(c for c in VECTORS if c["name"] == "stale_at_16_minutes")["lines"]
    bitmap = eb.render_bitmap(stale)
    rows = ink_rows(bitmap)
    # The first run of inked rows is the headline.
    head_end = next(i for i in range(len(rows) - 1) if rows[i + 1] != rows[i] + 1)
    head_height = rows[head_end] - rows[0] + 1
    # Body letters at scale 2 are at most 16 px including descenders.
    assert head_height > 16


def test_fr007_png_preview_is_a_valid_1_bit_image():
    bitmap = eb.render_bitmap(["IN RANGE", "112 mg/dL ->", "3 min ago"])
    png = bitmap.to_png()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    length, kind = struct.unpack(">I4s", png[8:16])
    width, height, depth, color = struct.unpack(">IIBB", png[16:26])
    assert (kind, length, width, height, depth, color) == (b"IHDR", 13, 296, 128, 1, 0)
    idat = png.index(b"IDAT")
    size = struct.unpack(">I", png[idat - 4 : idat])[0]
    raw = zlib.decompress(png[idat + 4 : idat + 4 + size])
    stride = 1 + (296 + 7) // 8
    assert len(raw) == stride * 128
    # In PNG grayscale 0 is black: find one inked pixel and check its bit.
    x, y = next((x, y) for y in range(128) for x in range(296) if bitmap.is_ink(x, y))
    byte = raw[y * stride + 1 + x // 8]
    assert not byte & (0x80 >> (x % 8))
    assert png.endswith(b"IEND\xaeB`\x82")


def test_fr007_epd_buffer_matches_the_waveshare_portrait_layout():
    bitmap = eb.Bitmap(296, 128)
    bitmap.fill(0, 0, 1, 1)  # top-left of the landscape image
    buffer = bitmap.to_epd_buffer()
    assert len(buffer) == 128 * 296 // 8
    # Rotated 90 degrees counterclockwise, the landscape top-left lands at the
    # bottom-left of the portrait panel: row 295, column 0. 0 bits are black.
    row_bytes = 128 // 8
    black = [i for i, b in enumerate(buffer) if b != 0xFF]
    assert black == [295 * row_bytes]
    assert buffer[295 * row_bytes] == 0x7F


def test_fr007_blank_bitmap_is_all_white_in_the_epd_buffer():
    assert set(eb.Bitmap(296, 128).to_epd_buffer()) == {0xFF}


def test_fr007_fill_is_clipped_to_the_panel():
    bitmap = eb.Bitmap(120, 70)
    bitmap.fill(-5, -5, 500, 500)
    assert all(bitmap.ink)


def test_fr007_fit_scale_falls_back_to_the_smallest_size():
    assert eb.fit_scale(["x" * 200], 100, 4) == 1
    assert eb.text_width("", 3) == 0


def test_fr007_headline_only_screen_renders():
    bitmap = eb.render_bitmap(["NO DATA"])
    assert ink_rows(bitmap)


@pytest.mark.parametrize(
    ("lines", "width", "height"), [([], 296, 128), (["X"], 99, 128), (["X"], 296, 59)]
)
def test_fr007_rejects_bad_input(lines, width, height):
    with pytest.raises(ValueError):
        eb.render_bitmap(lines, width, height)


def test_fr007_bitmap_can_wrap_existing_pixels():
    bitmap = eb.Bitmap(2, 2, bytearray([1, 0, 0, 1]))
    assert [bitmap.is_ink(x, y) for y in range(2) for x in range(2)] == [True, False, False, True]
