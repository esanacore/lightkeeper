"""The interactive `--watch` screen: the vector lines in an ASCII logbook frame.

Only an interactive terminal running `--watch` gets this (docs/BRAND.md,
Terminal); the CLI decides that. Piped, systemd and `--json` output stays
exactly the vector lines. This module builds the text of one redraw from the
lines alone, the way `panel_layout` plans a panel from them: the status
shape comes from the headline (`lines[0]`), so nothing is classified again.

    o))) lightkeeper   checked 02:14:07
    +-----------------------------+
    |  IN RANGE                   |
    |  112 mg/dL ->               |
    |  3 min ago                  |
    +-----------------------------+
    next check in 60s - Ctrl+C to stop - secondary display, confirm on the primary app

Shape before hue: each status keeps a cue without color (assets/brand/
tokens.json, `terminal`). LOW and HIGH are underlined across the content
width, the panel's rule; URGENT LOW, URGENT HIGH, STALE, NO DATA and any
other headline are in reverse video, a band; the STALE `last:` line is
struck through. NO_COLOR and --no-color drop only the color codes (30 to
37). Never dim, blink or bright black, never the bell, and ASCII only: any
other character in a line is drawn as `?`, so no line can carry an escape.

Nothing moves between checks. A redraw homes the cursor, overwrites the
frame row by row, and erases what is left below it. Erase-display (`ESC [2J`)
is sent only before the first frame: some terminals, Windows Terminal among
them, move the screen into the scrollback on it, so sending it on every
redraw would grow the scrollback once a minute.

Pure standard library (ADR-0005); imports no application code.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from lightkeeper.infrastructure.panel_layout import LAST, WIDEST_LINE, roles_for, treatment

SIGNATURE = "o)))"
PADDING = 2  # spaces between the frame and the text, on both sides

# SGR parameters per headline (assets/brand/tokens.json, `terminal.sgr`,
# keyed there by level; here by the headline the display shows).
SGR = {
    "IN RANGE": "32",
    "LOW": "4;31",
    "HIGH": "4;33",
    "URGENT LOW": "1;7;31",
    "URGENT HIGH": "1;7;33",
    "STALE - DO NOT TRUST": "7",
    "NO DATA": "7",
}
UNKNOWN_SGR = "7"  # the most cautious treatment, as NO DATA
STALE_LAST_SGR = "9"  # strike through the STALE `last:` line
COLOR_CODES = range(30, 38)

ESC = "\x1b"
HOME = ESC + "[H"
CLEAR_SCREEN = ESC + "[2J"
ERASE_LINE = ESC + "[K"  # from the cursor to the end of the line
ERASE_BELOW = ESC + "[J"  # from the cursor to the end of the screen
RESET = ESC + "[0m"

# Windows console API (wincon.h).
STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def headline_codes(headline: str, color: bool = True) -> str:
    """Return the SGR parameters for a headline; without `color`, only the shape cues."""
    codes = SGR.get(headline, UNKNOWN_SGR)
    if color:
        return codes
    return ";".join(code for code in codes.split(";") if int(code) not in COLOR_CODES)


def _ascii(text: str) -> str:
    """Printable ASCII only: anything else, control characters included, becomes `?`."""
    return "".join(char if " " <= char <= "~" else "?" for char in text)


def _styled(text: str, codes: str, escapes: bool) -> str:
    if not escapes or not codes:
        return text
    return f"{ESC}[{codes}m{text}{RESET}"


def footer_rows(interval_seconds: int, columns: int) -> list[str]:
    """Return the footer rows, broken between its parts only where it would not fit."""
    parts = [
        f"next check in {interval_seconds}s",
        "Ctrl+C to stop",
        "secondary display, confirm on the primary app",
    ]
    rows = [parts[0]]
    for part in parts[1:]:
        joined = f"{rows[-1]} - {part}"
        if len(joined) <= columns:
            rows[-1] = joined
        else:
            rows.append(part)
    return rows


def frame_rows(
    lines: Sequence[str],
    checked_at: datetime,
    interval_seconds: int,
    *,
    escapes: bool = True,
    color: bool = True,
    columns: int = 80,
) -> list[str]:
    """Return the rows of one frame: header, the boxed lines, then the footer.

    `checked_at` is shown in local time, as `HH:MM:SS` (a naive time is taken
    as local already). With `escapes` off nothing but ASCII text is
    returned, for a terminal that cannot act on escape codes.
    """
    if not lines:
        raise ValueError("nothing to draw: lines is empty")
    clean = [_ascii(line) for line in lines]
    width = max(len(WIDEST_LINE), *(len(line) for line in clean))
    struck = {
        index
        for index, role in enumerate(roles_for(treatment(clean[0]), len(clean) - 1), start=1)
        if role == LAST
    }
    pad = " " * PADDING
    rule = "+" + "-" * (width + 2 * PADDING) + "+"
    rows = [f"{SIGNATURE} lightkeeper   checked {checked_at.astimezone():%H:%M:%S}", rule]
    for index, line in enumerate(clean):
        if index == 0:
            # Underline and reverse span the content width: the panel's rule and band.
            body = _styled(line.ljust(width), headline_codes(line, color), escapes)
        else:
            codes = STALE_LAST_SGR if index in struck else ""
            body = _styled(line, codes, escapes) + " " * (width - len(line))
        rows.append(f"|{pad}{body}{pad}|")
    rows.append(rule)
    rows.extend(footer_rows(interval_seconds, columns))
    return rows


def render_frame(
    lines: Sequence[str],
    checked_at: datetime,
    interval_seconds: int,
    *,
    escapes: bool = True,
    color: bool = True,
    columns: int = 80,
    first: bool = False,
) -> str:
    """Return the text of one redraw, ready to write to the terminal.

    With `escapes`, the frame replaces the last one in place: home, each row
    erased to its end, then everything below erased. `first` clears the
    screen once before that. Without `escapes`, the plain frame and a blank
    line, so successive frames stay apart.
    """
    rows = frame_rows(
        lines, checked_at, interval_seconds, escapes=escapes, color=color, columns=columns
    )
    if not escapes:
        return "\n".join(rows) + "\n\n"
    start = CLEAR_SCREEN + HOME if first else HOME
    return start + "".join(row + ERASE_LINE + "\n" for row in rows) + ERASE_BELOW


def _kernel32() -> Any:
    """Return the Windows kernel32 library, or None anywhere else."""
    import ctypes

    return getattr(getattr(ctypes, "windll", None), "kernel32", None)


def enable_vt(platform: str = sys.platform, kernel32: Any = None) -> bool:
    """Make sure stdout acts on escape codes; False means draw the plain frame.

    Terminals on Linux and macOS, and over SSH, already do. The Windows
    console does once ENABLE_VIRTUAL_TERMINAL_PROCESSING is set on stdout
    (Windows 10 and later; Windows Terminal has it set already). If that
    fails, the frame is drawn without escape codes rather than as garbage.
    `kernel32` is injectable for tests.
    """
    if platform != "win32":
        return True
    import ctypes

    api = kernel32 if kernel32 is not None else _kernel32()
    if api is None:
        return False
    mode = ctypes.c_uint32()
    try:
        handle = api.GetStdHandle(STD_OUTPUT_HANDLE)
        if not api.GetConsoleMode(handle, ctypes.pointer(mode)):
            return False
        return bool(api.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except (AttributeError, OSError):
        return False
