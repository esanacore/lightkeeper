"""FR-011, FR-016, FR-017, NFR-005, HAZ-013: the demo page draws real panel pixels, honestly.

demo.html is one file. tools/gen_demo_panel.py copies web/panel/panel.js (the
browser port of the panel rasterizer), the Keeper 5x8 font, the spoken
sentences, the lamp icons and the panel profiles into it. These tests keep
that copy current, hold the page to the small-web rules (one file of 512 KB
or less that loads nothing), check its colors against
assets/brand/tokens.json, and run the port's own Node tests, plus parity
checks against the Python reference at sizes and lines the pixel vectors do
not pin.

If the block test fails, run `python tools/gen_demo_panel.py` and commit the
result. The Node tests need Node 20 or later: they are skipped where node is
missing, except on CI (CI=true), where a missing node fails.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import zlib
from pathlib import Path
from urllib.parse import unquote

import pytest

from lightkeeper.application.status_payload import status_payload
from lightkeeper.domain.glucose import parse_entries
from lightkeeper.domain.status import classify
from lightkeeper.infrastructure import panel_layout as pl
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap
from lightkeeper.infrastructure.panel_profiles import DEFAULT_PROFILE, PROFILES
from tests.helpers import NOW
from tests.test_brand_tokens import contrast
from tests.test_vectors import raw_entries, thresholds

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "gen_demo_panel", ROOT / "tools" / "gen_demo_panel.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def committed(relative):
    """Read a committed file's text, whatever line endings the checkout gave it."""
    return (ROOT / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


PAGE = committed("demo.html")
PANEL_JS = committed("web/panel/panel.js")
TOKENS = json.loads(committed("assets/brand/tokens.json"))
COLOR = TOKENS["color"]
FONT = json.loads(committed("spec/font5x8.json"))
SPOKEN = json.loads(committed("spec/spoken_vectors.json"))["cases"]
ICONS = {icon["name"]: icon["rows"] for icon in json.loads(committed(gen.ICONS))["icons"]}
VECTORS = json.loads(committed("spec/display_vectors.json"))["cases"]
DISPLAY = {case["name"]: case for case in VECTORS}

STYLE = PAGE[PAGE.index("<style>") + len("<style>") : PAGE.index("</style>")]
SCRIPT = PAGE[PAGE.rindex("<script>") + len("<script>") : PAGE.rindex("</script>")]
# The page's own script: everything after the generated panel block.
PAGE_SCRIPT = SCRIPT[SCRIPT.index(gen.END) :]

# The states the page opens with, in order (LK-08): fresh, low, urgent, STALE
# beating an urgent low, an outage with a fresh value, an outage with none, and
# a sensor limit.
STORY = [
    "in_range_flat",
    "low_69",
    "urgent_low_55",
    "stale_beats_urgent_low",
    "last_good_while_unreachable",
    "no_data_unreachable",
    "sensor_low_sentinel",
]


def generated(name):
    """Parse the JSON value the page script assigns to `const name`."""
    marker = f"\n{gen.INDENT}const {name} = "
    start = PAGE.index(marker) + len(marker)
    value, end = json.JSONDecoder().raw_decode(PAGE, start)
    assert PAGE[end] == ";", name
    return value


def rules(css=STYLE):
    """Every innermost CSS rule as (selector, {property: value}), comments removed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = {}
        for item in body.split(";"):
            if item.strip():
                prop, value = item.split(":", 1)
                declarations[prop.strip()] = " ".join(value.split())
        found.append((" ".join(selector.split()), declarations))
    return found


def rule(selector):
    """Return the declarations of the first rule with exactly `selector` (top level first)."""
    for found, declarations in rules():
        if found == selector:
            return declarations
    raise AssertionError(f"no CSS rule for {selector!r}")


def custom_properties(selector):
    """Return the custom properties a rule declares, without their leading dashes."""
    return {prop[2:]: value for prop, value in rule(selector).items() if prop.startswith("--")}


# --- the generated block ----------------------------------------------------------


def test_fr016_demo_panel_block_is_current():
    for relative, text in gen.build().items():
        assert committed(relative) == text, f"{relative} is stale: run tools/gen_demo_panel.py"


def test_fr016_inlined_script_is_panel_js_byte_for_byte():
    start = PAGE.index("\n", PAGE.index(gen.BEGIN)) + 1
    assert PAGE[start : start + len(PANEL_JS)] == PANEL_JS
    assert PAGE[start + len(PANEL_JS) :].startswith(f"{gen.INDENT}const font = ")
    assert PAGE.count(gen.BEGIN) == PAGE.count(gen.END) == 1


def test_fr016_inlined_font_equals_font5x8_json():
    assert generated("font") == FONT


def test_fr017_inlined_spoken_map_equals_spoken_vectors():
    assert generated("spoken") == SPOKEN
    assert set(SPOKEN) == set(generated("states")) == set(DISPLAY)


def test_fr016_inlined_profiles_lamps_and_states_match_their_sources():
    assert generated("profiles") == {
        p.name: {"width": p.width, "height": p.height, "description": p.description}
        for p in PROFILES.values()
    }
    assert generated("defaultProfile") == DEFAULT_PROFILE
    assert generated("lampIcons") == {name: ICONS[name] for name in gen.LAMPS}
    assert generated("states") == {
        name: {"level": case["level"], "lines": case["lines"]} for name, case in DISPLAY.items()
    }


def test_fr011_page_is_one_file_of_512_kb_or_less_and_says_so():
    size = len(PAGE.encode("utf-8"))
    assert size <= 512 * 1024 == gen.PAGE_BUDGET
    assert generated("pageBytes") == size
    assert 'id="page-weight"' in PAGE


# --- small-web rules ----------------------------------------------------------------


def test_fr011_page_loads_nothing_from_anywhere():
    assert re.search(r"<script\b[^>]*\bsrc\s*=", PAGE, re.I) is None
    assert re.search(r"\ssrc\s*=", PAGE, re.I) is None
    for tag in re.findall(r"<link\b[^>]*>", PAGE, re.I):
        # The favicon is the only link, drawn inline from the mono mark.
        assert 'rel="icon"' in tag and 'href="data:image/svg+xml,' in tag, tag
    for tag in ("<img", "<iframe", "<embed", "<object", "<video", "<audio", "<source", "<base"):
        assert tag not in PAGE.lower(), tag
    assert "@import" not in PAGE
    assert "@font-face" not in PAGE  # D13: no font files ship
    assert re.search(r"url\(\s*[\"']?\s*(https?:)?//", PAGE, re.I) is None
    for call in (
        "fetch(",
        "import(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "Worker(",
        "sendBeacon",
        "serviceWorker",
        "document.cookie",
        "eval(",
    ):
        assert call not in SCRIPT, call
    assert re.search(r"^\s*(import|export)\b", SCRIPT, re.M) is None
    # A URL anywhere else is a link to read, the page's own address, or a namespace.
    for url in re.findall(r"https?://[^\s\"'<>)]+", PAGE):
        assert (
            url == "http://www.w3.org/2000/svg"
            or f'href="{url}"' in PAGE
            or f'property="og:url" content="{url}"' in PAGE
        ), url


def test_fr011_page_works_without_storage_and_keeps_no_cookies():
    lines = PAGE_SCRIPT.splitlines()
    uses = [i for i, line in enumerate(lines) if "localStorage" in line]
    assert len(uses) == 2  # read the view choice, and remember it
    for i in uses:
        assert lines[i - 1].strip() == "try {", lines[i]
        assert lines[i + 1].strip().startswith("} catch"), lines[i]
    for store in ("sessionStorage", "indexedDB", "cookie"):
        assert store not in SCRIPT


def test_fr011_nothing_moves_blinks_ticks_or_sounds():
    for timer in ("setInterval", "setTimeout", "requestAnimationFrame"):
        assert timer not in SCRIPT, timer
    for loud in ("Audio(", "AudioContext", "vibrate", "Notification", "speechSynthesis"):
        assert loud not in SCRIPT, loud
    assert "@keyframes" not in STYLE and "blink" not in STYLE
    assert "<blink" not in PAGE.lower() and "<marquee" not in PAGE.lower()
    for _, declarations in rules():
        assert declarations.get("animation", "none !important") == "none !important"
        assert declarations.get("transition", "none !important") == "none !important"
    reduced = STYLE[STYLE.index("@media (prefers-reduced-motion: reduce)") :]
    assert "animation: none !important" in reduced and "transition: none !important" in reduced


# --- accessibility --------------------------------------------------------------------


def test_fr011_live_region_is_polite_and_holds_spans_only():
    outputs = re.findall(r"<output\b[^>]*>(.*?)</output>", PAGE, re.S)
    assert outputs == [""], "one live region, filled by the page script"
    tag = re.search(r"<output\b[^>]*>", PAGE).group(0)
    assert 'role="status"' in tag and 'aria-live="polite"' in tag
    assert "assertive" not in PAGE
    # Every element the page script makes is named here: no div in the live region.
    assert 'createElement("div")' not in SCRIPT
    assert '"line struck" : "line", line)' in PAGE_SCRIPT
    assert 'textBlock("span", "sr-only", sentence)' in PAGE_SCRIPT
    assert rule(".result .line")["display"] == "block"


def test_fr011_text_view_strikes_the_stale_last_line():
    # The text view is a screen surface too: STALE's 'last:' line is struck, in
    # Muted at body size, never shown like the age line under it.
    speak = PAGE_SCRIPT[PAGE_SCRIPT.index("function speak(") :]
    speak = speak[: speak.index("\n      }\n")]
    assert "const struck = P.glance(lines).struck;" in speak
    assert 'index === 1 && struck !== null ? "line struck" : "line"' in speak
    struck = rule(".struck")
    assert struck["text-decoration"] == "line-through" and struck["color"] == "var(--muted)"
    assert "font-size" not in struck and "font-size" not in rule(".result .line")
    # Muted is readable on the panel paper the text view sits on, in both themes.
    for theme, paper in (("light", "paper"), ("dark", "night-paper")):
        assert contrast(COLOR["muted"][theme], COLOR[paper][theme]) >= 4.5, theme
    # The rule the page follows is the phone card's: only STALE has a struck line.
    stale = [c for c in VECTORS if c["level"] == "STALE"]
    assert stale and all(pl.treatment(c["lines"][0]) == "stale" for c in stale)
    assert all(c["lines"][1].startswith("last: ") for c in stale)


def test_fr011_wide_panels_scroll_in_a_named_box_a_keyboard_can_reach():
    for box, name in (("bezel-view", "Panel preview"), ("mini-view", "Bedside panel preview")):
        tag = re.search(rf'<div class="[a-z-]+" id="{box}"[^>]*>', PAGE).group(0)
        assert f'role="group" aria-label="{name}"' in tag, tag
        assert "tabindex" not in tag  # a tab stop only while it scrolls
    assert "scrollStop(bezelView);" in PAGE_SCRIPT and "scrollStop(miniView);" in PAGE_SCRIPT
    stop = PAGE_SCRIPT[PAGE_SCRIPT.index("function scrollStop(") :]
    stop = stop[: stop.index("\n      }\n")]
    assert "box.scrollWidth > box.clientWidth) box.tabIndex = 0;" in stop
    assert 'else box.removeAttribute("tabindex");' in stop
    focus = rule(".bezel-view:focus-visible, .scroll:focus-visible")
    assert (focus["outline"], focus["outline-offset"]) == ("2px solid var(--beam)", "2px")
    assert rule(".bezel-view, .scroll")["overflow-x"] == "auto"


def test_fr016_panels_are_drawn_in_whole_screen_pixels():
    # At 125% or 150% display scaling a CSS pixel is not a whole screen pixel,
    # so each panel pixel covers a whole number of device pixels instead.
    pixels = PAGE_SCRIPT[PAGE_SCRIPT.index("function screenPixels(") :]
    pixels = pixels[: pixels.index("\n      }\n")]
    assert "Math.max(1, Math.floor((window.devicePixelRatio || 1) * scale + 1e-6))" in pixels
    # The CSS size is that many screen pixels, plus 1/256 of one so a browser
    # that truncates lengths to its 1/64 layout unit still lands on the whole.
    size = PAGE_SCRIPT[PAGE_SCRIPT.index("function sizeCanvas(") :]
    size = size[: size.index("\n      }\n")]
    for side in ("width", "height"):
        assert f"canvas.style.{side} = `${{(size.{side} * pixels + 1 / 256) / ratio}}px`;" in size
    assert "sizeCanvas(panel, size, pixels);" in PAGE_SCRIPT
    assert "sizeCanvas(mini, profiles[defaultProfile], screenPixels(1));" in PAGE_SCRIPT
    # Every other write of a canvas's CSS size would bypass the count.
    assert len(re.findall(r"\.style\.(width|height) =", PAGE_SCRIPT)) == 2
    # A new screen or zoom level fits the panels again.
    assert "(resolution: ${window.devicePixelRatio || 1}dppx)" in PAGE_SCRIPT
    assert "watchRatio();\n          fitPanel();" in PAGE_SCRIPT
    assert 'window.addEventListener("resize", fitPanel);\n      watchRatio();' in PAGE_SCRIPT
    # The canvases' own pixels stay one per panel pixel; only their CSS size changes.
    assert (
        "canvas.width = size.width;" in PAGE_SCRIPT
        and "canvas.height = size.height;" in PAGE_SCRIPT
    )


def test_fr011_canvases_are_hidden_from_assistive_tech_and_pixelated():
    canvases = re.findall(r"<canvas\b[^>]*>", PAGE)
    assert len(canvases) == 2
    for tag in canvases:
        assert 'aria-hidden="true"' in tag and 'width="296" height="128"' in tag
    assert rule("canvas")["image-rendering"] == "pixelated"


def test_fr011_promise_fails_visibly_and_simulated_labels_stay():
    assert "Fails loudly" not in PAGE
    assert "<strong>Fails visibly, not silently</strong>" in PAGE
    assert ">SIMULATED</span>" in PAGE
    assert "not a medical device" in PAGE
    assert "always confirm on the primary CGM app" in PAGE


def test_fr011_story_states_come_first_and_every_vector_is_one_click_away():
    start = PAGE_SCRIPT.index("const story = [")
    story = PAGE_SCRIPT[start : PAGE_SCRIPT.index("];", start)]
    assert re.findall(r'^\s*\["([a-z0-9_]+)", "', story, re.M) == STORY
    assert set(STORY) <= set(DISPLAY)
    assert 'const DEFAULT_STATE = "in_range_flat";' in PAGE_SCRIPT
    # The full set sits behind a disclosure, after the story.
    assert PAGE.index('id="story-choices"') < PAGE.index('<details id="all-states">')
    details = PAGE[PAGE.index('<details id="all-states">') : PAGE.index("</details>")]
    assert 'id="groups"' in details
    # A deep link goes through the port's chooser, which only ever names a real vector.
    assert "P.chooseState(location.hash, states, DEFAULT_STATE)" in PAGE_SCRIPT


def test_nfr005_controls_links_and_kicker_meet_their_contrast():
    button = rule("button")
    assert button["border"] == "2px solid var(--line-strong)"
    assert button["min-width"] == button["min-height"] == "44px"
    pressed = rule('button[aria-pressed="true"]')
    assert (pressed["background"], pressed["color"]) == ("var(--ink)", "var(--band-text)")
    focus = rule("button:focus-visible, summary:focus-visible, a:focus-visible")
    assert (focus["outline"], focus["outline-offset"]) == ("2px solid var(--beam)", "2px")
    assert rule("a")["color"] == rule(".kicker")["color"] == "var(--beam-text)"
    for theme in ("light", "dark"):
        for ground in ("fog", "surface"):
            back = COLOR[ground][theme]
            assert contrast(COLOR["line-strong"][theme], back) >= 3, (theme, ground)
            assert contrast(COLOR["beam"][theme], back) >= 3, (theme, ground)
            assert contrast(COLOR["beam-text"][theme], back) >= 4.5, (theme, ground)
            assert contrast(COLOR["muted"][theme], back) >= 4.5, (theme, ground)
        assert contrast(COLOR["band-text"][theme], COLOR["ink"][theme]) >= 7, theme
    # The panel preview: Ink on Paper in light, night ink on night paper in dark.
    assert contrast(COLOR["ink"]["light"], COLOR["paper"]["light"]) >= 7
    assert contrast(COLOR["night-ink"]["dark"], COLOR["night-paper"]["dark"]) >= 7


def test_nfr005_chip_tones_and_lamps_follow_tokens_json():
    status = TOKENS["status"].values()
    assert generated("tones") == {entry["word"]: entry["color"] for entry in status}
    assert generated("lamps") == {entry["treatment"]: entry["icon"] for entry in status}
    unknown = TOKENS["unknown_headline"]
    assert generated("UNKNOWN_TONE") == unknown["color"]
    assert generated("lamps")[unknown["treatment"]] == unknown["icon"]
    css_name = {token: css for css, token in CSS_TO_TOKEN.items()}
    for entry in status:
        tone = rule(f'[data-tone="{entry["color"]}"]')
        assert tone["--tone"] == f"var(--{entry['color']})"
        assert tone["--tint"] == f"var(--{css_name.get(entry['chip'], entry['chip'])})"


def test_fr011_every_profile_has_a_picker_label():
    labels = generated("profileLabels")
    assert list(labels) == list(PROFILES)
    assert labels["waveshare_7in5"] == "7.5-inch / TRMNL"


def test_nfr005_forced_colors_keep_the_chip_word_and_border():
    # Under forced colors only borders and words survive, so every chip has a
    # border of its own and its word as text (the lamp follows the text color).
    assert rule(".chip")["border"] == "2px solid var(--tone)"
    assert rule('[data-shape="dashed"] .chip')["border"] == "2px dashed var(--line-strong)"
    assert 'path.setAttribute("fill", "currentColor")' in PAGE_SCRIPT
    assert "document.createTextNode(headline)" in PAGE_SCRIPT
    forced = STYLE[STYLE.index("@media (forced-colors: active) {") :]
    assert "Highlight" in forced[: forced.index("\n      }\n")]


def test_fr011_phone_mock_banner_outranks_the_number():
    sizes = {
        name: float(value.removesuffix("rem"))
        for name, value in custom_properties(".phone").items()
    }
    assert sizes["phone-chip"] >= 1.25  # never below .title3 semibold
    assert sizes["phone-hero"] > sizes["phone-chip"]  # a fresh number is the hero
    assert sizes["phone-banner"] > sizes["phone-urgent-hero"]  # URGENT: the banner is largest
    assert sizes["phone-banner"] >= sizes["phone-chip"]
    banner = '.phone .chip-frame:not([data-shape="plain"]):not([data-shape="rule"]) .chip'
    assert rule(banner)["font-size"] == "var(--phone-banner)"
    assert rule(".phone .chip")["font-size"] == "var(--phone-chip)"
    assert rule(".hero .num")["font-size"] == "var(--phone-hero)"
    urgent = '.phone .chip-frame[data-shape="inverse"] ~ .hero .num'
    assert rule(urgent)["font-size"] == rule(".hero .word")["font-size"]
    assert rule(".hero .word")["font-size"] == "var(--phone-urgent-hero)"
    # STALE's old value is struck, in Muted, at body size: never a hero.
    struck = rule(".struck")
    assert struck["text-decoration"] == "line-through" and struck["color"] == "var(--muted)"
    assert "font-size" not in struck
    assert "if (card.hero !== null)" in PAGE_SCRIPT


def test_fr011_spacing_snaps_to_the_4px_grid():
    spacing = re.compile(r"(margin|padding|gap|row-gap|column-gap|inset|top|right|bottom|left)")
    off = []
    for selector, declarations in rules():
        for prop, value in declarations.items():
            if spacing.fullmatch(prop.split("-")[0]) or spacing.fullmatch(prop):
                off += [
                    f"{selector} {{{prop}: {value}}}"
                    for px in re.findall(r"(\d+)px", value)
                    if int(px) % 4
                ]
    assert off == []


# --- colors and textures against tokens.json -----------------------------------------

CSS_TO_TOKEN = {"chip-inrange": "chip-in-range"}
PANEL_COLORS = {"panel-paper": ("paper", "night-paper"), "panel-ink": ("ink", "night-ink")}
SHADOW = {"light": "beam-soft", "dark": "line"}  # hard shadow: 3px 3px 0
TEXTURES = {  # CSS name: (texture in tokens.json, the color it is drawn in)
    "dither-12": ("dither-12", "line-strong"),
    "dither-25": ("dither-25", "line-strong"),
    "dither-50": ("dither-50", "line-strong"),
    "hatch": ("hatch-45", "stale"),
}
FONT_STACKS = {"display", "body", "mono"}


def texture(value):
    """(cells, fill) of a CSS texture: an inline SVG of 1 px squares."""
    match = re.fullmatch(r'url\("data:image/svg\+xml,([^"]+)"\)', value)
    assert match, value
    svg = unquote(match.group(1))
    assert "href" not in svg and "http://www.w3.org/2000/svg" in svg
    width = int(re.search(r"width='(\d+)'", svg).group(1))
    height = int(re.search(r"height='(\d+)'", svg).group(1))
    (fill,) = re.findall(r"fill='(#[0-9A-Fa-f]{6})'", svg)
    (path,) = re.findall(r" d='([^']+)'", svg)
    squares = re.findall(r"M(\d+) (\d+)h1v1h-1z", path)
    assert "".join(f"M{x} {y}h1v1h-1z" for x, y in squares) == path, path
    grid = [["."] * width for _ in range(height)]
    for x, y in squares:
        grid[int(y)][int(x)] = "#"
    return ["".join(row) for row in grid], fill.upper()


def expected_theme(theme):
    """Every custom property the page declares (fonts aside), with its value for `theme`."""
    css_name = {token: css for css, token in CSS_TO_TOKEN.items()}
    values = {css_name.get(token, token): COLOR[token][theme] for token in COLOR}
    for css, (light, dark) in PANEL_COLORS.items():
        values[css] = COLOR[light if theme == "light" else dark][theme]
    values["shadow-hard"] = f"3px 3px 0 {COLOR[SHADOW[theme]][theme]}"
    for css, (name, color) in TEXTURES.items():
        values[css] = (TOKENS["texture"][name]["cells"], COLOR[color][theme])
    return values


def actual(declared):
    """Return the declared properties: textures decoded, fonts set aside, hex upper case."""
    out = {}
    for name, value in declared.items():
        if name in FONT_STACKS:
            assert "url(" not in value, name
            continue
        out[name] = texture(value) if name in TEXTURES else value.upper().replace("PX", "px")
    return out


def test_nfr005_root_block_equals_tokens_json():
    light = expected_theme("light")
    declared = custom_properties(":root")
    assert set(declared) == set(light) | FONT_STACKS
    assert actual(declared) == {key: light[key] for key in light}


@pytest.mark.parametrize(
    "selector", [':root:not([data-theme="light"])', ':root[data-theme="dark"]']
)
def test_nfr005_both_dark_blocks_equal_tokens_json(selector):
    light, dark = expected_theme("light"), expected_theme("dark")
    changed = {key: value for key, value in dark.items() if value != light[key]}
    declared = custom_properties(selector)
    # Exactly what differs from light, so a value that should change cannot be forgotten.
    assert actual(declared) == changed
    # The panel preview uses night paper only (D16), so it is never the brightest thing.
    assert declared["panel-paper"] == COLOR["night-paper"]["dark"]
    assert declared["panel-ink"] == COLOR["night-ink"]["dark"]
    if selector.startswith(":root:not"):
        media = STYLE[: STYLE.index(selector)]
        assert media.rstrip().endswith("@media (prefers-color-scheme: dark) {")


def test_nfr005_textures_are_one_css_px_a_cell_and_only_in_the_margins():
    sizes = {css: len(TOKENS["texture"][name]["cells"]) for css, (name, _) in TEXTURES.items()}
    used = {}
    for selector, declarations in rules():
        image = declarations.get("background-image", "")
        match = re.fullmatch(r"var\(--([a-z0-9-]+)\)", image)
        if match:
            n = sizes[match.group(1)]
            assert declarations["background-size"] == f"{n}px {n}px", selector
            used.setdefault(match.group(1), []).append(selector)
    # Margins, bezels, headers and the STALE frame only: never under the words.
    assert used == {
        "dither-12": ["body"],
        "dither-25": [".bezel"],
        "dither-50": [".sec-head h2::before"],
        "hatch": ['.chip-frame[data-shape="stale"]'],
    }
    for selector in ("main", ".chip", ".result", ".sim"):
        assert rule(selector).get("background", rule(selector).get("background-color"))
    # Gone under more contrast, forced colors and print.
    plain = STYLE[
        STYLE.index("@media (prefers-contrast: more), (forced-colors: active), print {") :
    ]
    plain = plain[: plain.index("}")]
    for selectors in used.values():
        for selector in selectors:
            assert selector in plain, selector
    assert "background-image: none" in STYLE[STYLE.index("(prefers-contrast: more)") :]


# --- the port, run in Node -----------------------------------------------------------


def node_or_skip():
    """Return the node executable; skip without one, but fail on CI, where it must exist."""
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI", "").lower() == "true":
            pytest.fail("node is missing on CI: the demo's panel port must be tested there")
        pytest.skip("node is not installed: the demo's panel port tests need Node 20 or later")
    return node


def test_fr016_missing_node_skips_locally_and_fails_on_ci(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="missing on CI"):
        node_or_skip()
    monkeypatch.delenv("CI")
    with pytest.raises(pytest.skip.Exception, match="Node 20"):
        node_or_skip()


def test_fr016_node_tests_for_the_panel_port_pass():
    node = node_or_skip()
    result = subprocess.run(  # noqa: S603 - fixed arguments, the node on PATH
        [node, "--test", "web/panel/panel.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    assert re.search(r"^\S* ?fail 0$", result.stdout, re.M), result.stdout[-2000:]


# Loads the port the way the page does, then answers every request in a JSON file.
RUNNER = """
const fs = require("node:fs");
const vm = require("node:vm");
const request = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
vm.runInThisContext(fs.readFileSync(request.panel, "utf8"), { filename: "panel.js" });
const P = globalThis.LightkeeperPanel;
const font = JSON.parse(fs.readFileSync(request.font, "utf8"));
const answers = request.cases.map((c) => {
  if (c.ha) {
    return P.haGlucose(c.level, c.lines);
  }
  try {
    const options = c.stamp === null ? undefined : { stamp: c.stamp };
    const packed = P.renderPanel(c.lines, c.width, c.height, font, options);
    return [P.crc32(packed), P.inkCount(packed)];
  } catch (error) {
    return error instanceof RangeError ? "refused" : String(error);
  }
});
process.stdout.write(JSON.stringify(answers));
"""


def run_port(tmp_path, cases):
    """Ask the JavaScript port about each case; see RUNNER."""
    node = node_or_skip()
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "panel": str(ROOT / "web" / "panel" / "panel.js"),
                "font": str(ROOT / "spec" / "font5x8.json"),
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603 - fixed arguments, the node on PATH
        [node, "-e", RUNNER, str(request)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout)


def python_pixels(case):
    """Return what the Python reference draws for a case: [CRC-32, ink count] or 'refused'."""
    try:
        bitmap = render_bitmap(case["lines"], case["width"], case["height"], case["stamp"])
    except ValueError:
        return "refused"
    return [zlib.crc32(bitmap.to_packed_rows()), sum(bitmap.ink)]


def accepted(width, height):
    try:
        pl.check_size(width, height)
    except ValueError:
        return False
    return True


def narrowest(height):
    """Return the narrowest panel width the layout accepts at `height`."""
    return next(w for w in range(1, pl.MAX_SIDE + 1) if accepted(w, height))


def shortest(width):
    """Return the shortest panel height the layout accepts at `width`."""
    return next(h for h in range(1, pl.MAX_SIDE + 1) if accepted(width, h))


def parity_cases():
    """Sizes and lines spec/panel_vectors.json does not pin, accepted and refused."""
    narrow = [(narrowest(h), h) for h in (70, 96, 128, 177, 333)]
    short = [(w, shortest(w)) for w in (296, 1000)]
    sizes = [*narrow, *short, (333, 177), (480, 272), (1024, 758)]
    refused = [(w - 1, h) for w, h in narrow] + [(w, h - 1) for w, h in short]
    refused += [(0, 128), (296, 0), (4097, 128), (296, 4097)]
    odd = [
        ["MYSTERY", "112 mg/dL ->", "3 min ago"],
        ["IN RANGE"],
        ["STALE - DO NOT TRUST"],
        ["NO DATA"],
        ["IN RANGE", "112 mg/dL ->", "3 min ago", "one", "two", "three", "four", "five"],
        ["URGENT HIGH", "", "", ""],
        ["IN RANGE", "café ☃ 112", "3 min ago"],
        ["LOW", "W" * 60, "3 min ago"],
        ["STALE - DO NOT TRUST", "last: 45 mg/dL v", "40 min ago", "Confirm", "Nightscout"],
    ]
    vectors = [case["lines"] for case in VECTORS]
    cases = [
        {"lines": lines, "width": w, "height": h, "stamp": stamp}
        for w, h in sizes
        for lines in vectors + odd
        for stamp in (None, "23:59")
    ]
    cases += [{"lines": vectors[0], "width": w, "height": h, "stamp": None} for w, h in refused]
    return cases


def test_fr016_port_matches_python_beyond_the_pixel_vectors(tmp_path):
    cases = parity_cases()
    expected = [python_pixels(c) for c in cases]
    assert expected.count("refused") == 11  # every size just past an edge, and the extremes
    answers = run_port(tmp_path, cases)
    wrong = [
        f"{c['lines'][0]!r} at {c['width']}x{c['height']} stamp {c['stamp']}"
        for c, want, answer in zip(cases, expected, answers, strict=True)
        if answer != want
    ]
    assert wrong == []


def test_haz013_ha_tile_number_follows_status_payload(tmp_path):
    expected = []
    for case in VECTORS:
        readings = parse_entries(raw_entries(case))
        status = classify(readings[0] if readings else None, NOW, thresholds(case))
        expected.append(status_payload(status, case["error"], NOW)["mgdl"])
    cases = [{"ha": True, "level": c["level"], "lines": c["lines"]} for c in VECTORS]
    assert run_port(tmp_path, cases) == expected
    # The rule bites: some vectors publish a number, and STALE, NO DATA and sentinels do not.
    shown = {c["name"] for c, mgdl in zip(VECTORS, expected, strict=True) if mgdl is not None}
    assert "in_range_flat" in shown
    hidden = {"stale_beats_urgent_low", "no_data", "sensor_low_sentinel", "sensor_high_sentinel"}
    assert not shown & hidden


# --- the generator ------------------------------------------------------------------


def copy_sources(root):
    """Copy what the generator reads into a scratch repository root."""
    for relative in (gen.DEMO, gen.PANEL_JS, gen.FONT, gen.SPOKEN, gen.ICONS):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(committed(relative), encoding="utf-8", newline="\n")


def test_fr016_generator_check_reports_and_write_repairs(tmp_path, monkeypatch, capsys):
    copy_sources(tmp_path)
    stale = PAGE.replace(f"const pageBytes = {generated('pageBytes')};", "const pageBytes = 1;")
    (tmp_path / gen.DEMO).write_text(stale, encoding="utf-8", newline="\n")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    assert gen.main(["--check"]) == 1
    assert "out of date: demo.html" in capsys.readouterr().out
    assert gen.main([]) == 0
    assert "wrote demo.html" in capsys.readouterr().out
    assert gen.main(["--check"]) == 0
    written = (tmp_path / gen.DEMO).read_bytes()
    assert written == PAGE.encode("utf-8") and b"\r\n" not in written


@pytest.mark.parametrize(
    ("relative", "change", "message"),
    [
        (gen.PANEL_JS, lambda text: text.rstrip("\n"), "must end with a newline"),
        (gen.PANEL_JS, lambda text: text + "// </script>\n", "'</script'"),
        (gen.PANEL_JS, lambda text: text + "// <!-- x\n", "'<!--'"),
        (gen.PANEL_JS, lambda text: text + "// END GENERATED STATES\n", "where the page is cut"),
        (gen.DEMO, lambda text: text.replace(gen.END, "      // END"), "needs exactly one"),
        (gen.DEMO, lambda text: text + gen.BEGIN + "\n", "needs exactly one"),
        (
            gen.ICONS,
            lambda text: text.replace('"lamp-hatched"', '"lamp-other"'),
            "missing a lamp",
        ),
        (
            gen.SPOKEN,
            lambda text: text.replace("Just now.", "Just now.</script>", 1),
            "'</script'",
        ),
    ],
)
def test_fr016_generator_refuses_what_would_break_the_page(
    tmp_path, monkeypatch, relative, change, message
):
    copy_sources(tmp_path)
    path = tmp_path / relative
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match=re.escape(message)):
        gen.build()


def test_fr011_generator_refuses_a_page_over_budget(tmp_path, monkeypatch):
    copy_sources(tmp_path)
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    monkeypatch.setattr(gen, "PAGE_BUDGET", 1024)
    with pytest.raises(SystemExit, match="over the 1024 byte budget"):
        gen.build()
