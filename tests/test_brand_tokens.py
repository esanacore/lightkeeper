"""NFR-005: the brand tokens have one source, the guide mirrors it, and every pairing is legible.

assets/brand/tokens.json is the machine-readable twin of docs/BRAND.md. These
tests keep the two equal, recompute every contrast ratio the guide quotes from
the hex values, hold the WCAG minimums the Keeper's Logbook relies on, check
that every status keeps its word and a shape with all color removed, and check
the pixel icons and their committed PNGs.

If a PNG test fails, run `python tools/gen_brand_pixels.py` and commit the result.
"""

import importlib.util
import json
import math
import re
import struct
import zlib
from pathlib import Path

import pytest

from lightkeeper.domain.status import Level

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "docs" / "BRAND.md"
TOKENS_JSON = ROOT / "assets" / "brand" / "tokens.json"
ICONS_JSON = ROOT / "assets" / "brand" / "pixel-icons.json"
VECTORS = ROOT / "spec" / "display_vectors.json"

spec = importlib.util.spec_from_file_location(
    "gen_brand_pixels", ROOT / "tools" / "gen_brand_pixels.py"
)
pixels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pixels)


def load_strict(path):
    """Parse JSON and refuse repeated keys, which json.loads would silently collapse."""

    def no_repeats(pairs):
        keys = [key for key, _ in pairs]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        assert not repeated, f"{path.name} repeats keys: {repeated}"
        return dict(pairs)

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_repeats)


TOKENS = load_strict(TOKENS_JSON)
COLOR = TOKENS["color"]
STATUS = TOKENS["status"]
ICONS = load_strict(ICONS_JSON)["icons"]
DOC = BRAND.read_text(encoding="utf-8")

HEX = re.compile(r"#[0-9A-F]{6}")
RATIO = re.compile(r"\d+\.\d{2}")
CODE = re.compile(r"`([^`]*)`")
STATUS_COLORS = sorted({entry["color"] for entry in STATUS.values()})
CHIPS = sorted({entry["chip"] for entry in STATUS.values()})
BORDER = {entry["chip"]: entry["color"] for entry in STATUS.values()}  # chip -> status color
BANDS = {name: entry for name, entry in TOKENS["treatment"].items() if "band" in entry}
CONTROL = TOKENS["control"]
THEME_DEFAULTS = TOKENS["theme"]["defaults"]
THEMES = ("light", "dark")
# Where text and data sit, per theme. Dark Fog is Night; dark Paper is a light
# e-ink panel, never a ground for dark-theme text and never text on the dark Ink band.
GROUNDS = {"light": ("fog", "paper", "surface"), "dark": ("fog", "surface")}


# --- helpers ------------------------------------------------------------------


def luminance(hex_color):
    """WCAG 2.2 relative luminance of an sRGB hex color."""

    def channel(value):
        s = value / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    """WCAG 2.2 contrast ratio between two hex colors, at least 1.0."""
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def quoted(a, b):
    """Return the ratio as the guide prints it."""
    return f"{contrast(a, b):.2f}"


def table(heading):
    """Cells of the first Markdown table under `heading`, header and rule rows dropped."""
    lines = DOC.splitlines()
    start = lines.index(heading) + 1
    rows = []
    for line in lines[start:]:
        if line.startswith("#"):
            break
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip()[1:-1].split("|")])
        elif rows:
            break
    assert len(rows) > 2, f"no table under {heading!r} in docs/BRAND.md"
    return rows[2:]


def plain(cell):
    """Return a table cell without its code backticks."""
    return cell.replace("`", "")


def ink_cells(rows):
    return {(x, y) for y, row in enumerate(rows) for x, cell in enumerate(row) if cell == "#"}


def icon(name):
    return next(entry for entry in ICONS if entry["name"] == name)


def png_content(data):
    """(IHDR, decompressed pixel data): what a PNG shows, independent of the zlib build."""
    header, pixels_, pos = b"", b"", 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            pixels_ += body
        pos += 12 + length
    return header, zlib.decompress(pixels_)


