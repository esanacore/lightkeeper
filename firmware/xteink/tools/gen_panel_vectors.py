"""Turn spec/panel_vectors.json into a C++ include for the panel host tests.

Run by the Makefile, so the firmware rasterizer is always checked against the
same pixel vectors as the Python suite. The include defines the row types
(ROW_TYPES, so each row's fields are declared next to the code that fills
them), then:

- kPanelCases: every case in the spec (each display vector at each panel
  profile, plus the stamped cases) with its CRC-32 and ink count;
- kSpecProfiles, kSpecTreatments and kSpecIntConstants / kSpecTextConstants:
  the spec's tables, which the test compares with the C++ constants;
- kExtraCases, kSizeChecks, kStampChecks and kEpdCases: inputs the spec does
  not pin (stamps at every profile, unknown headlines, more lines than a
  screen has, edge and odd sizes, characters outside the font, the panel's
  portrait buffer), drawn or judged here by the Python reference
  (src/lightkeeper/infrastructure), so the C++ is held to Python beyond the
  spec too.

Usage: python gen_panel_vectors.py <panel_vectors.json> <out.inc>
"""

import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from lightkeeper.infrastructure import panel_layout  # noqa: E402
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap  # noqa: E402

LINE_SLOTS = 8  # lk::kMaxPanelLines: every case's lines array is padded to this
MAX_LINE_CHARS = 64  # lk::kMaxPanelLineChars

ROW_TYPES = f"""\
static_assert(lk::kMaxPanelLines == {LINE_SLOTS} && lk::kMaxPanelLineChars == {MAX_LINE_CHARS},
              "tools/gen_panel_vectors.py writes cases within the rasterizer's limits");

// One image to draw and the CRC-32 and ink count Python gives it.
struct PanelCase {{
  const char* vector;
  const char* profile;  // "custom" for a size no profile has
  int width;
  int height;
  int line_count;
  const char* lines[lk::kMaxPanelLines];
  const char* stamp;  // nullptr: no stamp
  uint32_t crc32;
  uint32_t ink;
}};

struct SpecProfile {{
  const char* name;
  int width;
  int height;
}};

struct SpecTreatment {{
  const char* headline;
  const char* kind;
}};

struct SpecIntConstant {{
  const char* name;
  int value;
}};

struct SpecTextConstant {{
  const char* name;
  const char* value;
}};

// An image and the CRC-32 and length of Python's Bitmap.to_epd_buffer() for it.
struct EpdCase {{
  const char* name;
  int width;
  int height;
  int line_count;
  const char* lines[lk::kMaxPanelLines];
  const char* stamp;
  uint32_t crc32;
  uint32_t length;
}};

// Whether panel_layout.check_size accepts a size.
struct SizeCheck {{
  int width;
  int height;
  bool ok;
}};

// Whether panel_layout.check_stamp accepts a stamp.
struct StampCheck {{
  const char* stamp;
  bool ok;
}};
"""

# Vectors drawn with a stamp at every profile: an age-row stamp where it fits,
# and the bottom strip where there is no age line or no room beside it.
STAMP = "12:34"
STAMPED_VECTORS = [
    "in_range_flat",
    "low_69",
    "urgent_high_250",
    "sensor_low_sentinel",
    "stale_at_16_minutes",
    "future_dated",
    "no_data_unreachable",
    "last_good_while_unreachable",
]

STALE = ["STALE - DO NOT TRUST", "last: 120 mg/dL ->", "16 min ago", "Confirm on primary device"]
NO_DATA = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
FRESH = ["IN RANGE", "112 mg/dL ->", "3 min ago"]

