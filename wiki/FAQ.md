# FAQ

Questions that come up about Lightkeeper, answered from the repository's documentation. Nothing here is medical advice.

## About trusting it

**Is Lightkeeper a medical device?**
No. It is a secondary, read-only display for awareness only, treated internally as the equivalent of IEC 62304 Class A because no software failure alone can cause injury. Always confirm on the primary CGM app before acting. See [[Safety]].

**Can it ever give insulin, or change pump or sensor settings?**
No. The repository contains no code that commands a pump, calculates a dose, changes therapy settings, or talks to a sensor (ADR-0004). The only planned exception is narrow and gated: the companion app may someday *request* a bolus through Trio's own remote protocol, where Trio decides. See [[Companion App]].

**Why does it say STALE when the number was fine a moment ago?**
Because the reading is older than 15 minutes (or your `LK_STALE_MINUTES`), or dated more than 2 minutes in the future. An old number is not evidence of a current one, so Lightkeeper stops presenting it as current. The screen keeps the last value visible, labeled "last:", with its age. See [[Troubleshooting]].

**Would it show a 40-minute-old low as URGENT LOW?**
No. Staleness is checked before the value. A 45 mg/dL reading that is 40 minutes old shows STALE, and that exact case is a shared test vector (`stale_beats_urgent_low`). See [[Display States]].

**What happens if Nightscout goes down?**
The display does not freeze. It shows the last good reading with "Nightscout unreachable" on the last line and lets it age into STALE; with no earlier reading it shows NO DATA (HAZ-002).

**What if one bad entry arrives in the data?**
It is dropped and the good readings around it are kept. Values are range-checked before conversion and timestamps are bounded to 2000 to 2100, so a `NaN`, a `1e+30`, or a seconds-instead-of-milliseconds upload cannot blank the screen or read as 1970 (HAZ-011).

**Can I rely on it for overnight alarms?**
No. Lightkeeper never sounds, vibrates, or pushes a notification, and the project avoids the word "alarm". The primary CGM app's alarms stay on the phone. Lightkeeper offers secondary awareness: a glanceable screen, and exit codes an automation can react to as an extra layer. See [[Community Research]].

## About setting it up

**Do I need a Nightscout site?**
Yes, for anything beyond demo mode. Nightscout is the single data hub every display reads from (ADR-0003), reachable from anywhere, so a cloud VPS or managed host rather than a machine at home. See [[Nightscout and Trio Setup]].

**Which token do I use?**
A token for a Nightscout subject with the `readable` role only, created under Admin Tools, Subjects. Never the `API_SECRET`; it grants write access and Lightkeeper has nothing to write. See [[Security and Privacy]].

**Can I try it without any of that?**
Yes. `python -m lightkeeper --demo` serves one made-up reading and never touches the network; `--demo-mgdl` and `--demo-minutes-ago` let you see each state. `demo.html` in the repository shows every screen in a browser, with a button for every vector. See [[Getting Started]].

**Does it support mmol/L?**
Not yet. Thresholds and screens are in mg/dL. mmol/L is reserved requirement FR-013, alongside delta (FR-014) and device status (FR-015). See [[Roadmap]].

**Can I change the thresholds?**
Yes, with `LK_URGENT_LOW`, `LK_LOW`, `LK_HIGH`, `LK_URGENT_HIGH`, and `LK_STALE_MINUTES`. They must be in order within 40 to 400 or the program refuses to start (HAZ-006). Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

**What hardware do I need?**
For a bedside display, a Raspberry Pi Zero 2 WH and a Waveshare 2.9 inch black and white e-paper HAT; the Python code runs on it as is. For a pocket display, the Xteink X4 Pro, once the firmware's device build exists. No Mac is needed anywhere. See [[Hardware]].

**Does it work with Home Assistant?**
Today through the exit code and the `--svg` file (a `command_line` sensor and a `local_file` camera). A proper integration (FR-008) is planned.

## About the project

**Why are the rules written three times?**
Because a Raspberry Pi runs Python, an ESP32-C3 cannot, and an iPhone wants Swift. Drift is handled by `spec/display_vectors.json`, 39 cases that all three implementations must pass identically, and by the rule that a change touches all of them in one commit. See [[How It Works]] and [[Testing and Quality]].

**How tested is it?**
177 Python tests at 100% line and branch coverage against a 90% floor, 287 firmware checks under AddressSanitizer and UBSan, the Swift vector tests in CI on macOS and Linux, and a traceability matrix in which every declared requirement has a verifying test named with its ID. See [[Testing and Quality]].

**Why Trio and not Loop or AndroidAPS?**
Trio for its oref algorithm features, active community, and Omnipod 5 support since v1.0.0. Loop remains a fallback; AndroidAPS lacked Omnipod 5 support as of October 2026. See [[Architecture Decisions]].

**How do I report a bug, a security problem, or an idea?**
Bugs and ideas: open an issue at https://github.com/esanacore/lightkeeper/issues, with synthetic data only. Security problems: private vulnerability reporting on the repository's Security tab, or email the maintainer; never a public issue. See [[Security and Privacy]] and [[Contributing]].

The name: a lighthouse watches all night and never steers the ship ([[Brand]]). Terms you did not recognize are in the [[Glossary]].