def png_ink(data):
    """Decode a 1-bit grayscale PNG with unfiltered rows into its set of black pixels."""
    header, raw = png_content(data)
    width, height, depth, color_type = struct.unpack(">IIBB", header[:10])
    assert (depth, color_type, header[12]) == (1, 0, 0), "expected 1-bit gray, not interlaced"
    stride = (width + 7) // 8
    ink = set()
    for y in range(height):
        row = raw[y * (stride + 1) : (y + 1) * (stride + 1)]
        assert row[0] == 0, "expected filter type none on every row"
        for x in range(width):
            if not row[1 + x // 8] & (0x80 >> (x % 8)):
                ink.add((x, y))
    return width, height, ink


def components(cells):
    """4-connected groups of cells."""
    left, groups = set(cells), []
    while left:
        stack, group = [left.pop()], set()
        while stack:
            x, y = stack.pop()
            group.add((x, y))
            for near in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if near in left:
                    left.remove(near)
                    stack.append(near)
        groups.append(group)
    return groups


# --- the guide mirrors tokens.json ----------------------------------------------


def test_nfr005_tokens_json_has_both_themes_for_every_color():
    assert COLOR, "tokens.json has no colors"
    for token_id, token in COLOR.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", token_id), token_id
        assert set(token) == {"name", "light", "dark", "role", "one_bit"}, token_id
        for theme in ("light", "dark"):
            assert HEX.fullmatch(token[theme]), f"{token_id} {theme}: {token[theme]!r}"


def test_nfr005_brand_color_tables_mirror_tokens_json():
    rows = table("## Color") + table("### New tokens")
    assert [row[0] for row in rows] == [token["name"] for token in COLOR.values()]
    for row, token in zip(rows, COLOR.values(), strict=True):
        assert HEX.findall(row[1]) == [token["light"]], row[0]
        assert HEX.findall(row[2]) == [token["dark"]], row[0]
        assert row[3] == token["role"], row[0]


def test_nfr005_existing_tokens_keep_their_values():
    # The values the guide carried before the Keeper's Logbook, unchanged by it.
    before = {
        "night": ("#0E1116", "#0E1116"),
        "ink": ("#15171C", "#E6E5DF"),
        "paper": ("#E6E5DF", "#DDDCD5"),
        "fog": ("#ECEBE5", "#0E1116"),
        "surface": ("#F6F5F0", "#161A21"),
        "line": ("#CFCDC4", "#262B33"),
        "muted": ("#5B6068", "#9AA0A9"),
        "beam": ("#B8730A", "#E0A526"),
        "beam-soft": ("#F1DDB4", "#3A2E13"),
        "in-range": ("#2E6B4A", "#6CC597"),
        "low": ("#B3261E", "#FF6B5E"),
        "high": ("#B86A00", "#F5A341"),
        "stale": ("#6B6F76", "#9AA0A9"),
    }
    assert {key: (COLOR[key]["light"], COLOR[key]["dark"]) for key in before} == before


def test_nfr005_color_table_contrast_column_is_measured_on_fog():
    by_name = {token["name"]: token for token in COLOR.values()}
    for row in table("## Color"):
        token = by_name[row[0]]
        expected = [
            quoted(token["light"], COLOR["fog"]["light"]),
            quoted(token["dark"], COLOR["fog"]["dark"]),
        ]
        assert RATIO.findall(row[4]) == expected, row[0]


def test_nfr005_new_token_ratios_are_measured():
    def pairs_on(token, light_grounds, dark_grounds):
        return [("light", token, ground) for ground in light_grounds] + [
            ("dark", token, ground) for ground in dark_grounds
        ]

    measured = {
        "line-strong": pairs_on("line-strong", GROUNDS["light"], ("night", "surface")),
        "beam-text": pairs_on("beam-text", GROUNDS["light"], ("night", "surface")),
        "band-text": pairs_on("band-text", ("ink",), ("ink",)),
        "night-paper": [("dark", "night-ink", "night-paper")],
        "night-ink": [("dark", "night-ink", "night-paper")],
    }
    for chip, status_color in BORDER.items():
        measured[chip] = [
            (theme, fg, chip) for theme in ("light", "dark") for fg in ("ink", status_color)
        ]
    by_name = {token["name"]: key for key, token in COLOR.items()}
    rows = table("### New tokens")
    assert {by_name[row[0]] for row in rows} == set(measured)
    for row in rows:
        expected = [
            quoted(COLOR[fg][theme], COLOR[bg][theme])
            for theme, fg, bg in measured[by_name[row[0]]]
        ]
        assert RATIO.findall(row[4]) == expected, row[0]


# --- WCAG minimums ----------------------------------------------------------------


def light(token):
    return COLOR[token]["light"]


def dark(token):
    return COLOR[token]["dark"]


MINIMUMS = (
    [(f"beam-text on light {g}", light("beam-text"), light(g), 4.5) for g in GROUNDS["light"]]
    + [(f"beam-text on dark {g}", dark("beam-text"), dark(g), 4.5) for g in GROUNDS["dark"]]
    + [("Beam on Night", dark("beam"), light("night"), 4.5)]
    + [(f"line-strong on light {g}", light("line-strong"), light(g), 3) for g in GROUNDS["light"]]
    + [(f"line-strong on dark {g}", dark("line-strong"), dark(g), 3) for g in ("night", "surface")]
    + [(f"Ink on light {chip}", light("ink"), light(chip), 7) for chip in CHIPS]
    + [(f"text on dark {chip}", dark("ink"), dark(chip), 4.5) for chip in CHIPS]
    + [
        (f"{border} border on {theme} {chip}", COLOR[border][theme], COLOR[chip][theme], 3)
        for chip, border in BORDER.items()
        for theme in ("light", "dark")
    ]
    + [("Night ink on Night paper", dark("night-ink"), dark("night-paper"), 7)]
    # The URGENT and STALE words on their Ink band, and a pressed control, in both themes.
    + [
        (
            f"{name} band text on {theme} band",
            COLOR[entry["band_text"]][theme],
            COLOR[entry["band"]][theme],
            7,
        )
        for name, entry in BANDS.items()
        for theme in THEMES
    ]
    + [
        (
            f"pressed text on {theme} pressed fill",
            COLOR[CONTROL["pressed_text"]][theme],
            COLOR[CONTROL["pressed_fill"]][theme],
            7,
        )
        for theme in THEMES
    ]
    + [
        (f"control {part} on {theme} {g}", COLOR[CONTROL[part]][theme], COLOR[g][theme], 3)
        for part in ("border", "focus_ring")
        for theme, grounds in GROUNDS.items()
        for g in grounds
    ]
    # Theme defaults on the default background: the accent may carry small text.
    + [
        (
            f"theme {slot} on {theme} background",
            COLOR[THEME_DEFAULTS[slot]][theme],
            COLOR[THEME_DEFAULTS["background"]][theme],
            minimum,
        )
        for slot, minimum in (("foreground", 7), ("accent", 4.5), ("line", 3))
        for theme in THEMES
    ]
    + [
        (f"Ink on {theme} {g}", COLOR["ink"][theme], COLOR[g][theme], 7)
        for theme, grounds in GROUNDS.items()
        for g in grounds
    ]
    + [
        (f"Muted on {theme} {g}", COLOR["muted"][theme], COLOR[g][theme], 4.5)
        for theme, grounds in GROUNDS.items()
        for g in grounds
    ]
    # Status words in color and the Beam lamp, rules and focus ring: large text and
    # non-text contrast, 3:1 on every ground.
    + [
        (f"{token} on {theme} {g}", COLOR[token][theme], COLOR[g][theme], 3)
        for token in [*STATUS_COLORS, "beam"]
        for theme, grounds in GROUNDS.items()
        for g in grounds
    ]
)


@pytest.mark.parametrize(
    ("foreground", "background", "minimum"),
    [pair[1:] for pair in MINIMUMS],
    ids=[pair[0] for pair in MINIMUMS],
)
def test_nfr005_wcag_minimums(foreground, background, minimum):
    assert contrast(foreground, background) >= minimum


@pytest.mark.parametrize(
    "key", [key for key in TOKENS["proposed"]["night-profile"]["colors"] if key != "background"]
)
def test_nfr005_proposed_night_tokens_are_legible_on_black(key):
    night = TOKENS["proposed"]["night-profile"]["colors"]
    assert night["background"] == "#000000"
    assert contrast(night[key], night["background"]) >= 4.5


def test_nfr005_contrast_helper_matches_known_wcag_values():
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#777777", "#FFFFFF") == pytest.approx(4.478, abs=0.001)
    assert contrast("#123456", "#123456") == 1.0


# --- status words and shapes ------------------------------------------------------


def test_nfr005_every_status_token_maps_to_its_status_word():
    cases = json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]
    assert set(STATUS) == {level.value for level in Level}
    assert {case["level"] for case in cases} == set(STATUS), "a level has no vector"
    for case in cases:
        assert STATUS[case["level"]]["word"] == case["lines"][0], case["name"]
    for level, entry in STATUS.items():
        # The guide's row for the color names this level: "Low, urgent low" for URGENT LOW.
        named = [part.strip().lower() for part in COLOR[entry["color"]]["name"].split(",")]
        assert level.lower() in named, (level, entry["color"])
        assert entry["chip"] in COLOR and entry["chip"].startswith("chip-"), level
    status_role = {key for key, token in COLOR.items() if token["role"] == "Status"}
    assert set(STATUS_COLORS) == status_role
    # One chip per status color and one status color per chip, so a border is never ambiguous.
    pairs = {(entry["chip"], entry["color"]) for entry in STATUS.values()}
    assert len(pairs) == len(CHIPS) == len(STATUS_COLORS)


