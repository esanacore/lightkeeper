# Glossary

Terms used across this wiki and the repository's documentation, in alphabetical order. Where a term has a Lightkeeper-specific meaning, that meaning is given; otherwise the definition is the community's. Nothing here is medical advice.

**AID (automated insulin delivery).** A system in which software adjusts insulin delivery automatically from CGM data. Commercial examples include Omnipod 5's SmartAdjust; open source examples are Trio, Loop, and AndroidAPS. Lightkeeper is not an AID and contains no AID code.

**AndroidAPS.** The Android open source AID app. Deferred in ADR-0002 because it did not support Omnipod 5 as of October 2026.

**API_SECRET.** Nightscout's master credential. It grants write access, including to treatments. Trio needs it to upload. Lightkeeper never receives it; every display uses a readable token instead. See [[Security and Privacy]].

**CGM (continuous glucose monitor).** A sensor worn on the body that reports interstitial glucose every few minutes. The "primary CGM app" in the disclaimer is the manufacturer's app, or Trio, on the phone; its alarms are the safety net.

**Companion app.** The iOS app from ADR-0008, read-only first, with a gated bolus request path later. See [[Companion App]].

**Dexcom G7.** The CGM in the household setup. On iPhone, Trio reads it through the Dexcom G7 app, which stays installed as the sensor's radio.

**Exit code.** What `python -m lightkeeper` returns without `--watch`: 0 for fresh and IN RANGE, 1 for anything needing attention (including STALE and NO DATA), 2 for a setting or option that cannot be used or a failed file write, and 130 for a one-shot run stopped with Ctrl+C. See [[Getting Started]].

**FR / NFR.** Functional and non-functional requirement IDs (`FR-003`, `NFR-001`) in `docs/PRODUCT_REQUIREMENTS.md`, each with acceptance criteria (`FR-003-AC-2`) and verifying tests named with the ID.

**Glance timeline.** The frames a future iOS widget, StandBy card or Live Activity is handed in advance, with STALE scheduled at the first stale millisecond, so a glance the system stops refreshing ends on STALE (FR-019, `GlanceTimeline.swift`). The widget itself is not built yet.

**HAZ-nnn.** An entry in the hazard log in `docs/SAFETY.md`. See [[Safety]].

**IOB and COB (insulin and carbs on board).** What the AID algorithm estimates is still active or still being absorbed. Trio enforces a Max IOB on remote bolus requests. Not shown by Lightkeeper yet.

**Keeper 5x8.** The project's own pixel font (`font5x7.py`, exported as `spec/font5x8.json`): five cells wide, seven rows plus a descender, drawn at whole-number scales only. The name is one of the brand additions waiting for Eric's approval. See [[Brand]].

**Keeper's Logbook.** The design language in `docs/BRAND.md`: plain data on flat paper, a lo-fi frame, a 1-bit shape for every status, and nothing that moves or sounds. Its new tokens wait for Eric's approval.

**Loop.** The iOS open source AID app alongside Trio. Also supports Omnipod 5 since v3.14.7; kept as a fallback in ADR-0002.

**LoopFollow.** An iOS follower app for Loop and Trio users, and the reference client for Trio's Remote Control. Its safety model shapes HAZ-010.

**MQTT discovery.** Home Assistant's convention for creating entities from retained config messages on an MQTT broker. Lightkeeper uses it for four sensors (Glucose level, Glucose, Glucose reading age, and Last reading), with a Last Will and `expire_after` so they go `unavailable` when the publisher stops (ADR-0010, HAZ-013).

**mg/dL and mmol/L.** The two glucose units. US practice uses mg/dL; much of the world uses mmol/L (divide mg/dL by 18.016). Lightkeeper's thresholds, vectors, and screens are in mg/dL; mmol/L is reserved requirement FR-013.

**Nightscout.** The open source, self-hosted web app that stores CGM and AID data. The single data hub every Lightkeeper display reads from (ADR-0003). Trio writes to it; Lightkeeper only reads.

**NO DATA.** The level shown when there is no usable reading at all: nothing in Nightscout, or every recent entry rejected. See [[Display States]].

