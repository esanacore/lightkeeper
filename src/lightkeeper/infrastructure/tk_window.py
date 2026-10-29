"""The desktop glance window: a thin adapter over an injected tkinter module (FR-018).

The window shows the real panel: the pixels `render_bitmap` draws for the
current lines, stamped with the local `HH:MM` of the draw (HAZ-014), enlarged
by a whole number and tinted (`ppm`), so the bedside e-ink, the demo page and
this window are visibly the same object. Above it, a 24 px status strip holds
the headline in a drawn chip with its shape cue (docs/BRAND.md, Keeper's
Logbook): IN RANGE, LOW and HIGH get a 2 px status border round the word in Ink
on its tint; URGENT LOW and URGENT HIGH an Ink band with a 4 px leading rule in
the status color; STALE the Ink band with hatching in the strip's margin; NO
DATA and any other headline a 2 px dashed frame. Below it, the key hints in
Muted. `t` swaps the pixels for the vector lines as text in TkFixedFont (the
STALE `last:` line struck through, in Muted, and the draw's stamp under them,
so a frozen window shows in the text view too), `r` asks for a check, `q`
quits.

The panel's own rules (the status word never smaller than the number, STALE
never the hero) come from `render_bitmap`; nothing here draws a line larger.

The whole window always fits on the screen. The window cannot be resized, and
the bottom of the panel holds the age, the stamp and "Nightscout unreachable",
which must never be off screen. So the zoom is the largest whole number, no
larger than the one asked for, at which the window, its frame and title bar fit
the screen with room left for a taskbar. A panel that does not fit even at one
screen pixel a panel pixel is refused. On Windows the window opens centered:
Windows cascades new windows down the screen, which could push a tall one's
bottom under the taskbar.

Calm by construction: no bell, no taskbar flash, no notification, no `-alpha`
change, and nothing moves. A change is one redraw, and the screen on show is
never drawn again. The window title, which the caller makes from the lines,
gives screen readers the real text.

tkinter is never imported here. The composition root (desktop.py) imports it
lazily and passes the module in, so the CLI and the Pi never load it, and tests
run with a fake. Sizes are in 96 dpi pixels times `ui_scale`, a whole number
from the display's density: once `use_device_pixels` has told Windows the
window draws its own pixels, a 200% display shows every panel pixel as a whole
block of device pixels, never resampled by the system.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from lightkeeper.infrastructure.epaper_bitmap import render_bitmap, stamp_text
from lightkeeper.infrastructure.panel_layout import (
    DASH_OFF,
    DASH_ON,
    DASHED,
    HATCH_PITCH,
    HEADLINE,
    INVERSE,
    LAST,
    STALE,
    check_size,
    roles_for,
    treatment,
)
from lightkeeper.infrastructure.ppm import DARK, LIGHT, Tint, to_ppm

LIGHT_THEME = "light"
DARK_THEME = "dark"

TITLE = "Lightkeeper"  # until the first screen sets the real one
KEY_HINTS = "r refresh   t pixels/text   q quit"
TEXT_FONT = "TkFixedFont"
# Tk maps Helvetica to the platform's sans serif everywhere; no font file ships.
WORD_FONT = ("Helvetica", 10, "bold")
HINT_FONT = "TkDefaultFont"
PIXELS = "pixels"
TEXT = "text"

# Sizes in 96 dpi pixels, multiplied by ui_scale.
STRIP_HEIGHT = 24
MARGIN = 8  # round the strip, the panel and the hints
BEZEL = 2  # the Line strong ring round the panel
CHIP_INSET = 2  # above and below the chip, inside the strip
CHIP_PAD = 8  # from the word to the chip's edge
BORDER = 2  # the chip's border, and the thickness of its dashes
LEAD = 4  # URGENT's leading rule in the status color
TEXT_PAD = 12  # the text view's lines from the panel's edge
TEXT_GAP = 4  # between the text view's lines
BASE_DPI = 96
# What the system draws round the window, and keeps for itself at the screen's
# edge, in 96 dpi pixels at the display's own scale: room the window leaves for
# them. Windows 11 draws 7 px of frame and a 29 px title bar, and its taskbar is 48.
FRAME = 8  # each side, and below
TITLE_BAR = 32
SCREEN_EDGE = 48  # a taskbar, dock or menu bar

# A virtual event: any thread may queue it with `wake`, and Tk's thread runs its binding.
WAKE_EVENT = "<<LightkeeperWake>>"

# Colors by tokens.json color id, per theme (tests/test_tk_window.py checks each).
PALETTES: dict[str, dict[str, str]] = {
    LIGHT_THEME: {
        "fog": "#ECEBE5",
        "ink": "#15171C",
        "muted": "#5B6068",
        "line-strong": "#7D7B74",
        "band-text": "#E6E5DF",
        "in-range": "#2E6B4A",
        "low": "#B3261E",
        "high": "#B86A00",
        "stale": "#6B6F76",
        "chip-in-range": "#E4E6E0",
        "chip-low": "#EDE3DE",
        "chip-high": "#EDE6DE",
        "chip-stale": "#E7E6E2",
    },
    DARK_THEME: {
        "fog": "#0E1116",
        "ink": "#E6E5DF",
        "muted": "#9AA0A9",
        "line-strong": "#646C77",
        "band-text": "#0E1116",
        "in-range": "#6CC597",
        "low": "#FF6B5E",
        "high": "#F5A341",
        "stale": "#9AA0A9",
        "chip-in-range": "#335D4A",
        "chip-low": "#783433",
        "chip-high": "#734D29",
        "chip-stale": "#484C52",
    },
}
# The panel: Paper and Ink by day, Night paper and Night ink in dark mode.
TINTS: dict[str, Tint] = {LIGHT_THEME: LIGHT, DARK_THEME: DARK}

# tokens.json's status table, keyed by the headline the display shows: (color, chip).
STATUS_COLORS: dict[str, tuple[str, str]] = {
    "IN RANGE": ("in-range", "chip-in-range"),
    "LOW": ("low", "chip-low"),
    "HIGH": ("high", "chip-high"),
    "URGENT LOW": ("low", "chip-low"),
    "URGENT HIGH": ("high", "chip-high"),
    "STALE - DO NOT TRUST": ("stale", "chip-stale"),
    "NO DATA": ("stale", "chip-stale"),
}
UNKNOWN_COLORS = ("stale", "chip-stale")  # tokens.json unknown_headline, as NO DATA

# Windows: HKEY_CURRENT_USER\<this>, value AppsUseLightTheme (0 means dark).
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
PROCESS_SYSTEM_DPI_AWARE = 1  # shellscalingapi.h, PROCESS_DPI_AWARENESS


def ui_scale(dpi: float) -> int:
    """Return the whole-number scale for a display of `dpi` dots per inch: 1 at 96, 2 at 192.

    Rounded to the nearest whole number, halves up, and never below 1, so
    every size in the window, the panel's pixels among them, stays whole.
    """
    return max(1, int(dpi + BASE_DPI // 2) // BASE_DPI)


def chrome(dpi: float) -> tuple[int, int, int]:
    """Return the room for the frame, the title bar and the screen's edge, in device pixels.

    The system draws these at the display's own scale (150% is 1.5), not at
    `ui_scale`'s whole number, and never smaller than at 96 dpi.
    """
    factor = max(1.0, dpi / BASE_DPI)
    return round(FRAME * factor), round(TITLE_BAR * factor), round(SCREEN_EDGE * factor)


def system_theme(platform: str = sys.platform, registry: Any = None) -> str:
    """Return the theme the system asks apps for: `dark` or `light`.

    On Windows this reads AppsUseLightTheme; anywhere else, or when it cannot
    be read, the answer is light. `registry` (winreg) is injectable for tests.
    """
    if platform != "win32":
        return LIGHT_THEME
    try:
        api = registry if registry is not None else importlib.import_module("winreg")
        with api.OpenKey(api.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            value, _kind = api.QueryValueEx(key, "AppsUseLightTheme")
    except (ImportError, OSError):
        return LIGHT_THEME
    return DARK_THEME if value == 0 else LIGHT_THEME


def _shcore() -> Any:
    """Return shcore with SetProcessDpiAwareness typed, or None off Windows.

    A private instance, so the types set here never change
    `ctypes.windll.shcore` for anything else in the process.
    """
    import ctypes

    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        return None
    shcore = loader("shcore", use_last_error=True)
    shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
    shcore.SetProcessDpiAwareness.restype = ctypes.c_long  # HRESULT
    return shcore


def use_device_pixels(platform: str = sys.platform, shcore: Any = None) -> bool:
    """Tell Windows the window draws its own pixels; call it before the window opens.

    Otherwise, on a display scaled above 100%, Windows stretches the window
    and smooths every panel pixel. Returns True when Windows took it (or had
    already been told). Other systems already draw a window's pixels as they
    are. `shcore` is injectable for tests.
    """
    if platform != "win32":
        return False
    try:
        api = shcore if shcore is not None else _shcore()
        if api is None:
            return False
        # S_OK, or E_ACCESSDENIED when the awareness was set already, by a manifest.
        return api.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE) in (0, -2147024891)
    except (AttributeError, OSError):
        return False


def _nothing() -> None:
    """No action, for a key nobody asked to handle."""


class GlanceWindow:
    """The window: the status strip, the panel (pixels or text), and the key hints."""

    def __init__(
        self,
        tk: Any,
        width: int,
        height: int,
        scale: int = 2,
        theme: str = LIGHT_THEME,
        *,
        on_top: bool = False,
        on_refresh: Callable[[], object] = _nothing,
        on_quit: Callable[[], object] | None = None,
        on_error: Callable[[BaseException], object] | None = None,
        platform: str = sys.platform,
    ) -> None:
        """Open the window for a `width` x `height` panel, each pixel `scale` 96 dpi pixels.

        `tk` is the tkinter module. `on_quit` runs for `q` and the close box
        (by default the main loop stops); `on_error` gets any exception a Tk
        callback raises, Ctrl+C among them, instead of Tk printing it and
        carrying on. Raises ValueError for a panel the layout refuses, a scale
        that is not a whole number of 1 or more, or an unknown theme, before
        any window opens; and, closing the window it opened, for a panel the
        screen cannot hold even at one screen pixel a panel pixel. `zoom` is
        then the screen pixels a panel pixel, `scale` times `ui_scale` or less
        when that would not fit.
        """
        check_size(width, height)
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
            raise ValueError(f"scale must be a whole number of 1 or more, got {scale!r}")
        if theme not in PALETTES:
            raise ValueError(f"theme must be one of {', '.join(PALETTES)}, got {theme!r}")
        self._tk = tk
        self._width = width
        self._height = height
        self._palette = PALETTES[theme]
        self._tint = TINTS[theme]
        self.mode = PIXELS
        self._lines: tuple[str, ...] = ()
        self._stamp = ""
        self._screen: tuple[tuple[str, ...], str, str] | None = None
        self._photo: Any = None

        root = tk.Tk()
        self.root = root
        density = root.winfo_fpixels("1i")
        self.ui_scale = ui_scale(density)
        u = self.ui_scale
        background = self._palette["fog"]
        # Made first, packed last: its size, from the font, is part of what must fit.
        hints = tk.Label(
            root,
            text=KEY_HINTS,
            foreground=self._palette["muted"],
            background=background,
            font=HINT_FONT,
            anchor="w",
            borderwidth=0,
        )
        frame, title_bar, edge = chrome(density)
        screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
        room = (screen_width - 2 * frame, screen_height - title_bar - frame - edge)
        zoom = self._fit(scale * u, hints, room)
        if zoom is None:
            root.destroy()
            raise ValueError(
                f"a {width}x{height} panel does not fit on this {screen_width}x{screen_height} "
                "screen even at one screen pixel a panel pixel: choose a smaller panel"
            )
        self.zoom = zoom
        self.size = self._size(zoom, hints)  # the window's own area, frame and title bar aside
        if platform == "win32":
            # Windows cascades a new window down the screen, taskbar or not: center it.
            left = (screen_width - self.size[0] - 2 * frame) // 2
            top = (screen_height - edge - self.size[1] - title_bar - frame) // 2
            root.geometry(f"+{left}+{top}")
        root.title(TITLE)
        root.configure(background=background)
        root.resizable(False, False)
        if on_top:
            root.attributes("-topmost", True)
        if on_error is not None:
            root.report_callback_exception = lambda kind, error, trace: on_error(error)
        quit_action = on_quit if on_quit is not None else self.quit
        root.protocol("WM_DELETE_WINDOW", quit_action)
        for key, action in (("r", on_refresh), ("t", self.toggle), ("q", quit_action)):
            for name in (key, key.upper()):  # Caps Lock on
                root.bind(f"<KeyPress-{name}>", lambda _event, act=action: act())

        panel_width, panel_height = width * self.zoom, height * self.zoom
        self._strip_width = panel_width + 2 * BEZEL * u
        self._strip = tk.Canvas(
            root,
            width=self._strip_width,
            height=STRIP_HEIGHT * u,
            background=background,
            highlightthickness=0,
            borderwidth=0,
        )
        self._strip.pack(side="top", padx=MARGIN * u, pady=(MARGIN * u, CHIP_INSET * u))
        bezel = tk.Frame(
            root,
            background=self._palette["line-strong"],
            padx=BEZEL * u,
            pady=BEZEL * u,
            borderwidth=0,
            highlightthickness=0,
        )
        bezel.pack(side="top", padx=MARGIN * u)
        self._panel = tk.Canvas(
            bezel,
            width=panel_width,
            height=panel_height,
            background=self._tint.paper,
            highlightthickness=0,
            borderwidth=0,
        )
        self._panel.pack()
        hints.pack(side="top", fill="x", padx=MARGIN * u, pady=(CHIP_INSET * u, MARGIN * u))

    def _size(self, zoom: int, hints: Any) -> tuple[int, int]:
        """Return the window's own width and height at `zoom`: what the packer asks for."""
        u = self.ui_scale
        panel_width = self._width * zoom + 2 * BEZEL * u
        width = max(panel_width, hints.winfo_reqwidth()) + 2 * MARGIN * u
        height = (
            (2 * MARGIN + STRIP_HEIGHT + 2 * CHIP_INSET + 2 * BEZEL) * u
            + self._height * zoom
            + hints.winfo_reqheight()
        )
        return width, height

    def _fit(self, zoom: int, hints: Any, room: tuple[int, int]) -> int | None:
        """Return the largest whole zoom, `zoom` at most, whose window fits in `room`; or None."""
        for candidate in range(zoom, 0, -1):
            width, height = self._size(candidate, hints)
            if width <= room[0] and height <= room[1]:
                return candidate
        return None

    def show(self, lines: Sequence[str], title: str, drawn_at: datetime) -> bool:
        """Draw `lines`, stamped with the local HH:MM of `drawn_at`, and set the title.

        One redraw. Returns False, drawing nothing, when the lines, the title
        and the stamp are what is on screen already.
        """
        stamp = stamp_text(drawn_at)
        screen = (tuple(lines), title, stamp)
        if screen == self._screen:
            return False
        bitmap = render_bitmap(list(lines), self._width, self._height, stamp=stamp)
        photo = self._tk.PhotoImage(
            master=self.root, data=to_ppm(bitmap, self.zoom, self._tint), format="PPM"
        )
        self._screen = screen
        self._lines = screen[0]
        self._stamp = stamp
        self._photo = photo  # Tk shows an image only while Python holds on to it
        self.root.title(title)
        self._draw_strip(self._lines[0])
        self._draw_panel()
        return True

    def toggle(self) -> None:
        """Swap the panel's pixels for the vector lines as text, or back: one redraw."""
        self.mode = TEXT if self.mode == PIXELS else PIXELS
        if self._photo is not None:
            self._draw_panel()

    def _draw_panel(self) -> None:
        canvas = self._panel
        canvas.delete("all")
        if self.mode == PIXELS:
            canvas.create_image(0, 0, anchor="nw", image=self._photo)
            return
        u = self.ui_scale
        lines = self._lines
        roles = [HEADLINE, *roles_for(treatment(lines[0]), len(lines) - 1)]
        y = TEXT_PAD * u
        for line, role in zip(lines, roles, strict=True):
            struck = role == LAST  # an old value: struck through, in Muted
            fill = self._palette["muted"] if struck else self._tint.ink
            item = canvas.create_text(
                TEXT_PAD * u, y, text=line, anchor="nw", font=TEXT_FONT, fill=fill
            )
            left, top, right, bottom = canvas.bbox(item)
            if struck:
                middle = (top + bottom) // 2
                canvas.create_line(left, middle, right, middle, fill=fill, width=u)
            y = bottom + TEXT_GAP * u
        # The draw's stamp, as on the pixels, on a row of its own at the right: a frozen
        # window shows here too (HAZ-014). Screen chrome, not a vector line, so Muted.
        canvas.create_text(
            self._width * self.zoom - TEXT_PAD * u,
            y,
            text=self._stamp,
            anchor="ne",
            font=TEXT_FONT,
            fill=self._palette["muted"],
        )

    def _draw_strip(self, headline: str) -> None:
        """Draw the headline in its chip: the word plus its shape, color second."""
        canvas = self._strip
        canvas.delete("all")
        u = self.ui_scale
        palette = self._palette
        kind = treatment(headline)
        color, chip = STATUS_COLORS.get(headline, UNKNOWN_COLORS)
        banded = kind in (INVERSE, STALE)
        lead = LEAD * u if kind == INVERSE else 0
        top, bottom = CHIP_INSET * u, (STRIP_HEIGHT - CHIP_INSET) * u
        word = canvas.create_text(
            lead + CHIP_PAD * u,
            STRIP_HEIGHT * u // 2,
            text=headline,
            anchor="w",
            font=WORD_FONT,
            fill=palette["band-text" if banded else "ink"],
        )
        right = canvas.bbox(word)[2] + CHIP_PAD * u
        if banded:
            self._box(0, top, right, bottom, palette["ink"])
            if kind == INVERSE:
                self._box(0, top, lead, bottom, palette[color])
            else:
                self._hatch(right + MARGIN * u, palette[color])
        elif kind == DASHED:
            self._box(0, top, right, bottom, palette[chip])
            self._dashes(0, top, right, bottom, palette["line-strong"])
        else:
            edge = BORDER * u
            self._box(0, top, right, bottom, palette[color])
            self._box(edge, top + edge, right - edge, bottom - edge, palette[chip])
        canvas.tag_raise(word)

    def _box(self, left: int, top: int, right: int, bottom: int, fill: str) -> None:
        self._strip.create_rectangle(left, top, right, bottom, fill=fill, outline="", width=0)

    def _dashes(self, left: int, top: int, right: int, bottom: int, fill: str) -> None:
        """Draw a dashed ring inside the box, dashes counted from its top-left corner."""
        u = self.ui_scale
        thick, on, period = BORDER * u, DASH_ON * u, (DASH_ON + DASH_OFF) * u
        for x in range(left, right, period):
            end = min(x + on, right)
            self._box(x, top, end, top + thick, fill)
            self._box(x, bottom - thick, end, bottom, fill)
        for y in range(top, bottom, period):
            end = min(y + on, bottom)
            self._box(left, y, left + thick, end, fill)
            self._box(right - thick, y, right, end, fill)

    def _hatch(self, start: int, fill: str) -> None:
        """45 degree lines in the strip's margin from `start` on, never under the word."""
        u = self.ui_scale
        height = STRIP_HEIGHT * u
        for x in range(start, self._strip_width, HATCH_PITCH * u):
            self._strip.create_line(x, height, x + height, 0, fill=fill, width=u)

    def after(self, delay_ms: int, callback: Callable[[], object]) -> Any:
        """Run `callback` on Tk's thread in `delay_ms` milliseconds; returns the job."""
        return self.root.after(delay_ms, callback)

    def after_cancel(self, job: Any) -> None:
        """Cancel a job `after` returned."""
        self.root.after_cancel(job)

    def bind_wake(self, callback: Callable[[], object]) -> None:
        """Run `callback` on Tk's thread for every `wake`."""
        self.root.bind(WAKE_EVENT, lambda _event: callback())

    def wake(self) -> None:
        """Queue a wake-up for Tk's thread; safe to call from any thread.

        tkinter hands a call from another thread over to Tk's (threaded Tcl,
        as python.org and the Linux distributions build it), and `tail` queues
        the event there instead of running its binding in the caller's thread.
        Raises RuntimeError when Tk's main loop is not running, and TclError
        once the window is gone.
        """
        self.root.event_generate(WAKE_EVENT, when="tail")

    def mainloop(self) -> None:
        """Run until `quit`."""
        self.root.mainloop()

    def quit(self) -> None:
        """Stop the main loop; the window stays until `destroy`."""
        self.root.quit()

    def destroy(self) -> None:
        """Close the window."""
        self.root.destroy()