def test_nfr005_shape_grammar_reads_with_all_color_removed():
    groups = {}
    for level, entry in STATUS.items():
        groups.setdefault(entry["treatment"], []).append(level)
    assert {name: sorted(levels) for name, levels in groups.items()} == {
        "plain": ["IN RANGE"],
        "rule": ["HIGH", "LOW"],
        "inverse": ["URGENT HIGH", "URGENT LOW"],
        "stale": ["STALE"],
        "dashed": ["NO DATA"],
    }
    assert set(TOKENS["treatment"]) == set(groups)


def test_nfr005_treatments_differ_on_the_panel_and_on_screens():
    for side in ("panel", "screen"):
        texts = [entry[side] for entry in TOKENS["treatment"].values()]
        assert len(set(texts)) == len(texts), f"two treatments share one {side} description"


def test_nfr005_bands_name_their_text_color_in_both_themes():
    # URGENT and STALE words sit on an Ink band. Their color is a token of its own,
    # Paper's value in light and Night's in dark, because dark Paper on dark Ink is 1.09:1.
    assert set(BANDS) == {"inverse", "stale"}
    for name, entry in BANDS.items():
        assert (entry["band"], entry["band_text"]) == ("ink", "band-text"), name
        assert f"in {COLOR[entry['band_text']]['name']}" in entry["screen"], name
    assert COLOR["band-text"]["light"] == COLOR["paper"]["light"]
    assert COLOR["band-text"]["dark"] == COLOR["night"]["dark"]


