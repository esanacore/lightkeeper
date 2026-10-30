"""FR-018, NFR-005: the desktop window draws the real panel pixels, calmly, in brand colors.

These tests run the window against FakeTk, a stand-in for the tkinter module
that records every call, so they need no display. The window shows exactly
the pixels render_bitmap draws, stamped, at a whole-number zoom; `t` swaps
them for the lines as text in TkFixedFont, the stamp still under them; `r`
asks for a check and `q` quits; the whole window fits the screen at every
panel size, or the panel is refused; the status strip gives every headline
its word plus its shape; and nothing rings, flashes or blinks. Two tests open
a real Tk window, each in a fresh Python: with no display they skip locally,
and fail on CI (CI=true), where the Test Runner gives them one.
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lightkeeper.infrastructure import tk_window as tw
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap, stamp_text
from lightkeeper.infrastructure.panel_layout import roles_for, treatment
from lightkeeper.infrastructure.panel_profiles import PROFILES
from lightkeeper.infrastructure.ppm import DARK, LIGHT, to_ppm
from tests.test_brand_tokens import contrast
from tests.test_vectors import VECTORS

ROOT = Path(__file__).resolve().parent.parent
TOKENS = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))
COLOR = TOKENS["color"]

DRAWN = datetime(2026, 10, 18, 2, 14, 30).astimezone()
FRESH = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
STALE = ["STALE - DO NOT TRUST", "last: 120 mg/dL ->", "16 min ago", "Confirm on primary device"]
NO_DATA = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
HEADLINES = list(tw.STATUS_COLORS) + ["SOMETHING NEW"]


# --- FakeTk: a tkinter module that records ------------------------------------------------


class FakeTclError(Exception):
    """Stands in for tkinter.TclError."""


class FakeEvent:
    """What Tk passes a bound callback; the window ignores it."""


class FakeWidget:
    def __init__(self, master=None, **options):
        self.master = master
        self.options = dict(options)
        self.packed = None

    def pack(self, **options):
        self.packed = options


class FakeLabel(FakeWidget):
    """Asks for its text's size: 7 px a character and 15 px tall, as FakeCanvas measures."""

    def winfo_reqwidth(self):
        return FakeCanvas.CHAR_WIDTH * len(self.options["text"])

    def winfo_reqheight(self):
        return FakeCanvas.LINE_HEIGHT


