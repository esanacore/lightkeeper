# Safety Review Sheet

A short sheet for the person with diabetes, and their care team if they want it, to confirm or change the safety settings before any Lightkeeper display goes on a nightstand. It should take about fifteen minutes. The full reasoning is in [`SAFETY.md`](SAFETY.md); this page asks only the questions that need your answer.

Fill it in on paper, or edit this file, and give it back to Eric. Nothing changes until you have answered.

## What Lightkeeper is, and is not

- It **shows** the glucose number already in Nightscout on extra screens: an e-ink display, a pocket reader, an iPhone app.
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

A reading older than this is shown as **STALE - DO NOT TRUST**, crossed out on the phone app, even if the number itself looks fine. A new reading normally arrives every 5 minutes, so 15 minutes means about two missed readings.

| Setting | Default | Keep it? | Or change to |
| --- | --- | --- | --- |
| Stale after | 15 minutes | [ ] yes | ______ minutes |

A shorter limit flags trouble sooner but shows STALE more often during normal Bluetooth hiccups. A longer one shows an old number for longer. 15 is a common choice in the community.

## 3. Things to know before relying on it

- [ ] No Wi-Fi or no Nightscout means no new numbers. The screen ages into STALE rather than freezing.
- [ ] Even a fresh screen can be a few minutes behind the sensor (sensor, phone, upload, then display).
- [ ] mg/dL only for now.
- [ ] The bedside screen is for a glance. Anyone who sees LOW or URGENT LOW, or STALE at night, checks the phone.

## 4. Anything else

Worries, situations we haven't thought of, or things that happened with other devices that we should guard against:

&nbsp;

&nbsp;

## Sign-off

- Reviewed by: ______________________ Date: ____________
- Talked it over with the care team? [ ] yes [ ] not needed [ ] later

## What happens next (for Eric or an agent)

- Kept the defaults: mark step 6 done in `docs/AGENT_HANDOFF.md`, tick the TODO item, and record the date in `docs/MEMORY.md`.
- Changed a default: update `docs/ENV_VARS.md`, the defaults in all three implementations (Python `Thresholds`, firmware `lk::Thresholds`, Swift `Thresholds`), and the shared vectors. Changing an existing vector bumps `spec_version` and its three assertions. Then regenerate the gallery with `python tools/gen_display_gallery.py`.
- New concern: add it to the hazard log in `SAFETY.md` with a new HAZ ID before any code changes.