def test_nfr005_controls_mirror_tokens_json():
    name = {part: COLOR[token]["name"] for part, token in CONTROL.items()}
    assert set(name) == {"border", "focus_ring", "pressed_fill", "pressed_text"}
    fill, text = name["pressed_fill"], name["pressed_text"]
    assert f"A pressed control is an {fill} fill with {text}." in DOC
    assert f"The focus ring is 2 px {name['focus_ring']} with a 2 px offset." in DOC
    assert f"Controls are 44 px or larger, with {name['border']} borders" in DOC


def test_nfr005_unknown_headline_gets_the_most_cautious_treatment():
    unknown = TOKENS["unknown_headline"]
    no_data = STATUS["NO DATA"]
    assert unknown == {key: no_data[key] for key in ("color", "chip", "treatment", "icon")}
    assert TOKENS["terminal"]["unknown_headline"] == TOKENS["terminal"]["sgr"]["NO DATA"]


def test_nfr005_brand_shape_grammar_mirrors_tokens_json():
    words = {entry["word"]: entry["treatment"] for entry in STATUS.values()}
    words["Any other headline"] = TOKENS["unknown_headline"]["treatment"]
    rows = table("### Shape grammar")
    assert [row[0] for row in rows] == list(words)
    for row in rows:
        treatment = words[row[0]]
        assert CODE.findall(row[1]) == [treatment], row[0]
        if row[0] != "Any other headline":
            assert plain(row[2]) == TOKENS["treatment"][treatment]["panel"], row[0]
            assert plain(row[3]) == TOKENS["treatment"][treatment]["screen"], row[0]


