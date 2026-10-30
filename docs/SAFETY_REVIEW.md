# Safety Review Sheet

A short sheet for the person with diabetes, and their care team if they want it, to confirm or change the safety settings before any Lightkeeper display goes on a nightstand. It should take about fifteen minutes. The full reasoning is in [`SAFETY.md`](SAFETY.md); this page asks only the questions that need your answer.

Fill it in on paper, or edit this file, and give it back to Eric. Nothing changes until you have answered.

## What Lightkeeper is, and is not

- It **shows** the glucose number already in Nightscout on extra screens: an e-ink display, a pocket reader, an iPhone app, an Android phone app, a window on a computer.
- It **never** talks to the pump or the sensor, never doses, and never changes Trio settings.
- It **never** alarms. The Dexcom and Trio alerts on the phone stay the only alarms.
- When it is unsure (data too old, a clock wrong, Nightscout down), it says **STALE - DO NOT TRUST** or **NO DATA** instead of showing a number.
- Every screen means "confirm on the phone before you act."

- [ ] I understand this, and I'm comfortable with the extra screens on these terms.

## 1. The words on the screen

The display picks one word from the number. The thresholds below change only that word. They do not touch dosing or the phone's alarms, and they work best when they match the alert levels already set on the phone, in the Dexcom G7 app and in Trio.

| Word | Rule | Default | Keep it? | Or change to |
| --- | --- | --- | --- | --- |
| URGENT LOW | at or below | 55 mg/dL | [ ] yes | ______ mg/dL |
| LOW | below | 70 mg/dL | [ ] yes | ______ mg/dL |
| IN RANGE | everything between LOW and HIGH | 70 to 180 mg/dL | | |
| HIGH | above | 180 mg/dL | [ ] yes | ______ mg/dL |
| URGENT HIGH | at or above | 250 mg/dL | [ ] yes | ______ mg/dL |

The four numbers must go up in order, and stay between 40 and 400. A display refuses to start with anything else, so a typo can't quietly hide a low.

- [ ] These match the alerts on my phone (or I've written the numbers that do).

## 2. When a number stops being trusted

A reading older than this is shown as **STALE - DO NOT TRUST**, crossed out on the phone apps, even if the number itself looks fine. A new reading normally arrives every 5 minutes, so 15 minutes means about two missed readings.

| Setting | Default | Keep it? | Or change to |
| --- | --- | --- | --- |
| Stale after | 15 minutes | [ ] yes | ______ minutes |

A shorter limit flags trouble sooner but shows STALE more often during normal Bluetooth hiccups. A longer one shows an old number for longer. 15 is a common choice in the community.

## 3. Things to know before relying on it

- [ ] No Wi-Fi or no Nightscout means no new numbers. The screen ages into STALE rather than freezing.
- [ ] Even a fresh screen can be a few minutes behind the sensor (sensor, phone, upload, then display).
- [ ] A screen or an image file keeps its last picture if the display stops updating. Exported images show the time they were drawn (`HH:MM`), not the time of the reading; check the age line, and the phone when in doubt.
- [ ] The Android app is current only while it is open: it has no widget, and it re-ages the last reading the moment it comes back. The computer window ages on its own and stamps its picture with the time it was drawn, like an exported image.
- [ ] mg/dL only for now.
- [ ] The bedside screen is for a glance. Anyone who sees LOW or URGENT LOW, or STALE at night, checks the phone.

## 4. Anything else

Worries, situations we haven't thought of, or things that happened with other devices that we should guard against:

&nbsp;

&nbsp;

## 5. Screen text v2 (ADR-0011)

Three small wording changes. Each one says less than today about old or missing data, and none of them touches a fresh screen. Nothing changes until both lines are signed.

| Change | Today | Proposed | Agree? |
| --- | --- | --- | --- |
| No arrow beside an old number | `last: 45 mg/dL v` | `last: 45 mg/dL` | [ ] yes [ ] no |
| NO DATA names the link that failed when the display can't reach Nightscout | `Check sensor and phone` | `Check Nightscout/Wi-Fi` | [ ] yes [ ] no |
| A STALE age never matches a fresh one (15 min 1 s old) | `15 min ago` | [ ] `16 min ago` (round up) [ ] `over 15 min ago` | pick one |

- Kaitlin: ______________________ Date: ____________
- Eric: ______________________ Date: ____________

## Sign-off

- Reviewed by: ______________________ Date: ____________
- Talked it over with the care team? [ ] yes [ ] not needed [ ] later

## What happens next (for Eric or an agent)

- Kept the defaults: mark Kaitlin's review step done in `docs/AGENT_HANDOFF.md`'s Next Steps, tick the TODO item, and record the date in `docs/MEMORY.md`.
- Changed a default: update `docs/ENV_VARS.md`, the defaults in all three implementations (Python `Thresholds`, firmware `lk::Thresholds`, Swift `Thresholds`) and in the Android app's settings (`apps/android/app/src/main/java/com/esanacore/lightkeeper/Settings.kt`), and the shared vectors. Changing an existing vector bumps `spec_version` and its four assertions (Python, firmware, Swift, and the Android app's instrumented `testTheVectorsAreTheVersionThisSuiteWasWrittenFor`). Then regenerate the gallery with `python tools/gen_display_gallery.py`, the panel vectors with `python tools/gen_panel_spec.py`, the spoken vectors with `python tools/gen_spoken_vectors.py`, and the demo's panel block with `python tools/gen_demo_panel.py`. The iOS and Android steppers move in steps of 5, so a new default must sit on that grid or the ranges in `GlucoseModel.swift` and `Settings.kt` move too.
- New concern: add it to the hazard log in `SAFETY.md` with a new HAZ ID before any code changes.
- Signed section 5: ADR-0011 is implemented in one pull request at `spec_version` 2 (its promotion criteria), then marked Accepted in `docs/adr/README.md`.