class FakeCanvas(FakeWidget):
    """Records items in stacking order; text is 7 px a character and 15 px tall."""

    CHAR_WIDTH = 7
    LINE_HEIGHT = 15

    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.items = {}
        self.order = []
        self.clears = 0
        self._next = 1

    def _add(self, kind, coords, options):
        item = self._next
        self._next += 1
        self.items[item] = (kind, coords, options)
        self.order.append(item)
        return item

    def create_rectangle(self, *coords, **options):
        return self._add("rectangle", coords, options)

    def create_line(self, *coords, **options):
        return self._add("line", coords, options)

    def create_text(self, *coords, **options):
        return self._add("text", coords, options)

    def create_image(self, *coords, **options):
        return self._add("image", coords, options)

    def bbox(self, item):
        kind, (x, y), options = self.items[item]
        assert kind == "text"
        width = self.CHAR_WIDTH * len(options["text"])
        height = self.LINE_HEIGHT
        if options["anchor"] == "nw":
            return (x, y, x + width, y + height)
        assert options["anchor"] == "w"
        return (x, y - height // 2, x + width, y - height // 2 + height)

    def delete(self, tag):
        assert tag == "all"
        self.items.clear()
        self.order.clear()
        self.clears += 1

    def tag_raise(self, item):
        self.order.remove(item)
        self.order.append(item)

    def drawn(self, kind=None):
        """Items in stacking order, bottom first: (kind, coords, options)."""
        return [self.items[i] for i in self.order if kind is None or self.items[i][0] == kind]


class FakePhoto:
    def __init__(self, master=None, data=None, format=None):  # noqa: A002 (tkinter's name)
        self.master = master
        self.data = data
        self.format = format


class FakeRoot(FakeWidget):
    """The Tk root: records the title, attributes, bindings and timers; never rings."""

    def __init__(self, module):
        super().__init__(None)
        self.module = module
        self.titles = []
        self.attribute_calls = []
        self.geometries = []
        self.binds = {}
        self.protocols = {}
        self.timers = []  # (due ms, sequence, job, callback)
        self.posted = []  # virtual events queued with when="tail", from any thread
        self.now_ms = 0
        self.quits = 0
        self.destroyed = 0
        self.bells = 0
        self.reported = []
        self._jobs = 0

    def title(self, text):
        self.titles.append(text)

    def geometry(self, spec):
        self.geometries.append(spec)

    def winfo_screenwidth(self):
        return self.module.screen[0]

    def winfo_screenheight(self):
        return self.module.screen[1]

    def event_generate(self, sequence, when=None):
        assert when == "tail"  # queued for Tk's thread, never run in the caller's
        self.posted.append(sequence)  # list.append is atomic: any thread may post

    def configure(self, **options):
        self.options.update(options)

    def resizable(self, width, height):
        self.options["resizable"] = (width, height)

    def attributes(self, *args):
        self.attribute_calls.append(args)

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def bind(self, sequence, callback):
        self.binds[sequence] = callback

    def winfo_fpixels(self, distance):
        assert distance == "1i"
        return self.module.dpi

    def after(self, delay_ms, callback):
        self._jobs += 1
        job = f"after#{self._jobs}"
        self.timers.append((self.now_ms + delay_ms, self._jobs, job, callback))
        return job

    def after_cancel(self, job):
        self.timers = [timer for timer in self.timers if timer[2] != job]

    def mainloop(self):
        if self.module.driver is not None:
            self.module.driver(self)

    def quit(self):
        self.quits += 1

    def destroy(self):
        self.destroyed += 1

    def bell(self):
        self.bells += 1

    def report_callback_exception(self, kind, error, trace):
        self.reported.append(error)

    # Driving the fake main loop.

    def call(self, callback, *args):
        """Run a callback as tkinter's CallWrapper does: errors go to report_callback_exception."""
        try:
            return callback(*args)
        except SystemExit:
            raise
        except BaseException as error:  # noqa: BLE001 - tkinter catches everything here
            self.report_callback_exception(type(error), error, error.__traceback__)

    def step(self):
        """Run the next timer due, moving the fake clock to it."""
        self.timers.sort()
        due, _sequence, _job, callback = self.timers.pop(0)
        self.now_ms = due
        self.call(callback)

    def press(self, key):
        self.call(self.binds[f"<KeyPress-{key}>"], FakeEvent())

    def deliver(self):
        """Run the binding of every queued virtual event, oldest first, as Tk's thread does."""
        while self.posted:
            self.call(self.binds[self.posted.pop(0)], FakeEvent())


class FakeTk:
    """The tkinter module, faked: Tk, Canvas, Frame, Label, PhotoImage and TclError."""

    TclError = FakeTclError

    def __init__(self, dpi=96.0, error=None, screen=(3840, 2160)):
        self.dpi = dpi
        self.error = error
        self.screen = screen
        self.roots = []
        self.photos = []
        self.canvases = []
        self.labels = []
        self.frames = []
        self.driver = None

    def Tk(self):  # noqa: N802 (tkinter's name)
        if self.error is not None:
            raise self.error
        root = FakeRoot(self)
        self.roots.append(root)
        return root

    def Canvas(self, master=None, **options):  # noqa: N802
        canvas = FakeCanvas(master, **options)
        self.canvases.append(canvas)
        return canvas

    def Frame(self, master=None, **options):  # noqa: N802
        frame = FakeWidget(master, **options)
        self.frames.append(frame)
        return frame

    def Label(self, master=None, **options):  # noqa: N802
        label = FakeLabel(master, **options)
        self.labels.append(label)
        return label

    def PhotoImage(self, master=None, data=None, format=None):  # noqa: N802, A002
        photo = FakePhoto(master, data, format)
        self.photos.append(photo)
        return photo


def open_window(tk=None, **options):
    tk = tk or FakeTk()
    options.setdefault("theme", tw.LIGHT_THEME)
    options.setdefault("platform", "linux")  # the window manager places it
    window = tw.GlanceWindow(tk, options.pop("width", 296), options.pop("height", 128), **options)
    return tk, window


def strip(tk):
    return tk.canvases[0]


def panel(tk):
    return tk.canvases[1]


# --- the panel pixels ---------------------------------------------------------------------


@pytest.mark.parametrize("scale", [2, 3])
def test_fr018_window_shows_the_panel_pixels_at_whole_zoom(scale):
    tk, window = open_window(scale=scale)
    assert window.show(FRESH, "title", DRAWN) is True
    [photo] = tk.photos
    expected = render_bitmap(FRESH, 296, 128, stamp=stamp_text(DRAWN))
    assert photo.data == to_ppm(expected, scale, LIGHT)
    assert photo.format == "PPM" and photo.master is window.root
    assert panel(tk).options["width"] == 296 * scale
    assert panel(tk).options["height"] == 128 * scale
    assert panel(tk).drawn() == [("image", (0, 0), {"anchor": "nw", "image": photo})]


def test_fr018_zoom_follows_the_display_density_in_whole_numbers():
    """On a 200% display every panel pixel is 2 x scale device pixels, still whole."""
    tk, window = open_window(FakeTk(dpi=192.0), scale=2)
    assert (window.ui_scale, window.zoom) == (2, 4)
    window.show(FRESH, "title", DRAWN)
    assert tk.photos[0].data.startswith(b"P6\n1184 512\n255\n")
    assert strip(tk).options["height"] == 48


@pytest.mark.parametrize(
    "dpi,scale", [(72, 1), (96, 1), (120, 1), (143.9, 1), (144, 2), (192, 2), (240, 3), (288, 3)]
)
def test_fr018_ui_scale_is_a_whole_number_from_the_density(dpi, scale):
    assert tw.ui_scale(dpi) == scale


@pytest.mark.parametrize("scale", [2.5, 2.0, 0, -1, True, "2"])
def test_fr018_window_refuses_a_zoom_that_is_not_whole(scale):
    tk = FakeTk()
    with pytest.raises(ValueError, match="scale must be a whole number"):
        open_window(tk, scale=scale)
    assert tk.roots == []  # refused before any window opened


def test_fr018_window_refuses_an_unknown_theme_and_a_panel_too_small():
    tk = FakeTk()
    with pytest.raises(ValueError, match="theme must be one of light, dark"):
        open_window(tk, theme="sepia")
    with pytest.raises(ValueError):
        open_window(tk, width=20, height=10)
    assert tk.roots == []


def test_fr018_stamp_is_drawn_on_the_bitmap():
    tk, window = open_window()
    window.show(FRESH, "title", DRAWN)
    unstamped = to_ppm(render_bitmap(FRESH, 296, 128), 2)
    assert tk.photos[0].data != unstamped
    window.show(FRESH, "title", DRAWN + timedelta(minutes=1))
    assert tk.photos[1].data == to_ppm(
        render_bitmap(FRESH, 296, 128, stamp=stamp_text(DRAWN + timedelta(minutes=1))), 2
    )


def test_fr018_same_screen_is_never_drawn_twice():
    """A change is one redraw; the same lines, title and stamp draw nothing."""
    tk, window = open_window()
    assert window.show(FRESH, "a title", DRAWN) is True
    assert window.show(tuple(FRESH), "a title", DRAWN + timedelta(seconds=20)) is False
    assert len(tk.photos) == 1
    assert window.root.titles == [tw.TITLE, "a title"]
    assert panel(tk).clears == 1 and strip(tk).clears == 1
    assert window.show(FRESH, "a new title", DRAWN) is True
    assert window.root.titles[-1] == "a new title"


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr018_window_draws_every_vector_as_render_bitmap_does(case):
    tk, window = open_window(theme=tw.DARK_THEME)
    window.show(case["lines"], "title", DRAWN)
    expected = render_bitmap(case["lines"], 296, 128, stamp=stamp_text(DRAWN))
    assert tk.photos[0].data == to_ppm(expected, 2, DARK)


# --- the text view ------------------------------------------------------------------------


def test_fr018_t_shows_the_vector_lines_as_text_in_tk_fixed_font():
    tk, window = open_window()
    window.show(FRESH, "title", DRAWN)
    window.root.press("t")
    assert window.mode == tw.TEXT
    *texts, _stamp = panel(tk).drawn("text")
    assert [options["text"] for _kind, _coords, options in texts] == FRESH
    assert {options["font"] for _kind, _coords, options in texts} == {"TkFixedFont"}
    assert {options["fill"] for _kind, _coords, options in texts} == {LIGHT.ink}
    tops = [coords[1] for _kind, coords, _options in texts]
    assert tops == sorted(tops) and len(set(tops)) == len(tops)  # one under another
    assert panel(tk).drawn("image") == [] and panel(tk).drawn("line") == []
    window.root.press("T")  # Caps Lock on
    assert window.mode == tw.PIXELS
    assert [kind for kind, _coords, _options in panel(tk).drawn()] == ["image"]
    assert len(tk.photos) == 1  # a toggle redraws, but draws no new pixels


@pytest.mark.parametrize("lines", [FRESH, STALE, NO_DATA], ids=["fresh", "stale", "no-data"])
def test_fr018_text_view_keeps_the_stamp(lines):
    """The draw's HH:MM stays in the text view, so a frozen window shows there too (HAZ-014)."""
    tk, window = open_window()
    window.show(lines, "title", DRAWN)
    window.toggle()
    *texts, (_kind, (x, y), stamp) = panel(tk).drawn("text")
    assert stamp == {
        "text": "02:14",
        "anchor": "ne",
        "font": "TkFixedFont",
        "fill": tw.PALETTES[tw.LIGHT_THEME]["muted"],
    }
    assert x == 296 * 2 - tw.TEXT_PAD  # right-aligned in the panel
    last_bottom = texts[-1][1][1] + FakeCanvas.LINE_HEIGHT
    assert y == last_bottom + tw.TEXT_GAP  # a row of its own, under every line
    # The next minute's screen, still in text view, carries the new stamp.
    assert window.show(lines, "title", DRAWN + timedelta(minutes=1)) is True
    assert panel(tk).drawn("text")[-1][2]["text"] == "02:15"
    assert window.mode == tw.TEXT


def test_fr018_text_view_strikes_the_stale_last_line_in_muted():
    tk, window = open_window()
    window.show(STALE, "title", DRAWN)
    window.toggle()
    texts = panel(tk).drawn("text")
    fills = [options["fill"] for _kind, _coords, options in texts]
    muted = tw.PALETTES[tw.LIGHT_THEME]["muted"]
    assert fills == [LIGHT.ink, muted, LIGHT.ink, LIGHT.ink, muted]  # the stamp last
    [(_kind, (left, y0, right, y1), options)] = panel(tk).drawn("line")
    _kind, (x, top), text = texts[1]
    assert text["text"] == "last: 120 mg/dL ->"
    assert (left, right) == (x, x + 7 * len(text["text"]))
    assert y0 == y1 == top + 15 // 2
    assert options == {"fill": muted, "width": 1}


def test_fr018_toggle_before_the_first_screen_draws_nothing():
    tk, window = open_window()
    window.toggle()
    assert window.mode == tw.TEXT
    assert panel(tk).clears == 0
    window.show(NO_DATA, "title", DRAWN)
    assert [o["text"] for _k, _c, o in panel(tk).drawn("text")] == [*NO_DATA, "02:14"]


def test_fr018_text_view_roles_match_the_panel_layout():
    """The struck line is the panel's `last` line, from the headline alone."""
    for case in VECTORS:
        lines = case["lines"]
        roles = roles_for(treatment(lines[0]), len(lines) - 1)
        tk, window = open_window()
        window.show(lines, "title", DRAWN)
        window.toggle()
        assert len(panel(tk).drawn("line")) == roles.count("last"), case["name"]


# --- keys, and nothing that rings or flashes ----------------------------------------------


def test_fr018_r_t_and_q_keys():
    pressed = []
    tk, window = open_window(
        on_refresh=lambda: pressed.append("refresh"), on_quit=lambda: pressed.append("quit")
    )
    window.show(FRESH, "title", DRAWN)
    root = window.root
    for key in ("r", "R", "q", "Q"):
        root.press(key)
    assert pressed == ["refresh", "refresh", "quit", "quit"]
    root.call(root.protocols["WM_DELETE_WINDOW"])
    assert pressed[-1] == "quit"
    root.press("t")
    assert window.mode == tw.TEXT
    assert root.reported == []


def test_fr018_q_stops_the_main_loop_by_default():
    tk, window = open_window()
    window.root.press("q")
    window.root.call(window.root.protocols["WM_DELETE_WINDOW"])
    assert window.root.quits == 2
    window.root.press("r")  # no refresh handler: nothing happens, nothing is reported
    assert window.root.reported == []


def test_fr018_window_never_rings_flashes_or_changes_its_attributes():
    tk, window = open_window()
    for lines in (FRESH, STALE, NO_DATA, FRESH):
        window.show(lines, " - ".join(lines), DRAWN)
        window.toggle()
        window.toggle()
    for key in ("r", "t", "t"):
        window.root.press(key)
    assert window.root.bells == 0
    assert window.root.attribute_calls == []


def test_fr018_on_top_is_set_once_and_never_flashed():
    tk, window = open_window(on_top=True)
    for lines in (FRESH, STALE, NO_DATA):
        window.show(lines, "title", DRAWN)
    assert window.root.attribute_calls == [("-topmost", True)]
    assert window.root.bells == 0


def test_fr018_window_and_desktop_source_have_no_bell_flash_or_alpha():
    for module in ("infrastructure/tk_window.py", "desktop.py"):
        text = (ROOT / "src" / "lightkeeper" / module).read_text(encoding="utf-8")
        code = re.sub(r'"""(?:.|\n)*?"""|#.*', "", text)  # docstrings and comments may name them
        for forbidden in ("bell(", "FlashWindow", "-alpha", "notify", "flash"):
            assert forbidden not in code, (module, forbidden)


def test_fr018_window_is_fixed_size_with_the_panel_in_a_bezel():
    tk, window = open_window()
    assert window.root.options["resizable"] == (False, False)
    [bezel] = tk.frames
    assert bezel.options["background"] == tw.PALETTES["light"]["line-strong"]
    assert panel(tk).master is bezel
    assert panel(tk).options["highlightthickness"] == 0
    assert panel(tk).options["borderwidth"] == 0
    assert strip(tk).options["width"] == 296 * 2 + 2 * tw.BEZEL


def test_fr018_key_hints_are_muted_in_the_footer():
    tk, window = open_window()
    [hints] = tk.labels
    assert hints.options["text"] == "r refresh   t pixels/text   q quit"
    assert hints.options["foreground"] == tw.PALETTES["light"]["muted"]
    assert hints.options["background"] == tw.PALETTES["light"]["fog"]


def test_fr018_callback_errors_go_to_on_error():
    errors = []
    tk, window = open_window(on_error=errors.append)
    interrupt = KeyboardInterrupt()
    window.root.call(lambda: (_ for _ in ()).throw(interrupt))
    assert errors == [interrupt]


def test_fr018_timers_and_the_main_loop_pass_through():
    tk, window = open_window()
    calls = []
    job = window.after(30, lambda: calls.append("fired"))
    other = window.after(10, lambda: calls.append("other"))
    window.after_cancel(other)
    window.root.step()
    assert calls == ["fired"] and window.root.now_ms == 30 and job == "after#1"
    tk.driver = lambda root: calls.append("looped")
    window.mainloop()
    window.quit()
    window.destroy()
    assert calls[-1] == "looped"
    assert (window.root.quits, window.root.destroyed) == (1, 1)


def test_fr018_wake_queues_the_poll_for_tk_thread():
    """Any thread may wake the window; the binding runs later, on Tk's thread, not the caller's."""
    tk, window = open_window()
    woken = []
    window.bind_wake(lambda: woken.append(threading.current_thread()))
    caller = threading.Thread(target=window.wake)
    caller.start()
    caller.join()
    assert woken == [] and window.root.posted == [tw.WAKE_EVENT]
    window.root.deliver()
    assert woken == [threading.current_thread()]


# --- the window fits the screen -----------------------------------------------------------


def on_screen(window, dpi):
    """Return the window's outer width and height, frame, title bar and screen edge included."""
    frame, title_bar, edge = tw.chrome(dpi)
    width, height = window.size
    return width + 2 * frame, height + title_bar + frame + edge


@pytest.mark.parametrize("scale", [2, 3])
@pytest.mark.parametrize("name", list(PROFILES))
def test_fr018_window_fits_the_screen_for_every_profile(name, scale):
    """At 2880x1800 and 200%, as here: every panel, its age, stamp and last line, on screen."""
    profile = PROFILES[name]
    tk, window = open_window(
        FakeTk(dpi=192.0, screen=(2880, 1800)),
        width=profile.width,
        height=profile.height,
        scale=scale,
    )
    asked = scale * window.ui_scale
    assert 1 <= window.zoom <= asked
    width, height = on_screen(window, 192.0)
    assert width <= 2880 and height <= 1800
    if window.zoom < asked:  # the largest whole zoom that fits: one more would not
        bigger = window._size(window.zoom + 1, tk.labels[0])
        frame, title_bar, edge = tw.chrome(192.0)
        assert bigger[0] + 2 * frame > 2880 or bigger[1] + title_bar + frame + edge > 1800
    # The pixels, the panel and the strip are all at that zoom.
    window.show(STALE, "title", DRAWN)
    size = f"{profile.width * window.zoom} {profile.height * window.zoom}"
    assert tk.photos[0].data.startswith(f"P6\n{size}\n255\n".encode())
    assert panel(tk).options["width"] == profile.width * window.zoom
    assert strip(tk).options["width"] == profile.width * window.zoom + 2 * tw.BEZEL * 2


@pytest.mark.parametrize(
    "name,scale,zoom",
    [
        ("waveshare_2in9", 2, 4),  # fits as asked
        ("waveshare_7in5", 2, 3),  # 3240 px wide at 4: wider than the screen
        ("waveshare_4in2", 3, 5),  # 1911 px tall at 6: taller than the screen
        ("kindle", 2, 1),  # 1711 px tall at 2
    ],
)
def test_fr018_zoom_is_the_largest_whole_number_that_fits(name, scale, zoom):
    profile = PROFILES[name]
    _tk, window = open_window(
        FakeTk(dpi=192.0, screen=(2880, 1800)),
        width=profile.width,
        height=profile.height,
        scale=scale,
    )
    assert window.zoom == zoom


def test_fr018_kindle_on_a_1080p_screen_gets_a_zoom_that_fits():
    tk, window = open_window(FakeTk(screen=(1920, 1080)), width=600, height=800)
    assert window.zoom == 1
    assert window.size == (600 + 2 * tw.BEZEL + 2 * tw.MARGIN, 63 + 800)
    width, height = on_screen(window, 96.0)
    assert width <= 1920 and height <= 1080


def test_fr018_panel_the_screen_cannot_hold_is_refused_and_its_window_closed():
    tk = FakeTk(screen=(1366, 768))
    with pytest.raises(
        ValueError, match="a 600x800 panel does not fit on this 1366x768 screen even at one"
    ):
        open_window(tk, width=600, height=800)
    [root] = tk.roots
    assert root.destroyed == 1 and root.titles == []


def test_fr018_window_chrome_is_at_the_display_own_scale():
    assert tw.chrome(96.0) == (8, 32, 48)
    assert tw.chrome(144.0) == (12, 48, 72)  # 150%, where ui_scale rounds up to 2
    assert tw.chrome(192.0) == (16, 64, 96)
    assert tw.chrome(72.0) == (8, 32, 48)  # macOS reports 72: never less than at 96


@pytest.mark.parametrize("name", list(PROFILES))
def test_fr018_windows_opens_the_window_centered_clear_of_the_taskbar(name):
    """Windows would cascade a tall window under the taskbar; it opens centered instead."""
    profile = PROFILES[name]
    tk, window = open_window(
        FakeTk(dpi=192.0, screen=(2880, 1800)),
        width=profile.width,
        height=profile.height,
        platform="win32",
    )
    [spec] = window.root.geometries
    left, top = (int(n) for n in re.fullmatch(r"\+(\d+)\+(\d+)", spec).groups())
    frame, title_bar, edge = tw.chrome(192.0)
    outer_width = window.size[0] + 2 * frame
    outer_height = window.size[1] + title_bar + frame
    assert left + outer_width <= 2880 and abs(2880 - outer_width - 2 * left) <= 1
    assert top + outer_height <= 1800 - edge and abs(1800 - edge - outer_height - 2 * top) <= 1


def test_fr018_window_manager_places_the_window_off_windows():
    _tk, window = open_window(platform="linux")
    assert window.root.geometries == []
    _tk, window = open_window(platform="darwin")
    assert window.root.geometries == []


# --- the status strip: the word plus its shape --------------------------------------------


def chip_parts(tk):
    """Return the strip's one text item, its rectangles and its lines, in stacking order."""
    items = strip(tk).drawn()
    [word] = [item for item in items if item[0] == "text"]
    assert items[-1] is word  # the word is always on top: nothing is drawn over it
    rectangles = [
        (coords, options["fill"]) for kind, coords, options in items if kind == "rectangle"
    ]
    lines = [(coords, options) for kind, coords, options in items if kind == "line"]
    return word, rectangles, lines


@pytest.mark.parametrize("theme", [tw.LIGHT_THEME, tw.DARK_THEME])
@pytest.mark.parametrize("headline", ["IN RANGE", "LOW", "HIGH"])
def test_fr018_strip_plain_and_rule_get_a_status_border_round_the_tinted_chip(headline, theme):
    tk, window = open_window(theme=theme)
    window.show([headline, "1 mg/dL ->", "just now"], "title", DRAWN)
    palette = tw.PALETTES[theme]
    color, chip = tw.STATUS_COLORS[headline]
    (_kind, (x, y), word), rectangles, lines = chip_parts(tk)
    assert (word["text"], word["fill"], word["font"]) == (headline, palette["ink"], tw.WORD_FONT)
    right = x + 7 * len(headline) + tw.CHIP_PAD
    assert rectangles == [
        ((0, 2, right, 22), palette[color]),
        ((2, 4, right - 2, 20), palette[chip]),
    ]
    assert lines == [] and y == 12


@pytest.mark.parametrize("headline", ["URGENT LOW", "URGENT HIGH"])
def test_fr018_strip_urgent_is_an_ink_band_with_a_leading_status_rule(headline):
    tk, window = open_window()
    window.show([headline, "40 mg/dL vv", "just now"], "title", DRAWN)
    palette = tw.PALETTES["light"]
    color, _chip = tw.STATUS_COLORS[headline]
    (_kind, (x, _y), word), rectangles, lines = chip_parts(tk)
    assert word["fill"] == palette["band-text"] and x == tw.LEAD + tw.CHIP_PAD
    right = x + 7 * len(headline) + tw.CHIP_PAD
    assert rectangles == [((0, 2, right, 22), palette["ink"]), ((0, 2, 4, 22), palette[color])]
    assert lines == []


def test_fr018_strip_stale_is_an_ink_band_with_hatching_in_the_margin_only():
    tk, window = open_window()
    window.show(STALE, "title", DRAWN)
    palette = tw.PALETTES["light"]
    (_kind, (x, _y), word), rectangles, lines = chip_parts(tk)
    assert word["fill"] == palette["band-text"]
    right = x + 7 * len(STALE[0]) + tw.CHIP_PAD
    assert rectangles == [((0, 2, right, 22), palette["ink"])]
    starts = [coords[0] for coords, _options in lines]
    assert starts == list(range(right + tw.MARGIN, 296 * 2 + 4, 4))
    for (x0, y0, x1, y1), options in lines:
        assert (y0, y1, x1 - x0) == (24, 0, 24)  # 45 degrees, the strip's full height
        assert options == {"fill": palette["stale"], "width": 1}
        assert x0 > right  # never under the word or its band


@pytest.mark.parametrize("headline", ["NO DATA", "SOMETHING NEW"])
def test_fr018_strip_no_data_and_unknown_get_a_dashed_frame(headline):
    """NO DATA, and any headline the table does not know, get the most cautious shape."""
    tk, window = open_window()
    window.show([headline, "Check sensor and phone"], "title", DRAWN)
    palette = tw.PALETTES["light"]
    (_kind, (x, _y), word), rectangles, lines = chip_parts(tk)
    assert word["fill"] == palette["ink"] and lines == []
    right = x + 7 * len(headline) + tw.CHIP_PAD
    assert rectangles[0] == ((0, 2, right, 22), palette["chip-stale"])
    dashes = rectangles[1:]
    assert {fill for _coords, fill in dashes} == {palette["line-strong"]}
    top = [coords for coords, _fill in dashes if coords[1] == 2 and coords[3] == 4]
    assert [(x0, x1) for x0, _y0, x1, _y1 in top] == [
        (start, min(start + 4, right)) for start in range(0, right, 8)
    ]
    left = [coords for coords, _fill in dashes if coords[0] == 0 and coords[2] == 2]
    assert [(y0, y1) for _x0, y0, _x1, y1 in left] == [(2, 6), (10, 14), (18, 22)]


def test_fr018_strip_scales_with_the_display_density():
    tk, window = open_window(FakeTk(dpi=192.0))
    window.show(FRESH, "title", DRAWN)
    (_kind, (x, y), _word), rectangles, _lines = chip_parts(tk)
    assert (x, y) == (16, 24)
    assert rectangles[0][0][1::2] == (4, 44)
    window.show(STALE, "title", DRAWN)
    _word, _rectangles, lines = chip_parts(tk)
    assert {options["width"] for _coords, options in lines} == {2}


# --- brand tokens, contrast, dark mode ----------------------------------------------------


def test_nfr005_tk_window_colors_are_the_brand_tokens():
    for theme, palette in tw.PALETTES.items():
        for color_id, value in palette.items():
            assert value == COLOR[color_id][theme], (theme, color_id)
    assert tw.TINTS == {tw.LIGHT_THEME: LIGHT, tw.DARK_THEME: DARK}


def test_nfr005_tk_window_status_table_is_the_tokens_status_table():
    status = TOKENS["status"].values()
    assert tw.STATUS_COLORS == {entry["word"]: (entry["color"], entry["chip"]) for entry in status}
    unknown = TOKENS["unknown_headline"]
    assert tw.UNKNOWN_COLORS == (unknown["color"], unknown["chip"])
    # The strip's shape is the panel's: panel_layout.treatment, which tokens.json names too.
    for entry in status:
        assert treatment(entry["word"]) == entry["treatment"], entry["word"]
    assert treatment("SOMETHING NEW") == unknown["treatment"]


@pytest.mark.parametrize("theme", [tw.LIGHT_THEME, tw.DARK_THEME])
def test_nfr005_tk_window_text_meets_contrast_minimums(theme):
    palette, tint = tw.PALETTES[theme], tw.TINTS[theme]
    assert contrast(tint.ink, tint.paper) >= 7  # the panel, and the text view
    assert contrast(palette["muted"], tint.paper) >= 4.5  # the struck last: line
    assert contrast(palette["muted"], palette["fog"]) >= 4.5  # the key hints
    for headline in tw.STATUS_COLORS:
        _color, chip = tw.STATUS_COLORS[headline]
        banded = treatment(headline) in ("inverse", "stale")
        word, ground = ("band-text", "ink") if banded else ("ink", chip)
        assert contrast(palette[word], palette[ground]) >= 4.5, headline


def test_fr018_dark_mode_panel_is_night_paper():
    """The panel is never the brightest thing at the bedside."""
    tk, window = open_window(theme=tw.DARK_THEME)
    window.show(FRESH, "title", DRAWN)
    assert panel(tk).options["background"] == "#1C1E22"
    assert window.root.options["background"] == "#0E1116"
    assert tk.photos[0].data == to_ppm(render_bitmap(FRESH, 296, 128, stamp="02:14"), 2, DARK)


# --- the system theme and device pixels ---------------------------------------------------


class FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeRegistry:
    """Stands in for winreg: OpenKey and QueryValueEx under HKEY_CURRENT_USER."""

    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, value=1, error=None):
        self.value = value
        self.error = error
        self.opened = []

    def OpenKey(self, root, path):  # noqa: N802 (winreg's name)
        self.opened.append((root, path))
        if self.error is not None:
            raise self.error
        return FakeKey()

    def QueryValueEx(self, key, name):  # noqa: N802
        assert name == "AppsUseLightTheme"
        return self.value, 4  # REG_DWORD