def test_nfr005_one_bit_collapse_mirrors_brand():
    rows = table("### 1-bit collapse")
    listed = {row[0]: CODE.findall(row[1]) for row in rows}
    assert set(listed) == {"paper", "ink", "dither-25"}
    for target, ids in listed.items():
        assert ids == [key for key, token in COLOR.items() if token["one_bit"] == target]
    # Backgrounds become paper; ink, Muted, Beam and every status color become ink.
    for key in ("fog", "surface", "paper"):
        assert COLOR[key]["one_bit"] == "paper"
    for key in ("ink", "muted", "beam", *STATUS_COLORS):
        assert COLOR[key]["one_bit"] == "ink"
    assert COLOR["line"]["one_bit"] == "dither-25"
    assert "dither-25" in TOKENS["texture"]


def test_nfr005_textures_match_their_definitions():
    texture = {name: entry["cells"] for name, entry in TOKENS["texture"].items()}
    assert set(texture) == {"dither-12", "dither-25", "dither-50", "hatch-45"}
    for cells in texture.values():
        assert all(len(row) == len(cells) and set(row) <= {"#", "."} for row in cells)
    assert (len(texture["dither-12"]), len(ink_cells(texture["dither-12"]))) == (4, 2)
    assert (len(texture["dither-25"]), len(ink_cells(texture["dither-25"]))) == (2, 1)
    assert ink_cells(texture["dither-50"]) == {(0, 0), (1, 1)}
    # hatch-45: one rising diagonal, 1 px every 4 px, in the panel renderer's phase: it
    # inks the pixels where x + y is a multiple of 4.
    hatch = {(x, y) for x in range(4) for y in range(4) if (x + y) % 4 == 0}
    assert ink_cells(texture["hatch-45"]) == hatch
    rows = table("### Texture")
    assert {row[0]: plain(row[1]) for row in rows} == {
        name: " / ".join(cells) for name, cells in texture.items()
    }


def test_nfr005_status_colors_are_never_themeable():
    theme = TOKENS["theme"]
    assert theme["slots"] == ["background", "line", "foreground", "accent"]
    assert list(theme["defaults"]) == theme["slots"]
    for slot, token in theme["defaults"].items():
        assert token in COLOR, slot
        assert token not in STATUS_COLORS and token not in CHIPS, slot
    rows = table("### User themes")
    assert {row[0]: CODE.findall(row[1]) for row in rows} == {
        slot: [token] for slot, token in theme["defaults"].items()
    }


def test_nfr005_terminal_codes_keep_meaning_without_color():
    terminal = TOKENS["terminal"]
    sgr = terminal["sgr"]
    assert set(sgr) == set(STATUS)
    every = [*sgr.values(), terminal["unknown_headline"], terminal["stale_last_line"]]
    for codes in every:
        numbers = [int(code) for code in codes.split(";")]
        # Never dim, blink, rapid blink or bright black.
        assert not {2, 5, 6, 90} & set(numbers), codes
    first, last = (int(n) for n in terminal["color_codes"].split("-"))

    def without_color(codes):
        return ";".join(c for c in codes.split(";") if not first <= int(c) <= last)

    for level, codes in sgr.items():
        if level == "IN RANGE":
            assert without_color(codes) == ""
        else:
            assert without_color(codes), f"{level} has no cue left without color"
    for level in ("STALE", "NO DATA"):
        assert "7" in sgr[level].split(";")
    assert terminal["stale_last_line"] == "9"

    rows = table("### Terminal")
    expected = {**sgr, "Any other headline": terminal["unknown_headline"]}
    assert [row[0] for row in rows] == list(expected)
    for row in rows:
        codes = expected[row[0]]
        assert CODE.findall(row[1])[0] == codes, row[0]
        assert (CODE.findall(row[2]) or [row[2]])[0] == (without_color(codes) or "plain")
    stale_row = next(row for row in rows if row[0] == "STALE")
    assert "`9`" in stale_row[1] and "`9`" in stale_row[2]


