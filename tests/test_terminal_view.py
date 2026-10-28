"""FR-006: the interactive --watch frame (docs/BRAND.md, Terminal).

Shape before hue: every status keeps a cue in monochrome (underline for LOW
and HIGH, reverse for the urgent levels, STALE, NO DATA and anything
unknown, strike for the STALE `last:` line), the codes come from
assets/brand/tokens.json, and nothing in a frame can ring the bell, blink,
or carry a byte that is not ASCII.
"""

import ctypes
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lightkeeper.infrastructure import terminal_view as tv
from lightkeeper.infrastructure.panel_layout import TREATMENTS

ROOT = Path(__file__).resolve().parent.parent
VECTORS = json.loads((ROOT / "spec" / "display_vectors.json").read_text(encoding="utf-8"))["cases"]
TOKENS = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))[
    "terminal"
]
# A naive time is local already, so the header reads 02:14:07 in every time zone.
# Mid-July, mid-week: no time zone skips 02:14 that night.
CHECKED = datetime(2026, 7, 15, 2, 14, 7)
HEADER = "o))) lightkeeper   checked 02:14:07"
RULE = "+" + "-" * 29 + "+"
FOOTER_80 = ["next check in 60s - Ctrl+C to stop", "secondary display, confirm on the primary app"]
SGR_PARAMS = re.compile("\x1b\\[([0-9;]*)m")
ESCAPE = re.compile("\x1b\\[[0-9;]*[A-Za-z]")


def level_of(headline):
    """tokens.json keys the codes by level; the display's STALE headline is longer."""
    return "STALE" if headline == "STALE - DO NOT TRUST" else headline


def color_codes():
    low, high = (int(part) for part in TOKENS["color_codes"].split("-"))
    return set(range(low, high + 1))


def expected_rows(lines, color):
    """Build the frame the brand rules describe from tokens.json, not from the module."""
    level = level_of(lines[0])
    codes = TOKENS["sgr"].get(level, TOKENS["unknown_headline"]).split(";")
    if not color:
        codes = [code for code in codes if int(code) not in color_codes()]

    def styled(text, params):
        return f"\x1b[{';'.join(params)}m{text}\x1b[0m" if params else text

    rows = [HEADER, RULE, f"|  {styled(lines[0].ljust(25), codes)}  |"]
    for index, line in enumerate(lines[1:], start=1):
        strike = level == "STALE" and index == 1
        body = styled(line, [TOKENS["stale_last_line"]] if strike else [])
        rows.append(f"|  {body}{' ' * (25 - len(line))}  |")
    return [*rows, RULE, *FOOTER_80]


def rows(lines, **kwargs):
    return tv.frame_rows(lines, CHECKED, 60, **kwargs)


# --- the codes are the brand's -------------------------------------------------------


def test_fr006_sgr_codes_match_the_brand_tokens():
    for headline, codes in tv.SGR.items():
        assert TOKENS["sgr"][level_of(headline)] == codes, headline
    assert {level_of(headline) for headline in tv.SGR} == set(TOKENS["sgr"])
    assert tv.UNKNOWN_SGR == TOKENS["unknown_headline"]
    assert tv.STALE_LAST_SGR == TOKENS["stale_last_line"]
    assert set(tv.COLOR_CODES) == color_codes()


def test_fr006_every_headline_the_panel_knows_has_codes():
    assert set(tv.SGR) == set(TREATMENTS)


@pytest.mark.parametrize(
    ("headline", "color", "codes"),
    [
        ("IN RANGE", True, "32"),
        ("IN RANGE", False, ""),
        ("LOW", False, "4"),
        ("HIGH", False, "4"),
        ("URGENT LOW", False, "1;7"),
        ("URGENT HIGH", True, "1;7;33"),
        ("STALE - DO NOT TRUST", False, "7"),
        ("NO DATA", False, "7"),
        ("SOMETHING NEW", True, "7"),
        ("SOMETHING NEW", False, "7"),
    ],
)
def test_fr006_monochrome_keeps_reverse_and_underline(headline, color, codes):
    assert tv.headline_codes(headline, color) == codes


# --- golden frames ---------------------------------------------------------------------


