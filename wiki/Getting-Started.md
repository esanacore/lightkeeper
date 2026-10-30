# Getting Started

This page gets `lightkeeper` running on a workstation, first with canned data and then against a real Nightscout site. The complete setup guide, including the Raspberry Pi bedside display as a systemd service, is `docs/SETUP.md` in the repository; the commands here are the short path.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Requirements

Python 3.11 or newer and Git. The firmware host tests additionally need a C++17 compiler and `make`, but nothing on this page requires them. Supported platforms are Windows 11 with PowerShell 7, macOS 14 or newer, Ubuntu 22.04 or newer, and Raspberry Pi OS Bookworm. `lightkeeper` has no runtime dependencies; everything in the data path is the Python standard library (ADR-0005 in [[Architecture Decisions]]). The desktop window also needs Tk, the windowing toolkit behind the standard library's `tkinter`: the python.org installers for Windows and macOS include it; on Debian, Ubuntu and Raspberry Pi OS install `python3-tk` (`sudo apt install python3-tk`); with Homebrew's `python@3.12`, install `python-tk@3.12`. The command-line tool never loads it.

## Install

Clone with the submodule, because the constitution's scripts and templates live in `constitution/`.

```bash
git clone --recurse-submodules https://github.com/esanacore/lightkeeper
cd lightkeeper
```

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS (zsh) or Linux and Raspberry Pi (bash):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then run `python tools/doctor.py` (use `python3` on macOS and Linux). It checks the Python version, the submodule, the test and lint tools, and the C++ toolchain, and names exactly what is missing.

## Demo mode

Demo mode serves one made-up reading and never opens a network connection, so it is safe to run anywhere.

```bash
python -m lightkeeper --demo                          # IN RANGE, 112 mg/dL, 3 minutes old
python -m lightkeeper --demo --demo-mgdl 62           # LOW
python -m lightkeeper --demo --demo-mgdl 62 --demo-trend SingleDown   # LOW with a falling arrow
python -m lightkeeper --demo --demo-mgdl 55           # URGENT LOW
python -m lightkeeper --demo --demo-minutes-ago 40    # STALE - DO NOT TRUST
```

The `--demo-*` options work only with `--demo`; without it they exit 2.

For a click-through of every possible screen without installing anything, open `demo.html` from the repository in a browser, or read [[Display States]].

## Running against Nightscout

You need a Nightscout site served over HTTPS and an access token whose subject has the **readable** role only. Create the token in Nightscout under Admin Tools, Subjects. Never use the site's `API_SECRET`: it grants write access to treatments, and Lightkeeper has no use for it. [[Nightscout and Trio Setup]] covers standing up the site.

Windows (PowerShell):

```powershell
$env:NIGHTSCOUT_URL = "https://ns.example.com"
$env:NIGHTSCOUT_TOKEN = Read-Host "Readable token"
python -m lightkeeper
```

macOS or Linux:

```bash
export NIGHTSCOUT_URL="https://ns.example.com"
read -rs NIGHTSCOUT_TOKEN && export NIGHTSCOUT_TOKEN
python -m lightkeeper
```

`Read-Host` and `read -rs` keep the token out of shell history. There is no `.env` loader; set variables in the shell or the service definition.

Useful options:

- `--watch` refreshes until Ctrl+C (exit 0). In an interactive terminal it redraws one screen in place inside a plain ASCII frame headed `o))) lightkeeper   checked HH:MM:SS`; `--no-color` or `NO_COLOR` keeps its reverse video, underline and strike without color; piped or under systemd it prints exactly the screen lines, with a dashed separator between refreshes. `--interval N` sets the seconds between refreshes, with a floor of 15 seconds so it never hammers the server. Output is flushed every cycle, so `journalctl -f` is live under systemd.
- `--svg PATH` also writes each screen as an SVG image of the e-paper panel, with a small "written HH:MM UTC" stamp so a dashboard can tell a live writer from a dead one. The file is written to a temporary name and renamed, so a reader never sees a half-written image. In watch mode a failed write (full disk, locked file) is logged and retried next cycle; run once, it is exit code 2.
- `--json PATH` writes the same status as JSON (level, glucose, trend, age, the screen's lines, any error), replaced atomically the same way. The glucose field is empty whenever the level is STALE or NO DATA. The payload is version 2 (still waiting for Eric's sign-off): the age is never negative, and `reading_at` gives the reading's time. Home Assistant publishing is set up separately; see `docs/SETUP.md`.
- `--png PATH` and `--bmp PATH` write the exact 1-bit panel pixels, replaced atomically and stamped with the local `HH:MM` they were drawn at; `--panel` picks the panel (`waveshare_2in9` by default, `trmnl`, `kindle`, or a size such as `800x480`).
- `--version` prints the package version.

## The desktop window

`python -m lightkeeper.desktop` shows the glance on a computer monitor as the real e-paper panel: the same 1-bit pixels the Pi panel would draw, enlarged by a whole number, stamped with the local `HH:MM` of each redraw, under a status strip with the headline's shape. It reads the same environment variables as the command-line tool (below), fetches every 60 seconds, and re-ages the last good reading on its own clock, so it turns STALE on time even when no fetch answers; a fetch with no answer after two minutes shows as `Nightscout unreachable`. It never rings, flashes or pops up a notification, does not publish to Home Assistant, and writes no files.

