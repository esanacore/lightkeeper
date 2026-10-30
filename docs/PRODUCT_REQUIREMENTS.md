# Product Requirements

This document translates product intent into concrete implementation requirements. Each requirement carries a stable ID and explicit acceptance criteria. The mapping from requirement to verifying test is tracked in `docs/REQUIREMENTS_TRACEABILITY.md`.

## Requirement Levels

- `MUST`: Required for the current release or MVP.
- `SHOULD`: Important, but can be deferred if needed.
- `COULD`: Useful future enhancement.
- `WON'T`: Explicitly out of scope for the current release or MVP.

## Requirement Identifiers

- Functional requirements use `FR-`, non-functional use `NFR-`.
- Acceptance criteria use sub-identifiers such as `FR-001-AC-1`.
- IDs are stable and never reused.

## Product Summary

An open source stack for managing one person's type 1 diabetes (built first for a real household) with community tools (Trio, Nightscout) instead of the stock Dexcom and Omnipod experience, plus our own read-only displays. Users: the person with diabetes first, the builder as secondary viewer, and later anyone in the community. Current release goal (0.1.0): a trustworthy, tested `lightkeeper` that can drive a text display from Nightscout, and the documentation to stand up Nightscout and Trio.

## Functional Requirements

### Reading Glucose Data

**FR-001** `MUST` Parse Nightscout sensor glucose entries and reject anything untrustworthy.

- Level: `MUST`
- Acceptance criteria:
  - `FR-001-AC-1`: Entries of type `sgv` with a whole-number value from 39 to 401 mg/dL and a positive millisecond timestamp parse into a reading with a UTC timestamp.
  - `FR-001-AC-2`: Entries with missing, non-numeric, fractional, or out-of-range values, a non-`sgv` type, or a bad timestamp are rejected, not repaired.
  - `FR-001-AC-3`: An unknown trend direction keeps the number and shows an unknown arrow.

### Classifying Status

**FR-002** `MUST` Classify a fresh reading as URGENT LOW, LOW, IN RANGE, HIGH, or URGENT HIGH using configurable thresholds (defaults 55 / 70 / 180 / 250 mg/dL).

- Level: `MUST`
- Acceptance criteria:
  - `FR-002-AC-1`: Boundary values classify as documented (55 urgent low, 70 in range, 180 in range, 181 high, 250 urgent high).

**FR-003** `MUST` Never present stale or future-dated data as current.

- Level: `MUST`
- Acceptance criteria:
  - `FR-003-AC-1`: A reading older than the stale limit (default 15 minutes) is STALE, regardless of its value.
  - `FR-003-AC-2`: A reading more than 2 minutes in the future is STALE.
  - `FR-003-AC-3`: No reading at all is NO DATA.

### Displaying

**FR-004** `MUST` Render a status as at most four short ASCII lines suitable for a small e-ink display.

- Level: `MUST`
- Acceptance criteria:
  - `FR-004-AC-1`: Fresh readings show level, value with trend arrow, and age.
  - `FR-004-AC-2`: STALE leads with "STALE - DO NOT TRUST" and the last value's age; STALE and NO DATA tell the user to confirm on the primary device.
  - `FR-004-AC-3`: Sensor sentinels render as "LOW (<40)" and "HIGH (>400)".

**FR-005** `MUST` Degrade safely when Nightscout is unreachable or returns bad data.

- Level: `MUST`
- Acceptance criteria:
  - `FR-005-AC-1`: Network errors, timeouts, and non-JSON or non-list responses never crash the program.
  - `FR-005-AC-2`: After a failure, the last good reading is re-classified against the current time, so it becomes STALE once old enough.

**FR-006** `MUST` Provide a command-line interface with an offline demo mode and meaningful exit codes.