@pytest.mark.parametrize("color", [True, False], ids=["color", "no-color"])
@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr006_golden_frame_for_every_vector(case, color):
    assert rows(case["lines"], color=color) == expected_rows(case["lines"], color)


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr006_plain_frame_for_every_vector_has_no_escape_at_all(case):
    plain = rows(case["lines"], escapes=False)
    assert plain == [ESCAPE.sub("", row) for row in expected_rows(case["lines"], True)]
    assert all("\x1b" not in row for row in plain)


def test_fr006_golden_in_range_frame():
    assert rows(["IN RANGE", "112 mg/dL ->", "3 min ago"]) == [
        "o))) lightkeeper   checked 02:14:07",
        "+-----------------------------+",
        "|  \x1b[32mIN RANGE                 \x1b[0m  |",
        "|  112 mg/dL ->               |",
        "|  3 min ago                  |",
        "+-----------------------------+",
        "next check in 60s - Ctrl+C to stop",
        "secondary display, confirm on the primary app",
    ]


def test_fr006_golden_stale_frame_strikes_the_last_line_in_monochrome():
    lines = ["STALE - DO NOT TRUST", "last: 112 mg/dL ->", "40 min ago", "Nightscout unreachable"]
    assert rows(lines, color=False, columns=120) == [
        "o))) lightkeeper   checked 02:14:07",
        "+-----------------------------+",
        "|  \x1b[7mSTALE - DO NOT TRUST     \x1b[0m  |",
        "|  \x1b[9mlast: 112 mg/dL ->\x1b[0m         |",
        "|  40 min ago                 |",
        "|  Nightscout unreachable     |",
        "+-----------------------------+",
        "next check in 60s - Ctrl+C to stop - secondary display, confirm on the primary app",
    ]


def test_fr006_golden_low_and_urgent_frames():
    low = rows(["LOW", "69 mg/dL v", "2 min ago"], color=False)
    assert low[2] == "|  \x1b[4mLOW                      \x1b[0m  |"
    urgent = rows(["URGENT HIGH", "250 mg/dL ^", "1 min ago"])
    assert urgent[2] == "|  \x1b[1;7;33mURGENT HIGH              \x1b[0m  |"


def test_fr006_unknown_headline_gets_the_cautious_band_and_no_strike():
    frame = rows(["SOMETHING NEW", "last: 112 mg/dL ->", "3 min ago"])
    assert frame[2] == "|  \x1b[7mSOMETHING NEW            \x1b[0m  |"
    assert frame[3] == "|  last: 112 mg/dL ->         |"


def test_fr006_no_data_frame_is_a_band_with_no_number():
    frame = rows(["NO DATA", "Check sensor and phone", "Confirm on primary device"])
    assert frame[2] == "|  \x1b[7mNO DATA                  \x1b[0m  |"
    assert frame[4] == "|  Confirm on primary device  |"


def test_fr006_header_shows_an_aware_time_in_local_time():
    aware = datetime(2026, 7, 15, 9, 30, 5, tzinfo=UTC)
    header = tv.frame_rows(["IN RANGE"], aware, 60)[0]
    assert header == f"o))) lightkeeper   checked {aware.astimezone():%H:%M:%S}"


def test_fr006_a_longer_line_widens_the_frame_instead_of_being_cut():
    frame = rows(["IN RANGE", "x" * 30])
    assert frame[1] == "+" + "-" * 34 + "+"
    assert frame[3] == "|  " + "x" * 30 + "  |"


def test_fr006_empty_lines_are_refused():
    with pytest.raises(ValueError, match="nothing to draw"):
        rows([])


# --- footer and note -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (
            200,
            ["next check in 45s - Ctrl+C to stop - secondary display, confirm on the primary app"],
        ),
        (
            80,
            [
                "next check in 45s - Ctrl+C to stop",
                "secondary display, confirm on the primary app",
            ],
        ),
        (
            44,
            [
                "next check in 45s - Ctrl+C to stop",
                "secondary display, confirm on the primary",
                "app",
            ],
        ),
        (
            33,
            [
                "next check in 45s",
                "Ctrl+C to stop",
                "secondary display, confirm on the",
                "primary app",
            ],
        ),
        (
            # Below the frame's own width nothing is broken further: the box wraps anyway.
            10,
            [
                "next check in 45s",
                "Ctrl+C to stop",
                "secondary display, confirm on",
                "the primary app",
            ],
        ),
    ],
)
def test_fr006_footer_is_broken_to_the_terminal_width(columns, expected):
    assert tv.footer_rows(45, columns) == expected


