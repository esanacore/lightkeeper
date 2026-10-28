"""Generate lib/panel_bitmap/font5x8_data.h from spec/font5x8.json.

The header is the Keeper 5x8 font compiled into the firmware. PlatformIO builds
the device without running make, so the header is committed rather than made
at build time. tests/test_firmware_font.py fails while the committed file
differs from what this script writes, so a glyph changed in Python (font5x7.py,
exported to spec/font5x8.json by tools/gen_panel_spec.py) fails CI until the
header is regenerated here.

The output is already clang-format clean, so `make format-check` passes on it.

Usage (from the repository root or firmware/xteink):
    python firmware/xteink/tools/gen_font_header.py           # write the header
    python firmware/xteink/tools/gen_font_header.py --check   # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent.parent
ROOT = FIRMWARE.parent.parent
FONT = ROOT / "spec" / "font5x8.json"
HEADER = FIRMWARE / "lib" / "panel_bitmap" / "font5x8_data.h"

# The table covers printable ASCII; the C++ draws any other byte as the fallback.
FIRST = 0x20
LAST = 0x7E
WIDTH = 5
HEIGHT = 8

PREAMBLE = """\
// Generated from spec/font5x8.json by tools/gen_font_header.py. Do not edit.
//
// Keeper 5x8, the project's own bitmap font (src/lightkeeper/infrastructure/
// font5x7.py), for printable ASCII, 0x20 to 0x7E. One byte per glyph row, top
// to bottom: the five low bits are the five columns, the leftmost column in
// bit 4, and 1 is ink, so each literal reads like the glyph row it draws.
// Capitals and digits use rows 0 to 6; row 7 holds descenders. A character
// outside the table draws as the fallback glyph, as in Python.
//
// tests/test_firmware_font.py fails until this file matches the font.

#pragma once

#include <stdint.h>

namespace lk {
"""


def glyph_table(spec: dict[str, object]) -> list[tuple[int, list[str]]]:
    """Return (code, rows) for every printable ASCII code, the fallback filling any gap.

    Raises ValueError for anything the C++ table cannot hold the same way
    Python draws it: a cell size other than 5x8, a malformed row, or a glyph
    outside printable ASCII.
    """
    if (spec["glyph_width"], spec["glyph_height"]) != (WIDTH, HEIGHT):
        raise ValueError(f"the firmware font is {WIDTH}x{HEIGHT} cells")
    glyphs = spec["glyphs"]
    fallback = spec["fallback"]
    if not isinstance(glyphs, dict) or not isinstance(fallback, str) or fallback not in glyphs:
        raise ValueError("the font needs a glyph table that holds its fallback")
    for char, rows in glyphs.items():
        if len(char) != 1 or not FIRST <= ord(char) <= LAST:
            raise ValueError(f"glyph {char!r} is outside printable ASCII")
        if len(rows) != HEIGHT or any(len(row) != WIDTH or set(row) - {"#", "."} for row in rows):
            raise ValueError(f"glyph {char!r} is not {HEIGHT} rows of {WIDTH} '#' or '.' cells")
    return [(code, list(glyphs.get(chr(code), glyphs[fallback]))) for code in range(FIRST, LAST + 1)]


def row_literal(row: str) -> str:
    """Return one glyph row as a C++ binary literal: '.###.' is 0b01110."""
    return "0b" + row.replace("#", "1").replace(".", "0")


def render(spec: dict[str, object]) -> str:
    """Return the header text for a font spec (the parsed spec/font5x8.json)."""
    table = glyph_table(spec)
    fallback = str(spec["fallback"])  # glyph_table has checked it is one of the glyphs
    lines = [
        PREAMBLE,
        f"constexpr int kGlyphWidth = {WIDTH};",
        f"constexpr int kGlyphHeight = {HEIGHT};",
        f"constexpr int kFirstGlyph = 0x{FIRST:02X};",
        f"constexpr int kLastGlyph = 0x{LAST:02X};",
        f"constexpr int kFallbackGlyph = 0x{ord(fallback):02X};  // '{fallback}'",
        f"constexpr int kGlyphCount = {len(table)};",
        "",
        "constexpr uint8_t kFont5x8[kGlyphCount][kGlyphHeight] = {",
    ]
    for code, rows in table:
        cells = ", ".join(row_literal(row) for row in rows)
        lines.append(f"    {{{cells}}},  // 0x{code:02X} '{chr(code)}'")
    lines += ["};", "", "}  // namespace lk", ""]
    return "\n".join(lines)


def build(font: Path = FONT) -> str:
    """Return the header text generated from the font file."""
    return render(json.loads(font.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    """Write the header, or with --check report whether it is current."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the header is stale")
    args = parser.parse_args(argv)
    text = build()
    current = HEADER.read_text(encoding="utf-8").replace("\r\n", "\n") if HEADER.exists() else ""
    if current == text:
        return 0
    if args.check:
        print(f"out of date: {HEADER.name}; run python firmware/xteink/tools/gen_font_header.py")
        return 1
    HEADER.parent.mkdir(parents=True, exist_ok=True)
    HEADER.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {HEADER.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