@pytest.mark.parametrize("value,theme", [(0, "dark"), (1, "light")])
def test_fr018_auto_theme_reads_apps_use_light_theme_on_windows(value, theme):
    registry = FakeRegistry(value)
    assert tw.system_theme("win32", registry) == theme
    assert registry.opened == [("HKCU", tw.PERSONALIZE_KEY)]


def test_fr018_auto_theme_falls_back_to_light():
    assert tw.system_theme("linux", FakeRegistry(0)) == "light"
    assert tw.system_theme("darwin") == "light"
    assert tw.system_theme("win32", FakeRegistry(error=FileNotFoundError("no key"))) == "light"


def test_fr018_auto_theme_reads_the_real_registry_or_falls_back():
    """On Windows this reads the real value; elsewhere winreg cannot be imported."""
    assert tw.system_theme("win32") in ("light", "dark")
    if sys.platform != "win32":
        assert tw.system_theme("win32") == "light"


class FakeShcore:
    def __init__(self, result=0, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def SetProcessDpiAwareness(self, value):  # noqa: N802 (the Windows API's name)
        self.calls.append(value)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.parametrize("result,taken", [(0, True), (-2147024891, True), (-2147024809, False)])
def test_fr018_windows_is_told_the_window_draws_its_own_pixels(result, taken):
    shcore = FakeShcore(result)
    assert tw.use_device_pixels("win32", shcore) is taken
    assert shcore.calls == [1]  # PROCESS_SYSTEM_DPI_AWARE


def test_fr018_device_pixels_are_left_alone_off_windows_and_on_failure(monkeypatch):
    shcore = FakeShcore()
    assert tw.use_device_pixels("linux", shcore) is False
    assert shcore.calls == []
    assert tw.use_device_pixels("win32", FakeShcore(error=OSError("old Windows"))) is False
    assert tw.use_device_pixels("win32", object()) is False  # no such function
    monkeypatch.setattr(tw, "_shcore", lambda: None)
    assert tw.use_device_pixels("win32") is False


def test_fr018_shcore_is_typed_on_a_private_instance(monkeypatch):
    class Function:
        argtypes = None
        restype = None

    class Library:
        def __init__(self, name, use_last_error=False):
            self.name, self.use_last_error = name, use_last_error
            self.SetProcessDpiAwareness = Function()

    monkeypatch.setattr(ctypes, "WinDLL", Library, raising=False)
    shcore = tw._shcore()
    assert (shcore.name, shcore.use_last_error) == ("shcore", True)
    assert shcore.SetProcessDpiAwareness.argtypes == [ctypes.c_int]
    assert shcore.SetProcessDpiAwareness.restype is ctypes.c_long
    monkeypatch.delattr(ctypes, "WinDLL")
    assert tw._shcore() is None


# --- a real Tk window, where there is a display -------------------------------------------


NO_REAL_TK = 3  # what a child exits with when it cannot open a window, saying why


def run_real_tk(module, check):
    """Run `module.check()` in a fresh Python with a real Tk; skip locally when none can open.

    On CI (CI=true) a Tk that cannot open fails instead: the Test Runner gives
    these tests a display with xvfb-run, so a skip there would hide that the
    window's pixels and its ticker were never checked (HAZ-002, HAZ-016).

    In a child process, with one Tk interpreter, as the desktop app runs. Inside
    pytest, its file-descriptor capture swaps the standard handles under Tcl, and
    a second Tk interpreter in the same process then now and then cannot read
    its own library (seen on Windows: "Can't find a usable tk.tcl").
    """
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    result = subprocess.run(  # noqa: S603 - fixed arguments, this interpreter
        [sys.executable, "-c", f"import {module}; {module}.{check}()"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    if result.returncode == NO_REAL_TK:
        reason = result.stdout.strip()
        if os.environ.get("CI", "").lower() == "true":
            pytest.fail(f"real Tk must open on CI (the Test Runner runs under xvfb-run): {reason}")
        pytest.skip(reason)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == "ok"


def real_tkinter():
    """In a child: the real tkinter module, or exit NO_REAL_TK when this Python has none."""
    try:
        import tkinter
    except ImportError as error:
        print(f"no tkinter: {error}")
        sys.exit(NO_REAL_TK)
    return tkinter


def open_real_window():
    """In a child: a real window on the 2.9" panel, or exit NO_REAL_TK with no display."""
    tkinter = real_tkinter()
    try:
        return tw.GlanceWindow(tkinter, 296, 128, 2, tw.LIGHT_THEME)
    except tkinter.TclError as error:
        print(f"no display: {error}")
        sys.exit(NO_REAL_TK)


def child_window_holds_exactly_the_panel_pixels():
    window = open_real_window()
    try:
        now = datetime.now(UTC)
        assert window.show(STALE, "STALE - DO NOT TRUST - 16 min ago - Lightkeeper", now)
        expected = to_ppm(render_bitmap(STALE, 296, 128, stamp=stamp_text(now)), window.zoom)
        held = window.root.tk.call(window._photo, "data", "-format", "ppm")
        assert bytes(held) == expected
        assert window.root.title() == "STALE - DO NOT TRUST - 16 min ago - Lightkeeper"
        window.toggle()
        window.toggle()
        window.root.update_idletasks()
        # The size the fit was worked out for is the size Tk's packer asks for.
        assert (window.root.winfo_reqwidth(), window.root.winfo_reqheight()) == window.size
        width, height = window.root.winfo_screenwidth(), window.root.winfo_screenheight()
        assert window.size[0] <= width and window.size[1] <= height
    finally:
        window.destroy()
    print("ok")


def child_wake_from_another_thread_runs_on_tk_thread():
    """With no after() timer due for 5 s, another thread's wake-up still gets through at once.

    Tk's main loop waits for its next timer; a wake-up queued from another
    thread ends the wait. This is how the ticker keeps the window polling when
    a clock set back stalls Tk 8.6's wall-clock timers.
    """
    window = open_real_window()
    woken = []

    def on_wake():
        woken.append((threading.current_thread(), time.monotonic()))
        window.quit()

    caller = threading.Thread(target=window.wake, daemon=True)
    try:
        window.bind_wake(on_wake)
        window.after(100, caller.start)  # once the main loop is running
        window.after(5000, window.quit)  # never hang
        started = time.monotonic()
        window.mainloop()
        caller.join(5)
    finally:
        window.destroy()
    [(thread, at)] = woken
    assert thread is threading.current_thread()
    assert at - started < 2  # well before the 5 s timer
    print("ok")


def test_fr018_real_tk_unavailable_skips_locally_and_fails_on_ci(monkeypatch):
    no_display = subprocess.CompletedProcess(
        [], NO_REAL_TK, stdout="no display: couldn't connect to display\n", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: no_display)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="on CI"):
        run_real_tk("tests.test_tk_window", "child_window_holds_exactly_the_panel_pixels")
    monkeypatch.delenv("CI")
    with pytest.raises(pytest.skip.Exception, match="no display"):
        run_real_tk("tests.test_tk_window", "child_window_holds_exactly_the_panel_pixels")


def test_fr018_real_tk_window_holds_exactly_the_panel_pixels():
    run_real_tk("tests.test_tk_window", "child_window_holds_exactly_the_panel_pixels")


def test_fr018_real_tk_wake_from_another_thread_runs_on_tk_thread():
    run_real_tk("tests.test_tk_window", "child_wake_from_another_thread_runs_on_tk_thread")