def test_fr006_min_columns_is_the_narrowest_frame():
    assert tv.MIN_COLUMNS == len(rows(["IN RANGE"])[1]) == 31


LONG_NOTE = (
    "Nightscout answered, but not with a list of readings. Check NIGHTSCOUT_URL points at "
    "Nightscout itself, not a login or maintenance page"
)


@pytest.mark.parametrize("columns", [35, 36, 40, 44, 45, 50, 60, 79, 80, 120])
@pytest.mark.parametrize("interval", [15, 60, 86400])
def test_fr006_no_row_is_wider_than_the_terminal(columns, interval):
    """A wider row would wrap, and the next redraw would leave its tail on the screen."""
    for case in VECTORS:
        frame = tv.frame_rows(case["lines"], CHECKED, interval, columns=columns, note=LONG_NOTE)
        assert all(len(ESCAPE.sub("", row)) <= columns for row in frame), case["name"]


def replay(text, columns, height=40):
    """Return the screen after `text`, on a small model of a VT terminal.

    It knows the codes a redraw uses (home, erase display, erase row, erase
    below; SGR changes attributes only) and wraps like xterm and the Windows
    console: a character in the last column leaves the cursor there, and the
    next printable character goes to the start of the next row. A line feed
    starts the next row, as a terminal's output processing makes it CR LF.
    """
    screen = [[" "] * columns for _ in range(height)]
    row = col = 0
    pending_wrap = False
    for token in re.findall("\x1b\\[[0-9;]*[A-Za-z]|\n|[^\x1b\n]", text):
        if token == "\n":
            row, col, pending_wrap = row + 1, 0, False
        elif token == tv.HOME:
            row, col, pending_wrap = 0, 0, False
        elif token == tv.CLEAR_SCREEN:
            screen = [[" "] * columns for _ in range(height)]
        elif token == tv.ERASE_ROW:
            screen[row] = [" "] * columns
        elif token == tv.ERASE_BELOW:
            screen[row][col:] = [" "] * (columns - col)
            for below in range(row + 1, height):
                screen[below] = [" "] * columns
        elif token.startswith("\x1b"):
            continue  # SGR: attributes, not characters
        else:
            if pending_wrap:
                row, col, pending_wrap = row + 1, 0, False
            screen[row][col] = token
            if col == columns - 1:
                pending_wrap = True
            else:
                col += 1
    return ["".join(cells).rstrip() for cells in screen]


def test_fr006_the_replay_model_wraps_like_a_terminal():
    assert replay("abcdef\nxy", 4, height=3) == ["abcd", "ef", "xy"]
    assert replay("abcd\nxy", 4, height=3) == ["abcd", "xy", ""]  # exactly full: no blank row
    assert replay("abcd\x1b[H\x1b[2Kz\x1b[J", 4, height=2) == ["z", ""]


STALE_LINES = [
    "STALE - DO NOT TRUST",
    "last: 112 mg/dL ->",
    "40 min ago",
    "Nightscout unreachable",
]
FRESH_LINES = ["IN RANGE", "112 mg/dL ->", "3 min ago"]


@pytest.mark.parametrize("columns", [31, 33, 35, 40, 44, 45, 60, 80])
def test_fr006_a_redraw_leaves_nothing_of_the_last_frame_behind(columns):
    """A taller frame with a note, then a shorter one: the screen shows only the second."""

    def frame(lines, note=None, first=False):
        return tv.render_frame(lines, CHECKED, 60, columns=columns, note=note, first=first)

    shown = replay(frame(STALE_LINES, note=LONG_NOTE, first=True) + frame(FRESH_LINES), columns)
    assert shown == replay(frame(FRESH_LINES, first=True), columns)
    assert any("primary" in row for row in shown)  # the footer is there, and nothing else


def test_fr006_footer_is_static_text_never_a_countdown():
    """The same footer every redraw: nothing ticks between checks."""
    assert tv.footer_rows(60, 80) == tv.footer_rows(60, 80) == FOOTER_80


def test_fr006_note_goes_under_the_footer_wrapped_and_unstyled():
    note = (
        "Nightscout refused the token (HTTP 401). Check NIGHTSCOUT_TOKEN is a readable "
        "token, never the API secret"
    )
    frame = rows(["NO DATA", "Check sensor and phone", "Nightscout unreachable"], note=note)
    assert frame[-4:-2] == FOOTER_80
    assert frame[-2:] == [
        "Nightscout refused the token (HTTP 401). Check NIGHTSCOUT_TOKEN is a readable",
        "token, never the API secret",
    ]
    assert all("\x1b" not in row for row in frame[-2:])