**Omnipod 5.** A tubeless insulin pump worn as disposable pods. Supported by Trio since v1.0.0 (September 15, 2026). A pod pairs with one controller at a time.

**OS-AID.** Open source automated insulin delivery: Trio, Loop, AndroidAPS.

**Panel vectors.** `spec/panel_vectors.json`: the 1-bit panel of every shared vector at six panel sizes, plus 3 stamped cases, pinned by CRC-32 and ink count; the Python, C++ and JavaScript panel renderers must all match it (FR-016).

**Readable token.** A Nightscout access token for a subject with only the `readable` role. The only credential Lightkeeper uses, set as `NIGHTSCOUT_TOKEN`.

**Remote Control (Trio).** Trio's feature for accepting commands from another app over push notifications, signed with a shared secret, subject to Trio's own limits. The only path by which the companion app may ever request a bolus.

**Sentinel.** Nightscout's placeholder for a reading outside the sensor's measurable range: 39 for below 40 mg/dL, 401 for above 400. Lightkeeper renders them as "LOW (<40)" and "HIGH (>400)", never as numbers.

**sgv.** Sensor glucose value, the only Nightscout entry type Lightkeeper accepts; `mbg` (meter) and `cal` (calibration) are rejected.

**Shared vectors.** `spec/display_vectors.json`: 39 golden cases that the Python, C++, and Swift implementations must all pass identically. Related files pin the raw responses (`spec/response_vectors.json`), the spoken sentences (`spec/spoken_vectors.json`) and the panel pixels (`spec/panel_vectors.json`). See [[Testing and Quality]].

**SMB (super micro bolus).** An oref algorithm feature in Trio and AndroidAPS that delivers small automatic boluses instead of only adjusting basal. A Trio setting decided with the care team; nothing in Lightkeeper touches it.

**spec_version.** The integer inside the shared vectors file that bumps when an existing case changes. All three implementations assert it.

**Spoken form.** One plain sentence per screen for screen readers, never more current than the screen (for example "In range. 112 milligrams per deciliter, steady. 3 minutes ago."), pinned in `spec/spoken_vectors.json` and shared by Python and Swift (FR-017). It is never sent to Home Assistant.

**STALE.** The level shown when the newest reading is older than the stale limit (15 minutes by default) or more than 2 minutes in the future. Shown as "STALE - DO NOT TRUST" and decided before the value is examined.

**Stamp.** The time an image was drawn, not the time of the reading: local `HH:MM` on exported PNG and BMP panels, `written HH:MM UTC` on the SVG, `checked HH:MM:SS` on the terminal frame (HAZ-014).

**Thresholds.** The four mg/dL boundaries (`LK_URGENT_LOW`, `LK_LOW`, `LK_HIGH`, `LK_URGENT_HIGH`). They change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

**Trend arrow.** Nightscout's direction string (`DoubleUp`, `Flat`, `SingleDown`, and so on), rendered as plain ASCII: `^^`, `^`, `/`, `->`, `\`, `v`, `vv`, or `?` for anything unrecognized.

**Trio.** The iOS open source AID app, built from source, that makes every dosing decision in the household setup (ADR-0002). Not Lightkeeper code.

**Watchdog (systemd).** `WatchdogSec=` in `deploy/lightkeeper.service`: Lightkeeper checks in after every finished refresh, and systemd restarts the service if the check-ins stop, so a hung cycle never leaves a frozen screen (HAZ-002).

**#WeAreNotWaiting.** The community movement of people with diabetes and their families who built open source CGM and AID tools rather than wait for commercial ones. Nightscout, xDrip, Loop, AndroidAPS, and Trio all grew from it.

**xDrip / xDrip+ / xDrip4iOS.** Community CGM collector apps. xDrip+ on Android can replace the vendor app entirely; xDrip4iOS can follow a Nightscout site. Relevant to the Android alternative deferred in ADR-0002.

**Xteink X4 / X3.** Pocket e-ink readers built on an ESP32-C3, the firmware target in ADR-0006, with CrossPoint as their community firmware. The X4 Pro adds a front light. See [[Hardware]] and [[Firmware]].

Back to [[Home]], or see the [[FAQ]].