- Level: `MUST`
- Acceptance criteria:
  - `FR-006-AC-1`: `--demo` runs with no network.
  - `FR-006-AC-2`: Exit code is 0 for fresh in-range, 1 for anything needing attention, 2 for a configuration error (naming the variable, its value and the clash), an unusable option, a file a one-shot run could not write, or a `--demo-*` option without `--demo`, and 130 for a one-shot run stopped with Ctrl+C; `--watch` stopped with Ctrl+C or by systemd exits 0.
  - `FR-006-AC-3`: `--watch` refreshes no more often than every 15 seconds.
  - `FR-006-AC-4`: Piped, systemd and `--json` output is exactly the vector lines; only an interactive `--watch` on a terminal (TERM not dumb) draws the logbook frame, which is ASCII only, never rings the bell, redraws in place, and keeps reverse, underline and strike without color (`--no-color`, `NO_COLOR`).
  - `FR-006-AC-5`: When Nightscout fails, stderr gets one redacted line naming the failing link and the setting to check, once per change, and `lightkeeper: Nightscout reachable again` on recovery; the screen text is unchanged.
  - `FR-006-AC-6`: `--png PATH` and `--bmp PATH` write the panel pixels for `--panel PROFILE|WxH` (default `waveshare_2in9`) atomically, always stamped with the local `HH:MM` they were drawn at (HAZ-014).

**FR-009** `MUST` Keep every display implementation in lockstep with the shared golden vectors.

- Level: `MUST`
- Acceptance criteria:
  - `FR-009-AC-1`: The Python suite and the firmware host tests both pass every case in `spec/display_vectors.json`, rendering identical level and lines, including cases with several entries per fetch and custom thresholds.

**FR-011** `SHOULD` Draw any screen as an SVG image of the e-paper panel, and keep the docs gallery and demo generated from the shared vectors.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-011-AC-1`: `render_svg` draws every rendered line in order, headline bold and larger, all text inside the panel and XML-escaped.
  - `FR-011-AC-2`: `--svg PATH` writes the current screen atomically.
  - `FR-011-AC-3`: `docs/DISPLAY_STATES.md`, its images, and the demo's state table match what `tools/gen_display_gallery.py` produces from `spec/display_vectors.json`, and each SVG's title and the gallery's alt text are the screen's own lines.
  - `FR-011-AC-4`: `render_svg` draws each status's 1-bit shape from the panel's treatment table (plain, rule, inverse band, hatched frame with a struck `last:` line, and a dashed frame for NO DATA and any unknown headline) in the brand's Paper and Ink, with Muted only for the stamp and Line strong only for the edge, and keeps every line inside the content box with the value line larger than body text and never larger than the headline, at every accepted panel size.
  - `FR-011-AC-5`: The demo page stays one self-contained file of 512 KB or less: it loads nothing from the network, keeps no cookies and works without storage, never moves, blinks, ticks or sounds, announces a state change through a polite live region, keeps its SIMULATED labels, and every vector is one click away.

**FR-016** `SHOULD` Lay out the e-paper panel with integer arithmetic only, and hold every panel renderer to shared pixel vectors.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-016-AC-1`: The panel layout and drawer use integers only: no float literals, no `/` division, no `round()` and no `float()` in `panel_layout.py` and `epaper_bitmap.py`, every plan field is an int, and the C++ `lib/panel_bitmap` has no float, double, new or malloc.
  - `FR-016-AC-2`: `spec/panel_vectors.json` equals a regeneration by `tools/gen_panel_spec.py`: 237 cases (every display vector at each of six panel profiles, plus 3 stamped cases), each pinned by the CRC-32 and ink count of its packed rows, and every case's lines equal its display vector.
  - `FR-016-AC-3`: `spec/font5x8.json` equals `glyph_table()`, and the firmware's compiled-in font header equals the Python font.
  - `FR-016-AC-4`: The C++ `panel_bitmap` and the demo's `web/panel/panel.js` draw every case pixel for pixel (CRC-32 and ink count), refuse exactly the sizes and stamps Python refuses, and leave the caller's buffer untouched on a refusal.
  - `FR-016-AC-5`: A custom `WxH` that cannot hold every screen line inside the margins is refused with the reason (the smallest accepted panel is 157x70 and no side may exceed 4096 pixels), never drawn with text cut off.

