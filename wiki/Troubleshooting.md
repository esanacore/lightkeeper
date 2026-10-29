# Troubleshooting

Known issues and their fixes, from `docs/TROUBLESHOOTING.md` in the repository plus the behavior the tests pin down. If a display ever disagrees with the primary CGM app, trust the primary app first, then debug.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Reading the screen

### STALE - DO NOT TRUST

**What you see:** the first line is STALE, the second shows the last value with "last:", and the age keeps growing.

**What it means:** Nightscout has not received a reading newer than the stale limit (15 minutes by default, or `LK_STALE_MINUTES`). This is the display doing its job. Usual causes: the phone lost Bluetooth to the sensor, Trio is not running in the background, the phone is offline, or the sensor is warming up.

**What to do:** check the Dexcom G7 app and Trio on the primary phone first, then the Nightscout site in a browser. The display recovers on its own when fresh data arrives.

### "time is in the future"

**What you see:** STALE, with "time is in the future" where the age would be.

**What it means:** a reading is timestamped more than 2 minutes ahead of the display's clock, so one of three clocks is wrong: the phone, the Nightscout server, or the display device. A wrong clock fails in the safe direction, but it is still worth recording as an incident.

**What to do:** turn on automatic network time on every device. On a Raspberry Pi, check `timedatectl`.

### NO DATA with "Nightscout unreachable"

**What you see:** NO DATA, "Check sensor and phone", "Confirm on primary device", "Nightscout unreachable".

**What it means:** the program cannot reach Nightscout and has no earlier reading. Causes: a wrong `NIGHTSCOUT_URL`, DNS or network failure, the site is down, or the token is wrong or lacks the `readable` role. An HTML maintenance page or a response over 1 MB lands here too.

**What to do:** read the `lightkeeper:` line on stderr (next section), which names the link that failed. Open the URL in a browser from the same device. Re-create the token in Nightscout's Admin Tools if needed. Error messages never contain the token, so they are safe to paste into an issue.

### A `lightkeeper:` line on stderr

**What you see:** the screen says "Nightscout unreachable", and stderr (or `journalctl -u lightkeeper`) has one line starting `lightkeeper:`.

**What it means:** the line names the link that failed: the token was refused, the site needs a token, a 404, a 5xx answer, a DNS failure, no connection, a timeout, a TLS failure, an answer that was not a list of readings, or a refused redirect. It is written once when the failure starts or changes, not every refresh, and `lightkeeper: Nightscout reachable again` follows on recovery. It never contains the token. The screen still says "Nightscout unreachable" whatever failed, because its job is only to say the data cannot be trusted.

**What to do:** check what the line names. `docs/TROUBLESHOOTING.md`, "A `lightkeeper:` line on stderr", lists every line with the setting to check.

### NO DATA with no error line

**What it means:** Nightscout answered, but none of the newest twelve entries was a usable sensor glucose reading. Either there is no uploader yet (expected on a new site), or every recent entry was rejected: not type `sgv`, a value outside 39 to 401, a fractional or non-finite value, or a timestamp outside 2000 to 2100. Entries are never repaired, and one bad entry no longer takes the good ones down with it (HAZ-011).

**What to do:** look at `/api/v1/entries/sgv.json?count=3` in a browser with your token and check what the uploader is sending.

### IN RANGE with "Nightscout unreachable" on the last line

**What it means:** the last fetch failed, so the display shows the last good reading it has and says so. It keeps aging and turns STALE if Nightscout stays down. This is the designed degradation path (HAZ-002), not a freeze.

### Home Assistant shows the Lightkeeper sensors as unavailable

**What it means:** the publisher stopped, and Home Assistant is doing what it should instead of showing an old level (HAZ-013): the broker published Lightkeeper's Last Will, no update arrived within `expire_after`, or the service was stopped cleanly. There are four sensors: Glucose level, Glucose, Glucose reading age, and Last reading. A glucose sensor that reads unknown while the level reads STALE or NO DATA is also by design: no number is published for a reading that is not current. Last reading should likewise read unknown when there is no reading at all, because the status then carries no reading time; that is still to be checked against a real Home Assistant (GAP-002).

