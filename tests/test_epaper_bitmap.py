"""FR-007 groundwork: every display state rasterizes cleanly for an e-paper panel.

The SPI driver waits for hardware (GAP-001); these tests pin everything up
to the bytes it will send, at the 2.9" default and at every other profile.
"""

import dataclasses
import json
import struct
import time
import zlib
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from lightkeeper.infrastructure import epaper_bitmap as eb
from lightkeeper.infrastructure import panel_layout as pl
from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT, GLYPH_WIDTH, covered, glyph
from lightkeeper.infrastructure.panel_profiles import PROFILES

VECTORS = json.loads((Path(__file__).parent.parent / "spec" / "display_vectors.json").read_text())[
    "cases"
]
PROFILE_IDS = list(PROFILES)


def ink_rows(bitmap):
    """Indexes of rows that contain any ink."""
    return [
        y for y in range(bitmap.height) if any(bitmap.is_ink(x, y) for x in range(bitmap.width))
    ]


def inside(box, x, y):
    return box.x <= x < box.x + box.w and box.y <= y < box.y + box.h


def text_lines(plan):
    return [plan.headline, *plan.lines, *([plan.stamp] if plan.stamp else [])]


def decode_png(data):
    """(width, height, pixels) of a 1-bit grayscale PNG; pixel 1 = ink (black)."""
    width, height = struct.unpack(">II", data[16:24])
    idat = data.index(b"IDAT")
    size = struct.unpack(">I", data[idat - 4 : idat])[0]
    raw = zlib.decompress(data[idat + 4 : idat + 4 + size])
    stride = 1 + (width + 7) // 8
    pixels = bytearray()
    for y in range(height):
        row = raw[y * stride + 1 : (y + 1) * stride]
        pixels.extend(0 if row[x // 8] & (0x80 >> (x % 8)) else 1 for x in range(width))
    return width, height, pixels


def decode_bmp(data):
    """(width, height, pixels) of a 1-bit BMP with a black-and-white palette; 1 = ink."""
    assert data[:2] == b"BM"
    size, _, _, offset = struct.unpack("<IHHI", data[2:14])
    assert size == len(data)
    header, width, height, planes, bits, compression = struct.unpack("<IiiHHI", data[14:34])
    assert (header, planes, bits, compression) == (40, 1, 1, 0)
    palette = [data[54 + 4 * i : 54 + 4 * i + 3] for i in range(2)]
    black = [entry == b"\x00\x00\x00" for entry in palette]
    assert black == [True, False]
    stride = (width + 31) // 32 * 4
    assert offset + stride * height == len(data)
    pixels = bytearray(width * height)
    for row in range(height):
        y = height - 1 - row  # bottom-up
        line = data[offset + row * stride : offset + (row + 1) * stride]
        for x in range(width):
            index = 1 if line[x // 8] & (0x80 >> (x % 8)) else 0
            pixels[y * width + x] = 1 if black[index] else 0
    return width, height, pixels


# --- Font ----------------------------------------------------------------------


def test_fr007_font_covers_printable_ascii_in_a_fixed_grid():
    assert covered() == frozenset(chr(c) for c in range(32, 127))
    for char in covered():
        rows = glyph(char)
        assert len(rows) == GLYPH_HEIGHT, char
        assert all(len(r) == GLYPH_WIDTH and set(r) <= {".", "#"} for r in rows), char


def test_fr007_unknown_characters_draw_as_a_question_mark_not_a_blank():
    assert glyph("é") == glyph("?")
    assert glyph("\n") == glyph("?")


# --- The default 2.9" panel ----------------------------------------------------


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr007_every_vector_fits_the_panel_with_real_glyphs(case):
    lines = case["lines"]
    assert all(char in covered() for line in lines for char in line)
    plan = pl.plan_panel(lines, eb.DEFAULT_WIDTH, eb.DEFAULT_HEIGHT)
    assert plan.margin == 8
    inner = plan.content.w - 2 * pl.BAND_PAD
    assert plan.headline.width <= inner
    assert plan.headline.scale >= 2
    for line in plan.lines:
        assert line.scale >= 2, "body text never drops to the smallest size"
        assert line.width <= plan.content.w

    bitmap = eb.render_bitmap(lines)
    assert bitmap.ink == eb.draw_plan(plan).ink
    # Nothing touches the panel edge: the outer 2 px are clear on every side,
    # and only a STALE or NO DATA frame enters the rest of the margin.
    for y in range(bitmap.height):
        for x in (0, 1, bitmap.width - 2, bitmap.width - 1):
            assert not bitmap.is_ink(x, y)
    for x in range(bitmap.width):
        for y in (0, 1, bitmap.height - 2, bitmap.height - 1):
            assert not bitmap.is_ink(x, y)


def test_fr007_a_long_headline_is_drawn_taller_than_the_body():
    stale = next(c for c in VECTORS if c["name"] == "stale_at_16_minutes")["lines"]
    plan = pl.plan_panel(stale, eb.DEFAULT_WIDTH, eb.DEFAULT_HEIGHT)
    # Narrowed to fit, then stretched back to the band's full height.
    assert plan.headline.tall > plan.headline.scale
    assert plan.headline.height == GLYPH_HEIGHT * pl.plan_panel(["IN RANGE"], 296, 128).band_scale
    assert all(plan.headline.height > line.height for line in plan.lines)
    bitmap = eb.render_bitmap(stale)
    # Measured in pixels: the inverse band runs down its padded left edge,
    # between paper above it and paper below it.
    x, top = plan.band.x, plan.band.y
    run = 0
    while bitmap.is_ink(x, top + run):
        run += 1
    assert not bitmap.is_ink(x, top - 1)
    assert run == plan.band.h
    # Body letters at scale 3 are at most 24 px including descenders.
    assert run > 24


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
    bitmap.fill(200, 0, 10, 10, ink=False)  # wholly off the panel: nothing happens
    bitmap.fill(0, 0, -3, 10, ink=False)
    assert all(bitmap.ink)
    bitmap.fill(118, 68, 9, 9, ink=False)
    assert [bitmap.is_ink(x, y) for y in (68, 69) for x in (117, 118, 119)] == [
        True,
        False,
        False,
    ] * 2


def test_fr007_fit_scale_falls_back_to_the_smallest_size():
    assert eb.fit_scale(["x" * 200], 100, 4) == 1
    assert eb.text_width("", 3) == 0


def test_fr007_headline_only_screen_renders():
    bitmap = eb.render_bitmap(["NO DATA"])
    assert ink_rows(bitmap)


@pytest.mark.parametrize(
    ("lines", "width", "height"),
    [([], 296, 128), (["X"], 99, 128), (["X"], 296, 59), (["X"], 128, 296), (["X"], 296, 69)],
)
def test_fr007_rejects_bad_input(lines, width, height):
    with pytest.raises(ValueError):
        eb.render_bitmap(lines, width, height)


def test_fr007_bitmap_can_wrap_existing_pixels():
    bitmap = eb.Bitmap(2, 2, bytearray([1, 0, 0, 1]))
    assert [bitmap.is_ink(x, y) for y in range(2) for x in range(2)] == [True, False, False, True]


# --- Every profile -------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_every_vector_fits_inside_margins_at_every_profile(profile):
    size = PROFILES[profile]
    assert_ink_stays_inside_the_margins(size.width, size.height)


# The narrowest panel resolve accepts at a few heights (the margin grows with
# the height, so the narrowest width does too): every line still fits.
@pytest.mark.parametrize(("width", "height"), [(157, 70), (165, 128), (185, 296), (221, 600)])
def test_fr007_narrowest_accepted_sizes_keep_glyph_ink_inside_the_margins(width, height):
    with pytest.raises(ValueError, match="too narrow"):
        pl.plan_panel(["NO DATA"], width - 1, height)
    assert_ink_stays_inside_the_margins(width, height)


def assert_ink_stays_inside_the_margins(width, height):
    """Every vector's text stays in the content box, and the margin holds only the frame."""
    # 1 for every margin pixel; pixels are 0/1 bytes, so big-integer AND masks them.
    edge = pl.margin(height)
    margin = eb.Bitmap(width, height)
    margin.fill(0, 0, width, height)
    margin.fill(edge, edge, width - 2 * edge, height - 2 * edge, ink=False)
    margin_mask = int.from_bytes(margin.ink, "big")
    for case in VECTORS:
        for stamp in (None, "02:14"):
            plan = pl.plan_panel(case["lines"], width, height, stamp)
            for line in text_lines(plan):
                box = line.box
                assert plan.content.x <= box.x and box.x + box.w <= plan.content.x + plan.content.w
                assert plan.content.y <= box.y and box.y + box.h <= plan.content.y + plan.content.h
            assert plan.headline.x + plan.headline.width <= plan.band.x + plan.band.w - pl.BAND_PAD
            bitmap = eb.draw_plan(plan)
            # The margin holds only the frame: the same pixels the frame alone draws.
            frame_only = eb.draw_plan(
                dataclasses.replace(
                    plan,
                    lines=(),
                    stamp=None,
                    ink_band=None,
                    rule=None,
                    strike=None,
                    headline=dataclasses.replace(plan.headline, text=""),
                )
            )
            margin_ink = int.from_bytes(bitmap.ink, "big") & margin_mask
            assert margin_ink == int.from_bytes(frame_only.ink, "big"), case["name"]
            assert (margin_ink != 0) == (plan.frame is not None), case["name"]


@pytest.mark.parametrize(
    "profile", ["waveshare_2in9", "waveshare_4in2", "waveshare_7in5", "kindle"]
)
def test_fr007_body_text_is_scale_2_or_more_at_296x128_and_wider(profile):
    size = PROFILES[profile]
    for case in VECTORS:
        for stamp in (None, "02:14"):
            plan = pl.plan_panel(case["lines"], size.width, size.height, stamp)
            assert all(line.scale >= 2 for line in text_lines(plan)), (profile, case["name"])


# Below 296 px wide, the longest lines only fit at scale 1 until D4 (wrapping
# the headline onto two rows on small panels) is decided. Pinned, so any
# change to which lines drop to scale 1 is seen.
SMALL_PANEL_EXCEPTIONS = {
    "waveshare_1in54": {
        "STALE - DO NOT TRUST",
        "last: 120 mg/dL ->",
        "last: 45 mg/dL v",
        "last: 110 mg/dL ->",
        "time is in the future",
        "Check sensor and phone",
        "Confirm on primary device",
        "Nightscout unreachable",
    },
    "waveshare_2in13": {
        "last: 120 mg/dL ->",
        "last: 45 mg/dL v",
        "last: 110 mg/dL ->",
        "Check sensor and phone",
        "Confirm on primary device",
        "Nightscout unreachable",
    },
}


@pytest.mark.parametrize("profile", sorted(SMALL_PANEL_EXCEPTIONS))
def test_fr007_small_panel_exceptions_are_pinned_pending_d4(profile):
    size = PROFILES[profile]
    for stamp in (None, "02:14"):
        at_scale_1 = set()
        for case in VECTORS:
            plan = pl.plan_panel(case["lines"], size.width, size.height, stamp)
            at_scale_1 |= {line.text for line in text_lines(plan) if line.scale < 2}
            # Even here, the value and the age never drop below 2 on a fresh screen.
            if plan.treatment in pl.FRESH:
                assert all(line.scale >= 2 for line in plan.lines[:2]), case["name"]
        assert at_scale_1 == SMALL_PANEL_EXCEPTIONS[profile], stamp


# --- Stamp ---------------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_haz014_stamp_is_opt_in_fits_and_never_overlaps_ink(profile):
    size = PROFILES[profile]
    placements = set()
    for case in VECTORS:
        lines = case["lines"]
        plain = pl.plan_panel(lines, size.width, size.height)
        assert plain.stamp is None
        assert eb.render_bitmap(lines, size.width, size.height).ink == eb.draw_plan(plain).ink
        plan = pl.plan_panel(lines, size.width, size.height, "02:14")
        stamp = plan.stamp
        assert stamp is not None and stamp.text == "02:14" and stamp.role == pl.STAMP
        assert stamp.scale >= pl.STAMP_MIN_SCALE
        # Right-aligned at the content edge, inside the content box.
        assert stamp.x + stamp.width == plan.content.x + plan.content.w
        assert plan.content.y <= stamp.y
        assert stamp.y + stamp.height <= plan.content.y + plan.content.h
        # Its box never meets another line, the band, or another line's ink.
        for other in [plan.band, *(line.box for line in plan.lines)]:
            apart = (
                other.x + other.w <= stamp.x
                or stamp.x + stamp.width <= other.x
                or other.y + other.h <= stamp.y
                or stamp.y + stamp.height <= other.y
            )
            assert apart, case["name"]
        bitmap = eb.render_bitmap(lines, size.width, size.height, "02:14")
        alone = eb.Bitmap(size.width, size.height)
        eb.draw_text(alone, stamp.text, stamp.x, stamp.y, stamp.scale)
        for y in range(stamp.y, stamp.y + stamp.height):
            for x in range(stamp.x, stamp.x + stamp.width):
                assert bitmap.is_ink(x, y) == alone.is_ink(x, y), case["name"]
        ages = [line for line in plan.lines if line.role == pl.AGE]
        on_age_row = (
            bool(ages) and ages[0].y + ages[0].height >= stamp.y + stamp.height > ages[0].y
        )
        placements.add("age row" if on_age_row else "bottom")
        if on_age_row:
            # Same baseline as the age line.
            base = ages[0].y + pl.CAP_ROWS * ages[0].scale
            assert stamp.y + pl.CAP_ROWS * stamp.scale == base
        else:
            assert stamp.y + stamp.height == plan.content.y + plan.content.h
    assert placements == {"age row", "bottom"}


def test_haz014_stamp_sits_on_the_age_row_when_there_is_room():
    lines = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    plan = pl.plan_panel(lines, 296, 128, "02:14")
    unstamped = pl.plan_panel(lines, 296, 128)
    assert plan.lines == unstamped.lines  # nothing else moves
    assert (plan.stamp.x, plan.stamp.y, plan.stamp.scale) == (234, 95, 2)
    stamped = eb.render_bitmap(lines, 296, 128, "02:14")
    plain = eb.render_bitmap(lines, 296, 128)
    assert stamped.ink != plain.ink
    # The long future-time age line leaves no room, so the stamp goes to the bottom.
    stale = next(c for c in VECTORS if c["name"] == "future_dated")["lines"]
    bottom = pl.plan_panel(stale, 296, 128, "02:14").stamp
    assert (bottom.x, bottom.y) == (234, 104)


def test_haz014_stamp_text_is_local_24_hour_time():
    # A naive time is already local.
    assert eb.stamp_text(datetime(2026, 7, 1, 2, 14)) == "02:14"
    assert eb.stamp_text(datetime(2026, 7, 1, 23, 5, 59)) == "23:05"
    # An aware time is shown in this machine's local zone, as the panel's owner reads it.
    for moment in (
        datetime(2026, 7, 1, 2, 14, tzinfo=UTC),
        datetime(2026, 1, 15, 18, 45, tzinfo=timezone(timedelta(hours=-5))),
    ):
        expected = time.strftime("%H:%M", time.localtime(moment.timestamp()))
        assert eb.stamp_text(moment) == expected
    with pytest.raises(ValueError, match="HH:MM"):
        eb.render_bitmap(["NO DATA"], stamp="2:14")


# --- Encodings -----------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), [(296, 128), (250, 122), (157, 71)])
def test_fr007_bmp_and_png_decode_to_the_same_pixels(width, height):
    lines = next(c for c in VECTORS if c["name"] == "stale_at_16_minutes")["lines"]
    bitmap = eb.render_bitmap(lines, width, height, "13:07")
    assert decode_png(bitmap.to_png()) == (width, height, bitmap.ink)
    assert decode_bmp(bitmap.to_bmp()) == (width, height, bitmap.ink)
    # scaled(2) is exact: every pixel becomes a 2x2 block.
    big = bitmap.scaled(2)
    assert (big.width, big.height) == (2 * width, 2 * height)
    for y in range(big.height):
        for x in range(big.width):
            assert big.is_ink(x, y) == bitmap.is_ink(x // 2, y // 2)
    assert decode_bmp(big.to_bmp()) == (big.width, big.height, big.ink)
    assert bitmap.scaled(1).ink == bitmap.ink


@pytest.mark.parametrize("factor", [0, -1, 2.0, True, "2"])
def test_fr007_scaled_refuses_anything_but_a_whole_number(factor):
    with pytest.raises(ValueError, match="whole number"):
        eb.Bitmap(4, 4).scaled(factor)


def test_fr016_packed_rows_are_ink_bits_msb_first_padded_with_paper():
    bitmap = eb.Bitmap(10, 2)
    bitmap.fill(0, 0, 1, 1)
    bitmap.fill(9, 0, 1, 1)
    bitmap.fill(1, 1, 8, 1)
    assert bitmap.to_packed_rows() == bytes([0b10000000, 0b01000000, 0b01111111, 0b10000000])
    # Any nonzero pixel byte counts as ink, as is_ink says.
    odd = eb.Bitmap(8, 1, bytearray([255, 0, 2, 0, 0, 0, 0, 1]))
    assert odd.to_packed_rows() == bytes([0b10100001])


def test_fr007_inverse_headline_is_paper_on_an_ink_band():
    lines = next(c for c in VECTORS if c["name"] == "urgent_low_55")["lines"]
    plan = pl.plan_panel(lines, 296, 128)
    bitmap = eb.draw_plan(plan)
    head = plan.headline
    # Every glyph cell of the headline is paper, everything else in the band ink.
    letters = eb.Bitmap(296, 128)
    eb.draw_text(letters, head.text, head.x, head.y, head.scale, head.tall)
    band = plan.band
    for y in range(band.y, band.y + band.h):
        for x in range(band.x, band.x + band.w):
            assert bitmap.is_ink(x, y) != letters.is_ink(x, y)


@pytest.mark.parametrize("kind", [pl.STALE, pl.DASHED])
def test_fr007_frames_are_texture_only_in_the_margin(kind):
    name = {pl.STALE: "stale_at_16_minutes", pl.DASHED: "no_data"}[kind]
    lines = next(c for c in VECTORS if c["name"] == name)["lines"]
    plan = pl.plan_panel(lines, 296, 128)
    frame = plan.frame
    assert frame.kind == kind
    assert frame.thickness == (pl.HATCH_WIDTH if kind == pl.STALE else pl.DASH_WIDTH)
    ring = eb.draw_plan(dataclasses.replace(plan, lines=(), ink_band=None, strike=None))
    inset = (plan.margin - frame.thickness) // 2
    assert frame.box == pl.Box(inset, inset, 296 - 2 * inset, 128 - 2 * inset)
    for y in range(128):
        for x in range(296):
            in_ring = inside(frame.box, x, y) and not inside(
                pl.Box(
                    inset + frame.thickness,
                    inset + frame.thickness,
                    296 - 2 * (inset + frame.thickness),
                    128 - 2 * (inset + frame.thickness),
                ),
                x,
                y,
            )
            if not in_ring:
                assert not ring.is_ink(x, y) or inside(plan.content, x, y)
                continue
            if kind == pl.STALE:
                expected = (x + y) % pl.HATCH_PITCH == 0
            else:
                across = y < inset + frame.thickness or y >= 128 - inset - frame.thickness
                along = x - inset if across else y - inset
                expected = along % (pl.DASH_ON + pl.DASH_OFF) < pl.DASH_ON
            assert ring.is_ink(x, y) == expected, (x, y)