# (name, lines, width, height, stamp): inputs no display vector reaches.
EXTRA = [
    (
        "unknown_headline_is_dashed",
        ["CHECK NIGHTSCOUT", "112 mg/dL ->", "3 min ago"],
        296,
        128,
        None,
    ),
    ("lowercase_headline_is_dashed", ["in range", "112 mg/dL ->", "3 min ago"], 296, 128, None),
    (
        "headline_with_a_space_is_dashed",
        ["IN RANGE ", "112 mg/dL ->", "3 min ago"],
        400,
        300,
        None,
    ),
    ("headline_only", ["URGENT LOW"], 296, 128, None),
    ("value_without_age_shrinks_to_fit", ["IN RANGE", "112 mg/dL ->"], 300, 78, None),
    # Wide and short with no context line: the hero shrinks to the age, then the age shrinks.
    ("fresh_without_context_shrinks_the_age", FRESH, 4096, 100, None),
    ("stale_headline_only_has_no_strike", ["STALE - DO NOT TRUST"], 200, 200, None),
    ("empty_lines", ["", "", ""], 200, 200, None),
    ("eight_lines_shrink_to_fit", [*FRESH, "one", "two", "three", "four", "five"], 250, 122, None),
    ("eight_stale_lines", [*STALE, "a", "b", "c", "d"], 157, 70, "00:00"),
    ("eight_dashed_lines", ["NO DATA", *"abcdefg"], 296, 128, "23:59"),
    ("long_line_clipped_at_the_edge", ["NO DATA", "x" * MAX_LINE_CHARS], 200, 200, None),
    ("long_headline_clipped_at_the_edge", ["W" * MAX_LINE_CHARS, "1 min ago"], 200, 200, None),
    (
        "bytes_outside_the_font_draw_as_fallback",
        ["IN RANGE", "\t120\x7f mg/dL", "\x01"],
        296,
        128,
        None,
    ),
    ("smallest_panel", [*NO_DATA, "Nightscout unreachable"], 157, 70, "23:59"),
    ("smallest_panel_rule", ["LOW", "69 mg/dL v", "2 min ago"], 157, 70, "07:30"),
    ("smallest_panel_stale", STALE, 157, 70, "07:30"),
    ("odd_size", FRESH, 203, 77, "19:05"),
    ("odd_size_stale", STALE, 211, 93, None),
    ("tall_portrait", STALE, 700, 2400, "06:45"),
    ("wide_strip", ["URGENT HIGH", "250 mg/dL ^^", "2 min ago"], 4096, 200, None),
    ("largest_panel", STALE, 4096, 4096, "00:01"),
]

# Panel profiles whose portrait buffers are checked against Bitmap.to_epd_buffer.
EPD = [
    ("in_range_flat", FRESH, 296, 128, None),
    ("stale_at_16_minutes", STALE, 250, 122, None),
    ("no_data", NO_DATA, 200, 200, None),
    ("urgent_low_55_stamped", ["URGENT LOW", "55 mg/dL vv", "1 min ago"], 400, 300, "02:14"),
    ("stale_kindle_portrait", STALE, 600, 800, None),
    ("odd_size", FRESH, 203, 77, "19:05"),
]

STAMPS = [
    "00:00",
    "23:59",
    "12:34",
    "09:05",
    "19:59",
    "20:00",
    "24:00",
    "29:00",
    "30:00",
    "2:14",
    "02:4",
    "02:60",
    "02:6x",
    "02-14",
    "02:14 ",
    " 02:14",
    "02:14\n",
    "",
    "ab:cd",
    "0a:00",
    "00:a0",
    "1:234",
    "002:14",
    "０２:14",  # full-width digits are not digits here
    "/0:00",
    ":0:00",
    "00:/0",
    "00:6/",
    "12:3a",
    "12:3/",
    "12:3:",
]


def c_str(text):
    """Return `text` as a C++ string literal, or nullptr for None.

    Anything outside printable ASCII becomes three-digit octal escapes of its
    UTF-8 bytes (a hex escape could swallow the next character), and '?' is
    escaped so no trigraph can form.
    """
    if text is None:
        return "nullptr"
    out = []
    for char in text:
        if char in '"\\?':
            out.append("\\" + char)
        elif 0x20 <= ord(char) < 0x7F:
            out.append(char)
        else:
            out.extend(f"\\{byte:03o}" for byte in char.encode("utf-8"))
    return '"' + "".join(out) + '"'


def lines_init(lines):
    """Return the padded C++ initializer for a case's lines."""
    if not 1 <= len(lines) <= LINE_SLOTS:
        raise ValueError(f"a case has 1 to {LINE_SLOTS} lines, not {len(lines)}")
    for line in lines:
        if len(line) > MAX_LINE_CHARS or not line.isascii() or "\0" in line:
            raise ValueError(f"line {line!r} is not at most {MAX_LINE_CHARS} ASCII characters")
    slots = [c_str(line) for line in lines] + ["nullptr"] * (LINE_SLOTS - len(lines))
    return "{" + ", ".join(slots) + "}"


def case_init(name, profile, width, height, lines, stamp, crc, ink):
    """One C++ PanelCase initializer."""
    fields = [c_str(name), c_str(profile), str(width), str(height), str(len(lines))]
    fields += [lines_init(lines), c_str(stamp), f"{crc}u", f"{ink}u"]
    return "    {" + ", ".join(fields) + "},"


def draw(lines, width, height, stamp):
    """Return the Python reference's packed rows and ink count for one input."""
    bitmap = render_bitmap(lines, width, height, stamp)
    return bitmap, bitmap.to_packed_rows(), sum(bitmap.ink)