**FR-017** `SHOULD` Give every screen a spoken form for screen readers that says what the screen says and is never more current.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-017-AC-1`: Every case in `spec/display_vectors.json` has exactly one sentence in `spec/spoken_vectors.json`, and Python (`spoken_text`) and Swift (`spokenText`) produce it from the classified status.
  - `FR-017-AC-2`: The age is always spoken; STALE leads with "Stale, do not trust." and says no trend word; NO DATA speaks no number.
  - `FR-017-AC-3`: The spoken form is used only through polite or passive accessibility channels (the iOS accessibility label, the demo's polite live region) and is never published to Home Assistant or any text-to-speech path.

**FR-018** `SHOULD` Show the glance on a desktop monitor as the real e-paper panel (`python -m lightkeeper.desktop`).

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-018-AC-1`: The window shows `render_bitmap`'s pixels for the current vector lines, stamped with the local `HH:MM` of the draw, at a whole-number zoom, in Paper and Ink, or in Night paper and Night ink with `--theme dark` (and with `--theme auto` when Windows asks apps for a dark theme). `t` swaps the pixels for the vector lines as text in TkFixedFont, with the STALE `last:` line struck through in Muted and the stamp kept on a row of its own, and a status strip above the panel shows the headline in its chip with its shape: a status border round the tinted chip for IN RANGE, LOW and HIGH, an Ink band with a 4 px leading status rule for URGENT LOW and URGENT HIGH, an Ink band with hatching in the margin only for STALE, and a dashed frame for NO DATA and any unknown headline.
  - `FR-018-AC-2`: The window re-ages with no fetch and shows STALE at the first stale millisecond, in one redraw, looking again at least every 30 seconds. A wall-clock jump of more than two fetch intervals (120 seconds at the fixed 60-second interval), in either direction, re-classifies at once and makes a fetch due; a ticker thread on the monotonic clock keeps the window polling when a clock set back stalls Tk 8.6's wall-clock `after()` timers. A fetch with no answer after two intervals counts as Nightscout unreachable and is retried on a new worker one interval later; its late answer is dropped. While 8 such threads are still stuck, no fetch starts and the screen goes on aging.
  - `FR-018-AC-3`: The CLI and the Pi never import tkinter. A setting that cannot be used, an unusable option, missing tkinter (a one-line hint to install `python3-tk`) or no display exits 2 with no window left open; `q` and the close box exit 0; Ctrl+C exits 130 with `lightkeeper: stopped`; an unexpected error in a Tk callback closes the window and is raised again. Nothing is written to stdout, and stderr only when the process has one: under `pythonw` or the `lightkeeper-window` gui script on Windows there is none, so nothing is printed.
  - `FR-018-AC-4`: The window never rings the bell, flashes the taskbar, changes `-alpha` or posts a notification, and `--on-top` is set once. Its title is `<headline> - <age line, or for NO DATA and any unknown headline the guidance line> - checked HH:MM - Lightkeeper`, every part but the clock verbatim from the lines, with `checking Nightscout...` in place of `checked HH:MM` until Nightscout first answers.
  - `FR-018-AC-5`: The whole window always fits the screen, at the largest whole zoom not above the one asked for (`--scale` times the display's whole-number scale), with one stderr line when it is drawn smaller; a panel that does not fit even at one screen pixel a panel pixel exits 2.

**FR-012** `SHOULD` Provide a read-only iOS companion app that shows the same status as every other display, using the same rules.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-012-AC-1`: The Swift rules pass every case in `spec/display_vectors.json`.
  - `FR-012-AC-2`: The app reads Nightscout with a readable token stored in the Keychain, over HTTPS only, refusing redirects that change scheme or host, and accepts only a site address (https, a host and an optional port, with no path, query, fragment or login), refused inline with the reason so it cannot be saved.
  - `FR-012-AC-3`: The app contains no pump or sensor communication (ADR-0004, ADR-0008).
  - `FR-012-AC-4`: The glance follows the shared hierarchy, built in LightkeeperCore's `ScreenPresentation` from the vector lines: on STALE no large number, arrow or unit, the STALE banner is the largest text and the old value appears only in the struck `last:` line at body size; NO DATA shows no number; the URGENT band is never shorter than the number; the status word is never smaller than `.title3`; and the VoiceOver label is the spoken form (FR-017).
  - `FR-012-AC-5`: With no usable site address saved, the app shows a setup card and makes no fetch; Check connection makes one read-only GET with the token in the header and reports the result in plain words; the outage start ("Nightscout unreachable since HH:MM") is the first failed fetch, and a late answer from an older fetch never changes the screen.

**FR-019** `SHOULD` Schedule every glance frame (widgets, StandBy, Live Activities) in advance, so a glance surface turns STALE on time even if the system never refreshes it.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-019-AC-1`: `glanceTimeline` gives a frame at now and at every instant the rendered lines change (each minute of the age, the first millisecond the reading is STALE, and for a future-dated reading the first millisecond its skew is 2 minutes or less), and each frame is exactly `renderLines(classify(...))` at its date.
  - `FR-019-AC-2`: STALE continues once a minute until the reading is maxMinutes old (default 120), the schedule always reaches the first STALE millisecond, and the last frame is STALE or NO DATA; no reading gives one NO DATA frame.
  - `FR-019-AC-3`: A fetch error adds "Nightscout unreachable" to every frame exactly as `renderLines` does; frames carry no new screen text, and the extension never uses `Text(date, style: .relative)`.
  - `FR-019-AC-4`: `reloadAfterMs(for:)` asks for a reload at most one reading interval (5 minutes) after now, and no later than the instant the timeline turns from fresh to STALE; it never asks at every frame boundary (once a minute), which would spend WidgetKit's daily reload budget in about an hour.

**FR-020** `SHOULD` Provide a read-only Android companion app that shows the same status as every other display, from the firmware's own C++ rules (`apps/android`).

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-020-AC-1`: Every case in `spec/display_vectors.json` gives exactly its lines, and every case in `spec/response_vectors.json` its reading, through JNI from the firmware's `glucose_rules` and `nightscout_json`, compiled in place by path with no copy under `apps/android`; a reading coming back from Kotlin is checked again by the firmware's parser, so a bad one shows NO DATA.
  - `FR-020-AC-2`: Every case in `spec/panel_vectors.json` (all six profiles, among them the 296x128 one the app shows, and the stamped cases) matches its CRC-32 and ink count through the firmware's `render_panel`; the image is drawn at a whole-number scale with filtering off, a refused image shows nothing (never the previous one), and a view too narrow for the image shows nothing rather than a crop.
  - `FR-020-AC-3`: The glance follows the shared hierarchy, built from the vector lines in `Presentation.kt`: on STALE no large number, separate arrow or unit, the STALE banner is the largest text and the old value appears only in the struck `last:` line at body size in Muted; NO DATA and any unknown headline show `--` and no number; the URGENT band is never shorter than the number; the status chip comes first in reading order at 20 sp bold or more; the headline is never under a system bar; and TalkBack reads the status area as the display lines in order.
  - `FR-020-AC-4`: The app fetches when its screen starts and every 60 seconds while it is visible, and re-ages the last good reading every 30 seconds and the moment the screen returns, with no fetch; returning also fetches when the last fetch began 15 seconds ago or more. One fetch runs at a time; one still running after 20 seconds is cancelled and shown as Nightscout unreachable; hiding the screen stops both timers, cancels a running fetch and drops its answer. With no usable address saved, the app shows "Add your Nightscout site to start" with no number and no level word, and makes no fetch.
  - `FR-020-AC-5`: Settings check the address as it is typed, with the iOS app's rule and reasons word for word (https, just the site), step the thresholds by 5 over the iOS ranges and Stale after by 1 from 6 to 60 with the iOS caution above 15; Save is refused for an invalid set, and an invalid set found on disk is reset to the defaults and written back.
  - `FR-020-AC-6`: The readable token is sealed with AES-256-GCM under an Android Keystore key and sent only in the `api-secret` header, over HTTPS with only the system's certificate authorities trusted, with no redirect followed (any redirect is a failed fetch); Save never rewrites or deletes a token field nobody touched, and the sealed token is deleted only on proof of damage, never because the Keystore could not be reached or a read ran alongside a write.
  - `FR-020-AC-7`: The manifest asks for `android.permission.INTERNET` only, with no service, receiver, provider, widget, notification, alarm or exact alarm; cleartext traffic, backup and device transfer are off; only the launcher activity is exported; no app source logs; and the APK ships no library but the Kotlin standard library (with its annotations).

**FR-008** `SHOULD` Publish the display status to Home Assistant (ADR-0010).

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-008-AC-1`: With `LK_MQTT_HOST` set, Home Assistant discovers sensors for level (an enum of the seven levels), glucose in mg/dL, reading age, and the time of the last reading, under a device named "Lightkeeper" ("Lightkeeper (<node id>)" for a non-default node id, with unique ids unchanged), and receives each refresh, so an automation can trigger on `URGENT LOW` or `STALE`.
  - `FR-008-AC-2`: When the publisher stops, the entities become unavailable (MQTT Last Will, `expire_after`, and `offline` on a clean `--watch` exit); state messages are never retained (HAZ-013).
  - `FR-008-AC-3`: The glucose number is published only for a fresh, measured reading; STALE, NO DATA, and sensor sentinels publish no number; the payload never carries a negative age (payload version 2, pending Eric's decision: `age_minutes` is null for a reading dated more than 2 minutes in the future), and the age sensor reads unknown for a negative or missing age (HAZ-013).
  - `FR-008-AC-4`: TLS is the default; plain MQTT is refused except to a broker on localhost, and a publish failure never stops the display.
  - `FR-008-AC-5`: `--json PATH` writes the same status payload atomically.

## Planned Requirements

These IDs are reserved for work that hasn't started. They are listed here, not declared above, so the traceability gate only enforces requirements the current release commits to. Promote one into Functional Requirements, in bold, in the same change that adds its first verifying test.

- FR-007 (SHOULD): Drive a physical e-ink display on a Raspberry Pi. Acceptance: the four rendered lines appear on the panel and refresh at least every 5 minutes.
- FR-010 (SHOULD): Run on an Xteink X4/X3 pocket e-ink reader over Wi-Fi. Acceptance: the device fetches from Nightscout, shows every vector state correctly, and updates at least every 5 minutes (ADR-0006).
- FR-013 (SHOULD): Display in mmol/L when configured. Acceptance: one setting switches every implementation to mmol/L with one decimal, the thresholds are entered in the same unit, and the shared vectors cover both units.
- FR-014 (COULD): Show the change since the previous reading (delta). Acceptance: a signed delta appears beside the arrow when two consecutive fresh readings exist, and is omitted otherwise.
- FR-015 (COULD): Show device status on hardware displays: battery level and time since the display itself last reached Nightscout. Acceptance: a low battery and an offline display are each visible on the panel without hiding the glucose line.

## Non-Functional Requirements

### Security

**NFR-001** `MUST` Protect health data and Nightscout credentials.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-001-AC-1`: Only HTTPS URLs are accepted unless local testing is explicitly enabled in code.
  - `NFR-001-AC-2`: The token never appears in error messages or program output.

### Reliability

**NFR-002** `MUST` Reject invalid configuration at startup.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-002-AC-1`: Thresholds must satisfy 40 <= urgent low < low < high < urgent high <= 400 and a positive stale limit, or the program exits.
  - `NFR-002-AC-2`: Every other setting (`NIGHTSCOUT_URL`, `NIGHTSCOUT_TOKEN`, the `LK_MQTT_*` settings, `--panel`) is checked once at startup, and an unusable one exits 2 with one line naming the variable, its value (never a secret) and the clash.

### Safety

**NFR-003** `MUST` Stay read-only.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-003-AC-1`: The client issues only GET requests to the `sgv` entries endpoint, with a bounded count.

### Testability

**NFR-004** `MUST` Keep the suite automated with 100% line and branch coverage, including the domain layer.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-004-AC-1`: `python -m pytest --cov` passes and reports coverage at or above the floor.

### Presentation

**NFR-005** `SHOULD` Keep presentation tokens in one machine-readable source and keep every status legible without color.

- Level: `SHOULD`
- Acceptance criteria:
  - `NFR-005-AC-1`: `assets/brand/tokens.json` and `docs/BRAND.md` list the same tokens, values and quoted contrast ratios, and every surface's colors (iOS `Palette.swift`, the Android `colors.xml`, the demo's CSS, the SVG panel, the terminal codes, and the desktop window's palette and panel tints) equal `tokens.json`.
  - `NFR-005-AC-2`: Text, chip and control pairings meet their WCAG 2.2 minimums: 4.5:1 for text, 3:1 for large text, control borders and focus rings, and 7:1 for Ink on light chips and Paper on Ink.
  - `NFR-005-AC-3`: Every status has its headline word and a 1-bit shape cue; an unknown headline gets the NO DATA treatment; status colors are never themeable; terminal codes keep a non-color cue for every level but IN RANGE.

## Explicit Non-Goals

- `WON'T` send any command to an insulin pump or calculate a dose (see `docs/SAFETY.md`).
- `WON'T` communicate with the Dexcom G7 sensor directly.
- `WON'T` write treatments or settings to Nightscout.
- `WON'T` replace the primary CGM app's alarms.

## Acceptance Criteria Summary

- [x] All `MUST` requirements for 0.1.0 (FR-001 to FR-006, FR-009, NFR-001 to NFR-004) have verifying tests and are `Verified` in `docs/REQUIREMENTS_TRACEABILITY.md`.
- [ ] The person with diabetes has reviewed the default thresholds and stale limit.

## Traceability

Each requirement above is tracked to its verifying tests and status in `docs/REQUIREMENTS_TRACEABILITY.md`.
