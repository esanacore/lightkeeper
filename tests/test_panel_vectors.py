"""FR-016: the shared pixel vectors and font file match the reference rasterizer.

spec/panel_vectors.json pins every display vector's pixels at every panel
profile by CRC-32, so the JavaScript and C++ ports can prove they draw the
same image. If a test here fails after an intended layout change, run
`python tools/gen_panel_spec.py`, review the diff, and commit the result.
"""

import importlib.util
import json
import shutil
import zlib
from pathlib import Path

import pytest

from lightkeeper.infrastructure import panel_layout as pl
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap
from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT, GLYPH_WIDTH, glyph_table
from lightkeeper.infrastructure.panel_profiles import ALIASES, DEFAULT_PROFILE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"

spec = importlib.util.spec_from_file_location(
    "gen_panel_spec", ROOT / "tools" / "gen_panel_spec.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PANEL = json.loads((SPEC / "panel_vectors.json").read_text(encoding="utf-8"))
FONT = json.loads((SPEC / "font5x8.json").read_text(encoding="utf-8"))
DISPLAY = {c["name"]: c for c in json.loads((SPEC / "display_vectors.json").read_text())["cases"]}


def committed(relative):
    """Read a committed file's text, whatever line endings the checkout gave it."""
    return (ROOT / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


def test_fr016_panel_vectors_are_current():
    for relative, text in gen.build().items():
        assert committed(relative) == text, f"{relative} is stale: run tools/gen_panel_spec.py"


def test_fr016_every_case_lines_equal_the_display_vector():
    for case in PANEL["cases"]:
        assert case["lines"] == DISPLAY[case["vector"]]["lines"], case["vector"]


def test_fr016_font_file_equals_glyph_table():
    assert FONT["glyphs"] == {char: list(rows) for char, rows in glyph_table().items()}
    assert (FONT["glyph_width"], FONT["glyph_height"]) == (GLYPH_WIDTH, GLYPH_HEIGHT)
    assert FONT["fallback"] in FONT["glyphs"]
    assert list(FONT["glyphs"]) == sorted(FONT["glyphs"])


def test_fr016_every_vector_at_every_profile_plus_stamped_cases():
    cases = PANEL["cases"]
    assert PANEL["panel_spec_version"] == 1
    assert len(cases) == 237 == len(DISPLAY) * len(PROFILES) + 3
    keys = [(c["vector"], c["profile"], c.get("stamp")) for c in cases]
    assert len(set(keys)) == len(keys)
    for profile in PROFILES:
        assert {v for v, p, s in keys if p == profile and s is None} == set(DISPLAY)
    stamped = [c for c in cases if "stamp" in c]
    assert [(c["vector"], c["profile"], c["stamp"]) for c in stamped] == gen.STAMPED
    assert (SPEC / "panel_vectors.json").stat().st_size < 100 * 1024


def test_fr016_spec_tables_match_the_code():
    assert PANEL["treatments"] == pl.TREATMENTS
    assert PANEL["unknown_treatment"] == pl.UNKNOWN_TREATMENT == pl.DASHED
    assert PANEL["default_profile"] == DEFAULT_PROFILE
    assert PANEL["aliases"] == ALIASES
    assert PANEL["profiles"] == {
        p.name: {"width": p.width, "height": p.height, "description": p.description}
        for p in PROFILES.values()
    }
    for case in PANEL["cases"]:
        size = PROFILES[case["profile"]]
        assert (case["width"], case["height"]) == (size.width, size.height)
    constants = PANEL["layout"]["constants"]
    assert constants["band_pad"] == pl.BAND_PAD
    assert constants["min_gap"] == pl.MIN_GAP
    assert constants["reference_headline"] == pl.REFERENCE_HEADLINE
    assert constants["widest_line"] == pl.WIDEST_LINE
    assert constants["max_side"] == pl.MAX_SIDE
    # Every case is hashed as drawn, portrait kindle included: never rotated.
    assert "as drawn" in PANEL["hash"]["input"] and "landscape" not in PANEL["hash"]["input"]
    assert any(c["height"] > c["width"] for c in PANEL["cases"])


def test_fr016_crc32_is_the_standard_one():
    # The check value every CRC-32/ISO-HDLC implementation must give.
    assert zlib.crc32(b"123456789") == 0xCBF43926


def packed_by_hand(bitmap):
    """Pack by the written hash rule, pixel by pixel, independent of to_packed_rows."""
    out = bytearray()
    for y in range(bitmap.height):
        for start in range(0, bitmap.width, 8):
            byte = 0
            for bit in range(8):
                x = start + bit
                if x < bitmap.width and bitmap.is_ink(x, y):
                    byte |= 0x80 >> bit
            out.append(byte)
    return bytes(out)


@pytest.mark.parametrize("profile", list(PROFILES))
def test_fr016_case_hashes_follow_the_written_rule(profile):
    for case in PANEL["cases"]:
        if case["profile"] != profile or case["vector"] not in (
            "in_range_flat",
            "stale_at_16_minutes",
            "no_data_unreachable",
            "urgent_low_55",
            "high_181",
        ):
            continue
        size = PROFILES[profile]
        bitmap = render_bitmap(case["lines"], size.width, size.height, case.get("stamp"))
        packed = packed_by_hand(bitmap)
        assert len(packed) == (size.width + 7) // 8 * size.height
        assert zlib.crc32(packed) == case["crc32"], case["vector"]
        assert sum(bitmap.ink) == case["ink"]


def test_fr016_check_mode_reports_and_write_mode_repairs(tmp_path, monkeypatch, capsys):
    (tmp_path / "spec").mkdir()
    shutil.copy(SPEC / "display_vectors.json", tmp_path / "spec" / "display_vectors.json")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    assert gen.main(["--check"]) == 1
    assert "out of date: spec/font5x8.json, spec/panel_vectors.json" in capsys.readouterr().out
    assert gen.main([]) == 0
    assert gen.main(["--check"]) == 0
    assert (tmp_path / "spec" / "panel_vectors.json").read_bytes() == (
        committed("spec/panel_vectors.json").encode()
    )
    assert b"\r\n" not in (tmp_path / "spec" / "font5x8.json").read_bytes()