def test_fr006_no_note_adds_no_rows():
    assert rows(["IN RANGE"], note=None) == rows(["IN RANGE"], note="")


# --- one redraw ------------------------------------------------------------------------


def test_fr006_first_redraw_clears_once_later_ones_only_home():
    lines = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    first = tv.render_frame(lines, CHECKED, 60, first=True)
    later = tv.render_frame(lines, CHECKED, 60)
    assert first.startswith("\x1b[2J\x1b[H\x1b[2K")
    assert later.startswith("\x1b[H\x1b[2K") and "\x1b[2J" not in later
    body = [tv.ERASE_ROW + row + "\n" for row in rows(lines)]
    assert later == tv.HOME + "".join(body) + tv.ERASE_BELOW
    assert first == tv.CLEAR_SCREEN + later


def test_fr006_plain_redraw_is_the_frame_and_a_blank_line():
    lines = ["LOW", "69 mg/dL v", "2 min ago"]
    plain = tv.render_frame(lines, CHECKED, 60, escapes=False, first=True)
    assert plain == "\n".join(rows(lines, escapes=False)) + "\n\n"


def test_fr006_redraw_passes_the_note_and_columns_through():
    text = tv.render_frame(["IN RANGE"], CHECKED, 60, escapes=False, columns=200, note="see it")
    assert text.split("\n")[-4:] == [
        "next check in 60s - Ctrl+C to stop - secondary display, confirm on the primary app",
        "see it",
        "",
        "",
    ]


# --- calm and safe bytes -----------------------------------------------------------------


def every_frame():
    for case in VECTORS:
        for escapes in (True, False):
            for color in (True, False):
                for first in (True, False):
                    yield tv.render_frame(
                        case["lines"],
                        CHECKED,
                        60,
                        escapes=escapes,
                        color=color,
                        first=first,
                        note="Could not connect to Nightscout.",
                    )


def test_fr006_frames_are_ascii_and_never_ring_the_bell():
    for frame in every_frame():
        data = frame.encode("ascii")  # raises on anything that is not ASCII
        assert b"\x07" not in data
        assert all(byte in (0x0A, 0x1B) or 0x20 <= byte <= 0x7E for byte in data)


def test_fr006_frames_never_dim_blink_or_use_bright_black():
    used = set()
    for frame in every_frame():
        for params in SGR_PARAMS.findall(frame):
            used.update(int(code) for code in params.split(";"))
    assert used <= {0, 1, 4, 7, 9, 31, 32, 33}
    assert not used & {2, 5, 6, 90}


def test_fr006_no_line_can_smuggle_a_control_character_or_non_ascii():
    hostile = ["IN RANGE\x07", "café \x1b[2J\x1b]0;title\x07", "→ ↑\t\r"]
    frame = tv.render_frame(hostile, CHECKED, 60, escapes=False, note="bell\x07 \x1b[5m")
    assert frame.isascii()
    assert "\x07" not in frame and "\x1b" not in frame and "\t" not in frame and "\r" not in frame
    assert "|  IN RANGE?" in frame
    assert "caf? ?[2J?]0;title?" in frame
    assert "bell? ?[5m" in frame


# --- when the frame is used ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("watch", "isatty", "environ", "framed"),
    [
        (True, True, {}, True),
        (True, True, {"TERM": "xterm-256color"}, True),
        (True, True, {"TERM": "dumb"}, False),
        (True, True, {"TERM": " DUMB "}, False),
        (True, False, {}, False),
        (False, True, {}, False),
        (False, False, {"TERM": "xterm"}, False),
    ],
    ids=["tty", "xterm", "dumb", "dumb-spelled-loosely", "piped", "one-shot", "neither"],
)
def test_fr006_frame_only_for_watch_on_an_interactive_terminal(watch, isatty, environ, framed):
    assert tv.wants_frame(watch, isatty, environ) is framed