```bash
python -m lightkeeper.desktop --demo                         # canned reading, no network
python -m lightkeeper.desktop --scale 3 --on-top
python -m lightkeeper.desktop --panel 800x480 --theme dark
```

Keys: `r` checks Nightscout now, `t` switches between the panel's pixels and its lines as text, and `q` quits, as the close box does. The title carries the headline, the age line (for NO DATA, the guidance line) and `checked HH:MM`, for example `IN RANGE - 3 min ago - checked 07:42 - Lightkeeper`, so a screen reader or the taskbar shows them too; until Nightscout first answers it says `checking Nightscout...` instead of the time.

- `--scale 2` (the default) or `3` counts 96 dpi pixels, so the panel keeps its size on a scaled display: at 200%, `--scale 2` draws each panel pixel as 4x4 device pixels. The whole window always fits the screen; when it would not, the panel is drawn at the largest whole zoom that fits, with one line on stderr saying so. Counting 96 dpi pixels here is a default pending Eric's decision.
- `--panel` takes the same profiles as the command-line tool (`waveshare_2in9` by default, `trmnl`, `kindle`, or a size such as `800x480`).
- `--theme auto` (the default) follows the Windows app theme, read once at startup; on macOS and Linux it is light. `--theme dark` draws the panel in Night paper and Night ink, so the window is not the brightest thing at the bedside.
- `--on-top` keeps the window above other windows.

Installed with `pip install -e .`, the same window is also the `lightkeeper-window` launcher (D12, pending Eric's review). On Windows that launcher has no console, so a configuration error, such as `NIGHTSCOUT_URL` unset, exits 2 with no message; run `python -m lightkeeper.desktop` in a terminal to see it.

| Code | Meaning |
| --- | --- |
| `0` | The window was closed, with `q` or the close box. |
| `2` | A setting or option that cannot be used, a panel too large for the screen even at one screen pixel a panel pixel, no tkinter, or no display to open a window on. No window is left open. |
| `130` | Stopped with Ctrl+C in the terminal that started it (`lightkeeper: stopped`). |

An unexpected error inside the window closes it and Python prints the traceback, so a window that has stopped updating never stays on screen looking alive. The window has been checked by hand on Windows 11 only, not yet on macOS or on Linux with a display.

## The Android app

The read-only Android app is a sideloaded debug APK for Android 8.0 or later; [[Companion App]] describes it, and `apps/android/README.md` in the repository has the build and install steps (JDK 17 or 21 and the Android SDK, then `./gradlew assembleDebug` and `adb install`). On Windows, keep the checkout path to about 60 characters or fewer, such as `C:\src\lightkeeper`: from a longer one the native build fails on the Windows path limit.

## Environment variables

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `NIGHTSCOUT_URL` | Yes, unless `--demo` | none | Base URL of the Nightscout site. Must be `https://`. No query, fragment, or embedded login. |
| `NIGHTSCOUT_TOKEN` | No | none | Access token with the readable role only. Treated as a secret and redacted from every error message. |
| `LK_URGENT_LOW` | No | `55` | Urgent low threshold in mg/dL, at or below. |
| `LK_LOW` | No | `70` | Low threshold in mg/dL, below. |
| `LK_HIGH` | No | `180` | High threshold in mg/dL, above. |
| `LK_URGENT_HIGH` | No | `250` | Urgent high threshold in mg/dL, at or above. |
| `LK_STALE_MINUTES` | No | `15` | Minutes before a reading is shown as STALE. |

Thresholds must satisfy `40 <= LK_URGENT_LOW < LK_LOW < LK_HIGH < LK_URGENT_HIGH <= 400`, and the stale limit must be positive, or the program exits at startup rather than run with settings that could hide a low. Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app. The authoritative list is `docs/ENV_VARS.md`.

## Exit codes

When run without `--watch`, the exit code is a signal for scripts, cron, and Home Assistant.

| Code | Meaning |
| --- | --- |
| `0` | Fresh reading, IN RANGE. |
| `1` | Someone should look: LOW, URGENT LOW, HIGH, URGENT HIGH, STALE, or NO DATA. |
| `2` | Configuration error (missing `NIGHTSCOUT_URL`, an `http://` URL, a non-numeric or out-of-order threshold, unusable `LK_MQTT_*` settings), a failed `--svg`, `--json`, `--png` or `--bmp` write when run once, a `--demo-*` option without `--demo`, or an unusable `--panel`. |
| `130` | A one-shot run stopped with Ctrl+C, so cron or Home Assistant never read it as fresh and in range. `--watch` stopped that way exits 0. |

## Before anyone relies on it

Run the display side by side with the primary CGM app for at least one full sensor session and log every mismatch, freeze, or missed STALE. That manual validation is the gate before a display is used for real; see [[Safety]] and [[Testing and Quality]]. If something looks wrong, [[Troubleshooting]] lists the common causes.