**What to do:** on the display device, `systemctl status lightkeeper` (the Status line shows the level) and `journalctl -u lightkeeper -f`. If the log says "Home Assistant publish failed", check the broker host, port (8883 with TLS), user, password, and ACL; Lightkeeper reconnects on its own each cycle and never stops the display over it.

### A dashboard shows an image that never changes

**What it means:** the writer may have died. The SVG carries a "written HH:MM UTC" stamp; if it is old, check `journalctl -u lightkeeper -f`, which is live because output is flushed every cycle. A failed write (full disk, locked file) is logged and retried instead of killing the watch loop (HAZ-011). A `--png` or `--bmp` image carries the local `HH:MM` it was drawn at (HAZ-014).

## Starting the program

### Exit code 2 on startup

**What you see:** one line, `Configuration error: ...`, naming the variable, its value and the clash, for example "Configuration error: NIGHTSCOUT_URL must use https: http would send the glucose readings and the token unencrypted", "Configuration error: LK_LOW=200 must be below LK_HIGH=180 (the default)", or "Configuration error: LK_LOW='abc' must be a whole number".

**What it means:** an `http://` URL, a URL with a query string or embedded login, a non-numeric threshold, or thresholds that do not satisfy `40 <= urgent low < low < high < urgent high <= 400`. The program refuses to run rather than run with settings that could hide a low (HAZ-006). Run once, a failed `--svg` or `--json` write also exits 2, and so do unusable `LK_MQTT_*` settings (TLS not true or false, plain MQTT to a remote broker, an invalid node id). A failed `--png` or `--bmp` write when run once, a `--demo-*` option without `--demo`, and a `--panel` too small for every screen also exit 2. `docs/TROUBLESHOOTING.md`, "Configuration error on startup", has the full list.

**What to do:** use the HTTPS URL with nothing after the host, and check the thresholds against [[Getting Started]]. Thresholds change only which word the display shows; match them to the primary app's alerts.

### "Configuration error: NIGHTSCOUT_URL is not set: set it to your Nightscout site's https address (see docs/ENV_VARS.md), or use --demo"

The variable is unset. There is no `.env` loader, so set it in the shell or the service definition.

### `--interval 5` still refreshes every 15 seconds

By design (FR-006), so a display never hammers a Nightscout site.

## Development environment

- `python tools/doctor.py` names the missing piece: Python 3.11+, the `constitution/` submodule (`git submodule update --init --recursive`), pytest, ruff, mypy, or the C++ toolchain (on Windows it looks inside WSL; only the firmware host tests need it).
- `make -C firmware/xteink test` needs `g++` or `clang++`, `make`, and Python 3. On Windows, run it in WSL (`wsl -- make -C firmware/xteink test`): MinGW toolchains (MSYS2, WinLibs, Git Bash) cannot link AddressSanitizer. A missing `clang-format` skips `format-check` with a note rather than failing.
- On Windows without WSL, the firmware host tests also run with the `clang++` that ships with the Swift toolchain, with clang's AddressSanitizer runtime (`clang_rt.asan_dynamic.dll`) on `PATH`. The full command is in `docs/TROUBLESHOOTING.md`, "Firmware host tests on Windows without WSL".
- `tests/test_gallery.py` fails after editing the vectors until you run `python tools/gen_display_gallery.py` and commit the result. See [[Display States]].
- The demo's panel tests need Node 20 or later (they skip without it locally); after editing `demo.html`, run `python tools/gen_demo_panel.py`.

Full environment reset:

```bash
deactivate 2>/dev/null; rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git submodule update --init --recursive
```

On Windows, remove `.venv` with `Remove-Item -Recurse -Force .venv` and activate with `.\.venv\Scripts\Activate.ps1`.

## Where to ask

Open an issue at https://github.com/esanacore/lightkeeper/issues. Security problems go through private vulnerability reporting ([[Security and Privacy]]). Questions about Trio, Nightscout, or the devices belong in those communities ([[Nightscout and Trio Setup]]). The maintainers cannot give medical advice. More answers are in the [[FAQ]].
