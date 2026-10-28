"""FR-018, NFR-005: the desktop window's PPM is the panel's own pixels, whole-number zoomed.

Every panel pixel becomes a square block in one of two token colors: Paper
and Ink by day, Night paper and Night ink in dark mode. Nothing is blended,
so a fractional zoom is refused.
"""

import json
from pathlib import Path

import pytest

from lightkeeper.infrastructure.epaper_bitmap import Bitmap, render_bitmap, stamp_text
from lightkeeper.infrastructure.ppm import DARK, LIGHT, Tint, to_ppm
from tests.helpers import NOW
from tests.test_vectors import VECTORS

ROOT = Path(__file__).resolve().parent.parent
COLOR = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))[
    "color"
]

PAPER = bytes.fromhex("E6E5DF")
INK = bytes.fromhex("15171C")
NIGHT_PAPER = bytes.fromhex("1C1E22")
NIGHT_INK = bytes.fromhex("B9B7AE")


def decode_ppm(data):
    """Return (width, height, rgb bytes) of a P6 file with a three-line header."""
    magic, size, depth, pixels = data.split(b"\n", 3)
    assert (magic, depth) == (b"P6", b"255")
    width, height = (int(part) for part in size.split(b" "))
    assert len(pixels) == 3 * width * height
    return width, height, pixels


def checker():
    """Return a 2x2 bitmap: ink top-left and bottom-right, paper elsewhere."""
    return Bitmap(2, 2, bytearray([1, 0, 0, 1]))


def test_fr018_ppm_bytes_for_a_two_by_two_bitmap_are_exact():
    assert to_ppm(checker(), 1) == b"P6\n2 2\n255\n" + INK + PAPER + PAPER + INK


def test_fr018_ppm_zoom_makes_every_pixel_a_square_block():
    rows = [INK * 2 + PAPER * 2] * 2 + [PAPER * 2 + INK * 2] * 2
    assert to_ppm(checker(), 2) == b"P6\n4 4\n255\n" + b"".join(rows)


def test_fr018_ppm_dark_tint_is_night_paper_and_night_ink():
    assert to_ppm(checker(), 1, DARK) == (
        b"P6\n2 2\n255\n" + NIGHT_INK + NIGHT_PAPER + NIGHT_PAPER + NIGHT_INK
    )


def test_fr018_ppm_light_tint_is_the_default():
    assert to_ppm(checker(), 3) == to_ppm(checker(), 3, LIGHT)


def test_fr018_ppm_reads_any_nonzero_pixel_as_ink():
    """As Bitmap.is_ink does: a pixel is ink when it is not 0."""
    assert to_ppm(Bitmap(2, 1, bytearray([0, 7])), 1) == b"P6\n2 1\n255\n" + PAPER + INK


@pytest.mark.parametrize("zoom", [1.5, 2.0, 0.5, 0, -2, True, "2", None])
def test_fr018_ppm_refuses_a_zoom_that_is_not_a_whole_number(zoom):
    with pytest.raises(ValueError, match="zoom must be a whole number"):
        to_ppm(checker(), zoom)


@pytest.mark.parametrize("zoom", [2, 3])
@pytest.mark.parametrize("case", VECTORS[::7], ids=[c["name"] for c in VECTORS[::7]])
def test_fr018_ppm_shows_exactly_the_panel_pixels(case, zoom):
    """Each zoom x zoom block is one panel pixel, ink where render_bitmap inks."""
    bitmap = render_bitmap(case["lines"], 296, 128, stamp=stamp_text(NOW))
    width, height, pixels = decode_ppm(to_ppm(bitmap, zoom))
    assert (width, height) == (296 * zoom, 128 * zoom)
    stride = 3 * width
    for y in range(bitmap.height):
        row = b"".join((INK if bitmap.is_ink(x, y) else PAPER) * zoom for x in range(296))
        for copy in range(zoom):
            start = (y * zoom + copy) * stride
            assert pixels[start : start + stride] == row, (y, copy)


@pytest.mark.parametrize(
    "paper,ink",
    [("E6E5DF", "#15171C"), ("#E6E5D", "#15171C"), ("#E6E5DF", "#15171G"), ("#E6E5DF", "")],
)
def test_fr018_tint_refuses_a_color_not_written_rrggbb(paper, ink):
    with pytest.raises(ValueError, match="must be a color written #RRGGBB"):
        Tint(paper=paper, ink=ink)


def test_nfr005_ppm_tints_are_the_brand_tokens():
    assert LIGHT == Tint(paper=COLOR["paper"]["light"], ink=COLOR["ink"]["light"])
    assert DARK == Tint(paper=COLOR["night-paper"]["dark"], ink=COLOR["night-ink"]["dark"])
