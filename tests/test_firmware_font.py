"""FR-016: the firmware's compiled-in font is the Keeper 5x8 font, glyph for glyph.

PlatformIO builds the device without running make, so
firmware/xteink/lib/panel_bitmap/font5x8_data.h is generated from
spec/font5x8.json by firmware/xteink/tools/gen_font_header.py and committed.
These tests fail while the committed header differs from what the generator
writes, or from the Python glyph table itself, so a glyph changed in
font5x7.py fails CI until the spec and the header are both regenerated:
`python tools/gen_panel_spec.py`, then
`python firmware/xteink/tools/gen_font_header.py`.
"""

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest

from lightkeeper.infrastructure.font5x7 import (
    FALLBACK,
    GLYPH_HEIGHT,
    GLYPH_WIDTH,
    glyph,
    glyph_table,
)

ROOT = Path(__file__).resolve().parent.parent
FIRMWARE = ROOT / "firmware" / "xteink"
HEADER = FIRMWARE / "lib" / "panel_bitmap" / "font5x8_data.h"

spec = importlib.util.spec_from_file_location(
    "gen_font_header", FIRMWARE / "tools" / "gen_font_header.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FONT = json.loads((ROOT / "spec" / "font5x8.json").read_text(encoding="utf-8"))
# One table row: eight five-bit binary literals, then the character's code.
ROW = re.compile(r"^    \{((?:0b[01]{5}, ){7}0b[01]{5})\},  // 0x([0-9A-F]{2}) ")


def committed():
    """Read the committed header, whatever line endings the checkout gave it."""
    return HEADER.read_text(encoding="utf-8").replace("\r\n", "\n")


def decoded(text):
    """Read the header's glyph table back as '#'/'.' rows, without the generator."""
    glyphs = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if match:
            cells = match.group(1).split(", ")
            rows = tuple(cell[2:].replace("1", "#").replace("0", ".") for cell in cells)
            glyphs[chr(int(match.group(2), 16))] = rows
    return glyphs


def constant(text, name):
    """Return the value of a `constexpr int` the header defines."""
    match = re.search(rf"constexpr int {name} = (0x[0-9A-F]+|[0-9]+);", text)
    assert match, f"{name} is missing from the header"
    return int(match.group(1), 0)


def test_fr016_firmware_font_header_is_current():
    assert committed() == gen.build(gen.FONT), (
        "font5x8_data.h is stale: run python firmware/xteink/tools/gen_font_header.py"
    )
    assert gen.main(["--check"]) == 0


def test_fr016_firmware_font_draws_every_python_glyph():
    text = committed()
    glyphs = decoded(text)
    first, last = constant(text, "kFirstGlyph"), constant(text, "kLastGlyph")
    assert (first, last) == (0x20, 0x7E)
    assert list(glyphs) == [chr(code) for code in range(first, last + 1)]
    assert constant(text, "kGlyphCount") == len(glyphs)
    assert (constant(text, "kGlyphWidth"), constant(text, "kGlyphHeight")) == (
        GLYPH_WIDTH,
        GLYPH_HEIGHT,
    )
    assert chr(constant(text, "kFallbackGlyph")) == FALLBACK
    assert set(glyph_table()) <= set(glyphs)
    for char, rows in glyphs.items():
        assert rows == glyph(char), f"glyph {char!r} differs from font5x7.py"


def test_fr016_firmware_font_header_is_formatted():
    text = committed()
    assert text.endswith("};\n\n}  // namespace lk\n") and text.isascii()
    # clang-format's column limit (firmware/xteink/.clang-format); make format-check runs it.
    assert max(len(line) for line in text.splitlines()) <= 100


def test_fr016_a_font_change_fails_until_the_header_is_regenerated(tmp_path, monkeypatch, capsys):
    changed = copy.deepcopy(FONT)
    changed["glyphs"]["0"][3] = "#####"  # a glyph edited in Python and exported to the spec
    font = tmp_path / "font5x8.json"
    font.write_text(json.dumps(changed), encoding="utf-8")
    header = tmp_path / "lib" / "font5x8_data.h"
    monkeypatch.setattr(gen, "FONT", font)
    monkeypatch.setattr(gen, "HEADER", header)

    assert gen.main(["--check"]) == 1  # no header yet
    header.parent.mkdir()
    header.write_text(committed(), encoding="utf-8")
    assert gen.main(["--check"]) == 1
    assert "out of date: font5x8_data.h" in capsys.readouterr().out
    assert header.read_text(encoding="utf-8") == committed()  # --check writes nothing

    assert gen.main([]) == 0
    assert "wrote font5x8_data.h" in capsys.readouterr().out
    assert gen.main(["--check"]) == 0
    assert decoded(header.read_text(encoding="utf-8"))["0"][3] == "#####"
    assert b"\r\n" not in header.read_bytes()

    # A Windows checkout's CRLF endings still count as current.
    header.write_bytes(header.read_bytes().replace(b"\n", b"\r\n"))
    assert gen.main(["--check"]) == 0


def test_fr016_firmware_font_fills_gaps_with_the_fallback():
    gapped = copy.deepcopy(FONT)
    del gapped["glyphs"]["~"]
    glyphs = decoded(gen.render(gapped))
    assert glyphs["~"] == tuple(FONT["glyphs"][FALLBACK])
    assert len(glyphs) == 0x7E - 0x20 + 1


def _set(path, value):
    def edit(font):
        *keys, last = path
        target = font
        for key in keys:
            target = target[key]
        target[last] = value

    return edit


def _add_glyph(char):
    return _set(("glyphs", char), ["....."] * 8)


@pytest.mark.parametrize(
    ("edit", "reason"),
    [
        (_set(("glyph_width",), 6), "5x8 cells"),
        (_set(("glyph_height",), 7), "5x8 cells"),
        (_set(("glyphs",), []), "holds its fallback"),
        (_set(("fallback",), "é"), "holds its fallback"),
        (_set(("fallback",), None), "holds its fallback"),
        (_add_glyph("é"), "outside printable ASCII"),
        (_add_glyph("\x7f"), "outside printable ASCII"),
        (_add_glyph("\x1f"), "outside printable ASCII"),
        (_add_glyph("ab"), "outside printable ASCII"),
        (_set(("glyphs", "A"), ["....."] * 7), "8 rows of 5"),
        (_set(("glyphs", "A"), ["....."] * 7 + ["...."]), "8 rows of 5"),
        (_set(("glyphs", "A"), ["....."] * 7 + ["..x.."]), "8 rows of 5"),
    ],
)
def test_fr016_firmware_font_refuses_what_the_firmware_cannot_draw(edit, reason):
    font = copy.deepcopy(FONT)
    edit(font)
    with pytest.raises(ValueError, match=reason):
        gen.render(font)
