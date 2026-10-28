"""NFR-005: the iOS app draws with the brand tokens, and only with them.

apps/ios/Lightkeeper/Sources/Palette.swift mirrors assets/brand/tokens.json:
one SwiftUI color per token, named after its color id, plus three pairs that
take their light value from one token and their dark value from another (the
panel preview on Night paper in dark mode, and the hard shadow). These tests
read the Swift source, so they run on Windows and in the CI Full suite with no
Mac. They also hold the app's asset catalog to the brand: the accent color is
Beam text, and the app icon is assets/brand/png/app-icon.png pixel for pixel.

If a palette test fails, change the color in tokens.json first, then mirror it
in Palette.swift; never the other way round.
"""

import json
import re
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "apps" / "ios" / "Lightkeeper"
SOURCES = APP / "Sources"
PALETTE = SOURCES / "Palette.swift"
CATALOG = SOURCES / "Assets.xcassets"
PROJECT = APP / "project.yml"
BRAND_ICON = ROOT / "assets" / "brand" / "png" / "app-icon.png"
TOKENS = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))
COLOR = TOKENS["color"]

SWIFT_COLOR = re.compile(r'static let (\w+) = Color\(light: "([^"]*)", dark: "([^"]*)"\)')
HEX = re.compile(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])")
# Ways to make a color without a token: a literal, or a system color by name.
RAW_COLOR = re.compile(
    r"\b(?:Color|UIColor)\s*\(\s*(?:red|hue|white|\.sRGB|\.displayP3|cgColor|uiColor|hex)\b"
    r"|(?<![\w.])(?:Color|UIColor)?\.(?:red|orange|yellow|green|mint|teal|cyan|blue|indigo|"
    r"purple|pink|brown|gray|black|white|systemRed|systemOrange|systemGreen)\b"
)

# Colors drawn from two tokens: (light token, dark token).
PAIRS = {
    # The panel preview: Paper and Ink by day, Night paper and Night ink in
    # dark mode, so the panel is never the brightest thing at the bedside.
    "panelPaper": ("paper", "night-paper"),
    "panelInk": ("ink", "night-ink"),
    # Hard offset shadow: Beam soft (light) or Line (dark).
    "hardShadow": ("beam-soft", "line"),
}


def token_id(name):
    """Return the tokens.json color id a Palette name mirrors: statusLow is low."""
    if name.startswith("status"):
        name = name[len("status") :]
        name = name[0].lower() + name[1:]
    return re.sub(r"(?<!^)([A-Z])", r"-\1", name).lower()


def palette():
    """Return {name: (light, dark)} for every color Palette.swift defines."""
    return {
        name: (light, dark)
        for name, light, dark in SWIFT_COLOR.findall(PALETTE.read_text(encoding="utf-8"))
    }


def expected(name):
    """Return the (light, dark) hex values tokens.json gives a Palette name."""
    light_id, dark_id = PAIRS.get(name, (token_id(name), token_id(name)))
    return COLOR[light_id]["light"], COLOR[dark_id]["dark"]