@pytest.mark.parametrize(
    ("no_color", "environ", "color"),
    [
        (False, {}, True),
        (False, {"NO_COLOR": ""}, True),  # no-color.org: set and not empty
        (False, {"NO_COLOR": "1"}, False),
        (False, {"NO_COLOR": "anything"}, False),
        (True, {}, False),
    ],
)
def test_fr006_no_color_and_the_flag_turn_color_off(no_color, environ, color):
    assert tv.wants_color(no_color, environ) is color


# --- Windows: VT processing, or the plain frame ----------------------------------------------


class FakeKernel32:
    """Stands in for kernel32: GetStdHandle, GetConsoleMode, SetConsoleMode."""

    def __init__(self, mode=0x0003, get_ok=1, set_ok=1, error=None):
        self.mode = mode
        self.get_ok = get_ok
        self.set_ok = set_ok
        self.error = error
        self.calls = []

    def GetStdHandle(self, which):  # noqa: N802 (the Windows API's name)
        self.calls.append(("GetStdHandle", which))
        if self.error:
            raise self.error
        return 1234

    def GetConsoleMode(self, handle, mode_ref):  # noqa: N802
        self.calls.append(("GetConsoleMode", handle))
        mode_ref._obj.value = self.mode
        return self.get_ok

    def SetConsoleMode(self, handle, mode):  # noqa: N802
        self.calls.append(("SetConsoleMode", handle, mode))
        return self.set_ok


def test_fr006_terminals_off_windows_already_act_on_escapes():
    kernel32 = FakeKernel32()
    assert tv.enable_vt("linux", kernel32) is True
    assert tv.enable_vt("darwin", kernel32) is True
    assert kernel32.calls == []


def test_fr006_windows_console_gets_vt_processing_switched_on():
    kernel32 = FakeKernel32(mode=0x0003)
    assert tv.enable_vt("win32", kernel32) is True
    assert kernel32.calls == [
        ("GetStdHandle", 0xFFFFFFF5),  # STD_OUTPUT_HANDLE, (DWORD)-11
        ("GetConsoleMode", 1234),
        ("SetConsoleMode", 1234, 0x0007),
    ]


def test_fr006_windows_terminal_already_has_it_and_is_left_alone():
    kernel32 = FakeKernel32(mode=0x0007)
    assert tv.enable_vt("win32", kernel32) is True
    assert [call[0] for call in kernel32.calls] == ["GetStdHandle", "GetConsoleMode"]


@pytest.mark.parametrize(
    "kernel32",
    [
        FakeKernel32(get_ok=0),  # stdout is not a console
        FakeKernel32(set_ok=0),  # a console too old for VT processing
        FakeKernel32(error=OSError("no console")),
        FakeKernel32(error=ctypes.ArgumentError("bad handle")),
        object(),  # no console functions at all
    ],
    ids=["not-a-console", "set-refused", "os-error", "ctypes-error", "no-api"],
)
def test_fr006_vt_enable_failure_falls_back_to_plain(kernel32):
    assert tv.enable_vt("win32", kernel32) is False


def test_fr006_no_kernel32_falls_back_to_plain(monkeypatch):
    monkeypatch.setattr(tv, "_kernel32", lambda: None)
    assert tv.enable_vt("win32") is False


def test_fr006_kernel32_is_typed_on_a_private_instance(monkeypatch):
    class Function:
        argtypes = None
        restype = None

    class Library:
        def __init__(self, name, use_last_error=False):
            self.name, self.use_last_error = name, use_last_error
            self.GetStdHandle = Function()
            self.GetConsoleMode = Function()
            self.SetConsoleMode = Function()

    monkeypatch.setattr(ctypes, "WinDLL", Library, raising=False)
    kernel32 = tv._kernel32()
    assert (kernel32.name, kernel32.use_last_error) == ("kernel32", True)
    # HANDLE is pointer-sized: never the default C int, which cuts it to 32 bits.
    assert kernel32.GetStdHandle.restype is ctypes.c_void_p
    assert kernel32.GetStdHandle.argtypes == [ctypes.c_uint32]
    assert kernel32.SetConsoleMode.argtypes == [ctypes.c_void_p, ctypes.c_uint32]
    assert kernel32.GetConsoleMode.restype is ctypes.c_int


def test_fr006_no_windll_means_no_kernel32(monkeypatch):
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    assert tv._kernel32() is None


def test_fr006_the_real_console_call_answers_without_raising():
    """On Windows this calls the real kernel32 (pytest's stdout is not a console)."""
    assert tv.enable_vt() in (True, False)