def test_nfr005_proposals_are_labelled_and_unused():
    proposed = TOKENS["proposed"]
    assert {key: p["state"] for key, p in proposed.items()} == {
        "in-range-neutral": "proposed, not in use",
        "night-profile": "proposed, not in use",
    }
    assert "### Proposed, not in use" in DOC.splitlines()
    assert "#### IN RANGE neutral" in DOC.splitlines()
    assert "#### Night profile" in DOC.splitlines()
    # Until IN RANGE neutral is decided IN RANGE keeps its green; the neutral border is Ink.
    assert STATUS["IN RANGE"]["color"] == "in-range"
    assert proposed["in-range-neutral"]["border"] == "ink"
    night = proposed["night-profile"]["colors"]
    in_use = {token[theme] for token in COLOR.values() for theme in ("light", "dark")}
    assert not set(night.values()) & in_use
    rows = table("#### Night profile")
    assert {row[0]: HEX.findall(row[1]) for row in rows} == {
        key.replace("-", " ").capitalize(): [value] for key, value in night.items()
    }
    for row in rows:
        key = row[0].lower().replace(" ", "-")
        expected = [] if key == "background" else [quoted(night[key], night["background"])]
        assert RATIO.findall(row[2]) == expected, row[0]


def test_nfr005_night_profile_has_no_red_tint():
    # Red means LOW, so nothing but the low color itself may lean red at night.
    night = TOKENS["proposed"]["night-profile"]["colors"]
    for key in ("background", "text", "beam"):
        r, g, b = (int(night[key][i : i + 2], 16) for i in (1, 3, 5))
        chroma = (max(r, g, b) - min(r, g, b)) / 255
        if chroma < 0.1:
            continue  # a neutral grey has no tint
        hue = math.degrees(math.atan2(math.sqrt(3) * (g - b), 2 * r - g - b)) % 360
        assert 25 <= hue <= 335, f"night {key} {night[key]} leans red (hue {hue:.0f})"


# --- pixel icons -------------------------------------------------------------------


STATUS_ICONS = ("lamp-lit", "lamp-hatched", "lamp-empty", "cut-link")


def test_nfr005_icon_grids_are_well_formed():
    names = [entry["name"] for entry in ICONS]
    assert len(names) == len(set(names)), "icon names repeat"
    assert set(STATUS_ICONS) <= set(names)
    assert {"gear", "refresh", "mark-16", "mark-32"} <= set(names)
    for entry in ICONS:
        name, rows = entry["name"], entry["rows"]
        assert pixels.NAME.fullmatch(name), name
        if entry["kind"] == "icon":
            assert entry["size"] == 16, name
        else:
            assert entry["kind"] == "mark", name
            assert entry["size"] == int(name.removeprefix("mark-")), name
        size = entry["size"]
        assert len(rows) == size, f"{name} has {len(rows)} rows"
        for row in rows:
            assert len(row) == size and set(row) <= {"#", "."}, f"{name}: {row!r}"
        assert 0 < len(ink_cells(rows)) < size * size, name
        assert entry["use"].strip(), name


def test_nfr005_tokens_name_only_real_icons():
    names = {entry["name"] for entry in ICONS}
    used = {entry["icon"] for entry in STATUS.values()} | {TOKENS["unknown_headline"]["icon"]}
    assert used <= names
    assert used == set(STATUS_ICONS) - {"cut-link"}