def png_rgb(path):
    """Return (width, height, rows) of an 8-bit RGB PNG, rows unfiltered."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    header, idat, pos = b"", b"", 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", header)
    # Color type 2 is RGB with no alpha channel, which an app icon must be.
    assert (depth, color, interlace) == (8, 2, 0), f"{path.name}: not 8-bit RGB, or interlaced"
    raw, stride = zlib.decompress(idat), width * 3
    rows, prev = [], bytes(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        # Filter 0 (none) stores the bytes as they are; 1 to 4 store each
        # byte minus a prediction from its left, upper and upper-left bytes.
        for i in range(stride if kind else 0):
            a = line[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if kind == 1:
                predicted = a
            elif kind == 2:
                predicted = b
            elif kind == 3:
                predicted = (a + b) // 2
            else:
                assert kind == 4, f"{path.name}: unknown filter {kind} on row {y}"
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predicted = a if pa <= pb and pa <= pc else b if pb <= pc else c
            line[i] = (line[i] + predicted) & 0xFF
        rows.append(bytes(line))
        prev = line
    return width, height, rows


def catalog(path):
    return json.loads((CATALOG / path / "Contents.json").read_text(encoding="utf-8"))


# --- the palette mirrors tokens.json ---------------------------------------------


def test_nfr005_every_palette_entry_is_a_light_and_dark_pair():
    # A color written any other way would escape the comparison below.
    source = PALETTE.read_text(encoding="utf-8")
    declared = re.findall(r"static let (\w+)", source)
    assert declared, "no colors found in Palette.swift"
    assert sorted(declared) == sorted(palette()), "every static let is Color(light:dark:)"
    for name, (light, dark) in palette().items():
        assert re.fullmatch(r"#[0-9A-F]{6}", light), f"{name}: {light}"
        assert re.fullmatch(r"#[0-9A-F]{6}", dark), f"{name}: {dark}"


@pytest.mark.parametrize("name", sorted(palette()))
def test_nfr005_every_palette_hex_equals_tokens_json(name):
    assert palette()[name] == expected(name), f"Palette.{name} has drifted from tokens.json"


def test_nfr005_palette_mirrors_every_brand_color():
    mirrored = {token_id(name) for name in palette() if name not in PAIRS}
    assert mirrored == set(COLOR), "one Palette color per tokens.json color id, and no extras"
    for light_id, dark_id in PAIRS.values():
        assert light_id in COLOR and dark_id in COLOR


def test_nfr005_panel_preview_uses_night_paper_in_dark_mode():
    assert palette()["panelPaper"][1] == COLOR["night-paper"]["dark"]
    assert palette()["panelInk"][1] == COLOR["night-ink"]["dark"]
    assert palette()["panelPaper"][0] == COLOR["paper"]["light"]


def test_nfr005_token_ids_map_to_palette_names():
    assert token_id("statusInRange") == "in-range"
    assert token_id("statusLow") == "low"
    assert token_id("chipInRange") == "chip-in-range"
    assert token_id("lineStrong") == "line-strong"
    assert token_id("fog") == "fog"


@pytest.mark.parametrize(
    "path",
    sorted(p for p in SOURCES.glob("*.swift") if p.name != PALETTE.name),
    ids=lambda p: p.name,
)
def test_nfr005_no_app_source_makes_a_color_outside_the_palette(path):
    source = path.read_text(encoding="utf-8")
    assert not HEX.findall(source), f"{path.name}: a hex color belongs in Palette.swift"
    assert not RAW_COLOR.findall(source), f"{path.name}: use a Palette color"


def test_nfr005_color_guards_catch_what_they_should():
    for spelled in (
        "Color(red: 1, green: 0, blue: 0)",
        ".foregroundStyle(.red)",
        "Color.gray",
        "UIColor(white: 0.5, alpha: 1)",
        "Color(hex: x)",
    ):
        assert RAW_COLOR.search(spelled), spelled
    for fine in (
        "Palette.statusLow",
        ".font(.title3)",
        "Text(reading.trend.symbol)",
        ".redacted(reason:)",
        "model.lastRefresh",
        "#Preview",
    ):
        assert not RAW_COLOR.search(fine), fine
        assert not HEX.search(fine), fine
    assert HEX.search('"#15171C"')


# --- the asset catalog -----------------------------------------------------------


def hex_of(components):
    return "#" + "".join(f"{int(components[c], 16):02X}" for c in ("red", "green", "blue"))


def test_nfr005_accent_color_is_beam_text():
    # The accent tints control text (Save, Check connection, Reset to
    # defaults), which is under 24 pt, so it is Beam text, not Beam: Beam on a
    # light ground is under 4.5:1 (docs/BRAND.md). In dark mode Beam text is Beam.
    colors = catalog("AccentColor.colorset")["colors"]
    light = [c for c in colors if "appearances" not in c]
    dark = [
        c
        for c in colors
        if c.get("appearances") == [{"appearance": "luminosity", "value": "dark"}]
    ]
    assert len(light) == 1 and len(dark) == 1 and len(colors) == 2
    for entry, theme in ((light[0], "light"), (dark[0], "dark")):
        assert entry["idiom"] == "universal"
        assert entry["color"]["color-space"] == "srgb"
        assert float(entry["color"]["components"]["alpha"]) == 1
        assert hex_of(entry["color"]["components"]) == COLOR["beam-text"][theme], theme


def test_nfr005_app_icon_is_the_brand_icon_at_1024():
    images = catalog("AppIcon.appiconset")["images"]
    assert images == [
        {
            "filename": "app-icon.png",
            "idiom": "universal",
            "platform": "ios",
            "size": "1024x1024",
        }
    ]
    width, height, rows = png_rgb(CATALOG / "AppIcon.appiconset" / "app-icon.png")
    assert (width, height) == (1024, 1024)
    # The brand PNG at a whole-number scale, nearest neighbour: every brand
    # pixel is a factor x factor block of the icon, so the two cannot drift.
    brand_width, brand_height, brand = png_rgb(BRAND_ICON)
    assert brand_width == brand_height and 1024 % brand_width == 0
    factor = 1024 // brand_width
    for y, row in enumerate(rows):
        source = brand[y // factor]
        scaled = b"".join(source[x : x + 3] * factor for x in range(0, len(source), 3))
        assert row == scaled, f"icon row {y} differs from {BRAND_ICON.name}"


def test_nfr005_png_reader_undoes_every_row_filter(tmp_path):
    # One 2x5 image written with each filter type must read back the same.
    pixels = [bytes([10, 20, 30, 200, 100, 50]), bytes([40, 60, 80, 7, 9, 11])] * 2
    pixels.append(bytes([255, 0, 128, 1, 2, 3]))
    raw, prev = b"", bytes(6)
    for kind, line in enumerate(pixels):
        out = bytearray()
        for i, value in enumerate(line):
            a = line[i - 3] if i >= 3 else 0
            b, c = prev[i], prev[i - 3] if i >= 3 else 0
            p = a + b - c
            paeth = min((abs(p - a), 0, a), (abs(p - b), 1, b), (abs(p - c), 2, c))[2]
            predicted = (0, a, b, (a + b) // 2, paeth)[kind]
            out.append((value - predicted) & 0xFF)
        raw += bytes([kind]) + bytes(out)
        prev = line

    def chunk(kind, body):
        crc = struct.pack(">I", zlib.crc32(kind + body))
        return struct.pack(">I", len(body)) + kind + body + crc

    png = tmp_path / "filters.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 5, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    assert png_rgb(png) == (2, 5, pixels)


def test_fr012_project_names_the_icon_and_the_accent_color():
    project = PROJECT.read_text(encoding="utf-8")
    assert re.search(r"^\s+ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon$", project, re.M)
    assert re.search(
        r"^\s+ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME: AccentColor$", project, re.M
    )
    assert (CATALOG / "AppIcon.appiconset").is_dir()
    assert (CATALOG / "AccentColor.colorset").is_dir()
    assert catalog(".")["info"] == {"author": "xcode", "version": 1}
