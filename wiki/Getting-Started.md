# Getting Started

This page gets `lightkeeper` running on a workstation, first with canned data and then against a real Nightscout site. The complete setup guide, including the Raspberry Pi bedside display as a systemd service, is `docs/SETUP.md` in the repository; the commands here are the short path.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Requirements

Python 3.11 or newer and Git. The firmware host tests additionally need a C++17 compiler and `make`, but nothing on this page requires them. Supported platforms are Windows 11 with PowerShell 7, macOS 14 or newer, Ubuntu 22.04 or newer, and Raspberry Pi OS Bookworm. `lightkeeper` has no runtime dependencies; everything in the data path is the Python standard library (ADR-0005 in [[Architecture Decisions]]).

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
python -m lightkeeper --demo --demo-mgdl 55           # URGENT LOW
python -m lightkeeper --demo --demo-minutes-ago 40    # STALE - DO NOT TRUST
```

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

- `--watch` refreshes until Ctrl+C, which exits cleanly. `--interval N` sets the seconds between refreshes, with a floor of 15 seconds so it never hammers the server. Output is flushed every cycle, so `journalctl -f` is live under systemd.
- `--svg PATH` also writes each screen as an SVG image of the e-paper panel, with a small "written HH:MM UTC" stamp so a dashboard can tell a live writer from a dead one. The file is written to a temporary name and renamed, so a reader never sees a half-written image. In watch mode a failed write (full disk, locked file) is logged and retried next cycle; run once, it is exit code 2.
- `--version` prints the package version.

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
| `2` | Configuration error (missing `NIGHTSCOUT_URL`, an `http://` URL, a non-numeric or out-of-order threshold), or a failed `--svg` write when run once. |

## Before anyone relies on it

Run the display side by side with the primary CGM app for at least one full sensor session and log every mismatch, freeze, or missed STALE. That manual validation is the gate before a display is used for real; see [[Safety]] and [[Testing and Quality]]. If something looks wrong, [[Troubleshooting]] lists the common causes.