def test_nfr005_lamp_states_share_one_outline_and_differ_inside():
    lit, hatched, empty = (ink_cells(icon(name)["rows"]) for name in STATUS_ICONS[:3])
    assert empty < lit and empty < hatched and lit != hatched
    flame, hatch = lit - empty, hatched - empty

    def has_block(cells):
        return any({(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= cells for x, y in cells)

    # Lit is a solid flame; hatched is thin diagonal lines, never a filled block.
    assert has_block(flame)
    assert not has_block(hatch)
    assert not any((x + 1, y) in hatch or (x, y + 1) in hatch for x, y in hatch)
    # The hatch rises like hatch-45 and runs 1 on, 3 off.
    assert len({x + y for x, y in hatch}) >= 2
    assert all((x + y) % 4 == min(x + y for x, y in hatch) % 4 for x, y in hatch)


@pytest.mark.parametrize("name", ["mark-16", "mark-32"])
def test_nfr005_marks_keep_their_arcs_and_sweep_right(name):
    entry = icon(name)
    cx, cy = entry["lamp_center"]
    groups = components(ink_cells(entry["rows"]))
    body = next(group for group in groups if (cx, cy) in group)
    arcs = [group for group in groups if group is not body]
    assert len(arcs) == entry["arcs"] == {"mark-16": 2, "mark-32": 3}[name]
    edge = math.radians(30)  # the sector is 30 degrees either side of horizontal
    for arc in arcs:
        centers = [(x + 0.5 - cx, cy - y - 0.5) for x, y in arc]  # from the lamp, y up
        assert all(dx > 0 for dx, _ in centers), "an arc sits left of the lamp"
        # Pixel tolerance: a 2-cell stroke a few cells from the lamp cannot hold 60
        # degrees exactly, so the end cell of an arc may straddle the sector's edge,
        # with its center at most half a cell outside it (mark-16's inner arc needs
        # 0.42), and only one cell at each end may lie outside at all.
        outside = [abs(dy) * math.cos(edge) - dx * math.sin(edge) for dx, dy in centers]
        assert max(outside) <= 0.5, "an arc leaves the 60 degree sector"
        assert sum(distance > 0 for distance in outside) <= 2, "an arc overruns the sector"
        angles = [math.degrees(math.atan2(dy, dx)) for dx, dy in centers]
        assert max(angles) >= 24 and min(angles) <= -24, "an arc stops short of the sweep"
        assert {(x, 2 * cy - 1 - y) for x, y in arc} == arc, "an arc is not symmetric"


def test_nfr005_brand_icon_table_mirrors_pixel_icons():
    rows = table("### Icons and marks")
    assert [CODE.findall(row[1]) for row in rows] == [[entry["name"]] for entry in ICONS]
    for row in rows:
        (image,) = re.findall(r"\]\(([^)]+)\)", row[0])
        assert (BRAND.parent / image).resolve().is_file(), image
        assert image.endswith(pixels.png_name(CODE.findall(row[1])[0], 4))


def test_nfr005_committed_pixel_pngs_are_up_to_date(tmp_path):
    generated = pixels.build(tmp_path)
    assert len(generated) == len(ICONS) * len(pixels.SCALES)
    for path in generated:
        relative = path.relative_to(tmp_path)
        committed = ROOT / relative
        assert committed.exists(), f"{relative} is missing; run tools/gen_brand_pixels.py"
        same = png_content(committed.read_bytes()) == png_content(path.read_bytes())
        assert same, f"{relative} is out of date; run tools/gen_brand_pixels.py"
    expected = {path.name for path in generated}
    committed_names = {path.name for path in (ROOT / pixels.PNG_DIR).glob("pixel-*.png")}
    assert committed_names == expected, "delete PNGs for icons that no longer exist"


@pytest.mark.parametrize("entry", ICONS, ids=[entry["name"] for entry in ICONS])
def test_nfr005_pixel_pngs_show_their_grids(entry):
    cells = ink_cells(entry["rows"])
    for scale in pixels.SCALES:
        data = (ROOT / pixels.PNG_DIR / pixels.png_name(entry["name"], scale)).read_bytes()
        width, height, ink = png_ink(data)
        assert width == height == entry["size"] * scale
        assert ink == {
            (x * scale + dx, y * scale + dy)
            for x, y in cells
            for dx in range(scale)
            for dy in range(scale)
        }


DOT = {"name": "dot", "size": 2, "rows": ["#.", ".#"]}


@pytest.mark.parametrize(
    "icons",
    [
        [{**DOT, "rows": ["#.", "#"]}],
        [{**DOT, "rows": ["#."]}],
        [{**DOT, "rows": ["#.", ".x"]}],
        [{**DOT, "name": "Bad_Name"}],
        [DOT, DOT],
        [{**DOT, "size": 0, "rows": []}],
        [{**DOT, "name": 7}],
        [{**DOT, "size": "2"}],
        [{**DOT, "size": True, "rows": ["#"]}],
        [{**DOT, "rows": [["#", "."], [".", "#"]]}],
        [{"name": "dot", "size": 2}],
    ],
    ids=[
        "short row",
        "missing row",
        "odd character",
        "bad name",
        "repeated name",
        "empty grid",
        "non-string name",
        "non-integer size",
        "boolean size",
        "rows not strings",
        "no rows",
    ],
)
def test_nfr005_generator_refuses_malformed_grids(tmp_path, icons):
    path = tmp_path / "pixel-icons.json"
    path.write_text(json.dumps({"icons": icons}), encoding="utf-8")
    with pytest.raises(SystemExit):
        pixels.load_icons(path)
    path.write_text(json.dumps({"icons": [DOT]}), encoding="utf-8")
    assert pixels.load_icons(path) == [DOT]