def size_samples(profiles):
    """Sizes to judge: the profiles, the edges of what check_size accepts, and a scatter."""
    sizes = {(p["width"], p["height"]) for p in profiles.values()}
    sizes |= {(0, 0), (-1, 100), (100, -1), (1, 1), (4096, 4096), (4097, 4096), (4096, 4097)}
    heights = [*range(1, 130), *range(130, 4097, 37), 479, 480, 481, 719, 720, 1439, 1440, 4095]
    heights += [4096, 4097]
    for height in heights:
        edge = panel_layout.margin(max(1, height))
        narrowest = panel_layout.min_content_width() + 2 * edge
        sizes |= {(narrowest + d, height) for d in (-1, 0, 1)} | {(4096, height)}
    state = 0x2545F491  # xorshift32, so the scatter is the same on every run
    for _ in range(600):
        pair = []
        for _ in range(2):
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= state >> 17
            state ^= (state << 5) & 0xFFFFFFFF
            pair.append(state % 4200 - 50)
        sizes.add((pair[0], pair[1]))
    return sorted(sizes)


def accepted(check, *args):
    """Return whether the Python check accepts its arguments."""
    try:
        check(*args)
    except ValueError:
        return False
    return True


def main(src, dst):
    """Write every table the panel host test needs from `src` to `dst`."""
    spec = json.loads(Path(src).read_text(encoding="utf-8"))
    profiles = spec["profiles"]
    version = int(spec["panel_spec_version"])
    out = [
        "// Generated from spec/panel_vectors.json by tools/gen_panel_vectors.py. Do not edit.",
        f"// panel_spec_version {version}",
        ROW_TYPES,
        f"const int kPanelSpecVersion = {version};",
        "const PanelCase kPanelCases[] = {",
    ]
    for case in spec["cases"]:
        out.append(
            case_init(
                case["vector"],
                case["profile"],
                case["width"],
                case["height"],
                case["lines"],
                case.get("stamp"),
                case["crc32"],
                case["ink"],
            )
        )
    out.append("};")

    out.append("const SpecProfile kSpecProfiles[] = {")
    for name, size in profiles.items():
        out.append(f"    {{{c_str(name)}, {size['width']}, {size['height']}}},")
    out.append("};")
    out.append("const SpecTreatment kSpecTreatments[] = {")
    for headline, kind in spec["treatments"].items():
        out.append(f"    {{{c_str(headline)}, {c_str(kind)}}},")
    out.append("};")
    out.append(f"const char* const kSpecUnknownTreatment = {c_str(spec['unknown_treatment'])};")
    constants = spec["layout"]["constants"]
    numbers = {k: v for k, v in constants.items() if isinstance(v, int)}
    texts = {k: v for k, v in constants.items() if isinstance(v, str)}
    out.append("const SpecIntConstant kSpecIntConstants[] = {")
    out += [f"    {{{c_str(name)}, {value}}}," for name, value in numbers.items()]
    out.append("};")
    out.append("const SpecTextConstant kSpecTextConstants[] = {")
    out += [f"    {{{c_str(name)}, {c_str(value)}}}," for name, value in texts.items()]
    out.append("};")

    by_name = {case["vector"]: case["lines"] for case in spec["cases"]}
    extra = [
        (f"{vector}_stamped", by_name[vector], profile, size["width"], size["height"], STAMP)
        for vector in STAMPED_VECTORS
        for profile, size in profiles.items()
    ]
    extra += [(name, lines, "custom", w, h, stamp) for name, lines, w, h, stamp in EXTRA]
    largest = 0
    out.append("const PanelCase kExtraCases[] = {")
    for name, lines, profile, width, height, stamp in extra:
        _, rows, ink = draw(lines, width, height, stamp)
        largest = max(largest, len(rows))
        out.append(case_init(name, profile, width, height, lines, stamp, zlib.crc32(rows), ink))
    out.append("};")
    out.append(f"const size_t kLargestExtraBytes = {largest};")

    out.append("const EpdCase kEpdCases[] = {")
    for name, lines, width, height, stamp in EPD:
        bitmap, _, _ = draw(lines, width, height, stamp)
        epd = bitmap.to_epd_buffer()
        fields = [c_str(name), str(width), str(height), str(len(lines)), lines_init(lines)]
        fields += [c_str(stamp), f"{zlib.crc32(epd)}u", f"{len(epd)}u"]
        out.append("    {" + ", ".join(fields) + "},")
    out.append("};")

    out.append("const SizeCheck kSizeChecks[] = {")
    for width, height in size_samples(profiles):
        ok = accepted(panel_layout.check_size, width, height)
        out.append(f"    {{{width}, {height}, {'true' if ok else 'false'}}},")
    out.append("};")
    out.append("const StampCheck kStampChecks[] = {")
    for stamp in STAMPS:
        ok = accepted(panel_layout.check_stamp, stamp)
        out.append(f"    {{{c_str(stamp)}, {'true' if ok else 'false'}}},")
    out.append("};")

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
