# How It Works

The whole stack has two halves with a one-way boundary between them. The therapy half is community software on the primary iPhone, the one the person with diabetes carries. The display half is this repository. Data flows from the first into the second and never back.

```mermaid
flowchart TD
    G7[Dexcom G7 sensor] -- BLE --> Dex[Dexcom G7 app<br/>kept as the sensor radio]
    Dex -- readings --> Trio[Trio on the primary iPhone<br/>dosing decisions]
    Trio -- BLE commands --> Pod[Omnipod 5 pod]
    Trio -- HTTPS upload --> NS[(Nightscout<br/>self-hosted)]
    NS -- HTTPS GET, readable token --> LK[Lightkeeper<br/>parse, classify, render]
    LK --> Pi[Bedside e-ink on a Pi]
    LK --> X4[Xteink pocket display]
    LK --> iOS[iOS companion app]
    LK --> HA[Home Assistant]
```

Everything above Nightscout is configured, tested, and contributed to upstream, but none of its code lives here. Everything below Nightscout is Lightkeeper. The detailed version, with the component diagram and the layer table, is `docs/ARCHITECTURE.md` in the repository.

## The data flow, step by step

1. The Dexcom G7 sends a reading every five minutes to the Dexcom G7 app. On iPhone, Trio reads that value from the same phone, which is why the Dexcom app stays installed as a background radio.
2. Trio runs its algorithm, commands the pod, and uploads glucose entries, insulin, and loop status to Nightscout.
3. `lightkeeper` requests the newest entries from Nightscout's `/api/v1/entries/sgv.json` endpoint over HTTPS, with a token that has only the readable role. It asks for twelve entries, never more than 288, and only ever issues GET.
4. The domain layer parses each entry and drops anything untrustworthy: a type other than `sgv`, a missing, fractional, non-finite, or out-of-range value (39 to 401 mg/dL), a timestamp outside 2000 to 2100. Nothing is repaired, and one poisoned entry never discards its neighbors (HAZ-011). The newest valid reading wins; two readings with the same timestamp resolve to the lower value.
5. The domain layer classifies that reading against the current time. Staleness comes first: older than the stale limit (15 minutes by default) or more than 2 minutes in the future means STALE, regardless of the value. Only a fresh reading is compared against the thresholds.

   ![How a reading becomes a word](https://raw.githubusercontent.com/esanacore/lightkeeper/main/assets/diagrams/classification.svg)

6. The application layer renders three or four short ASCII lines and the CLI returns an exit code. If the fetch failed, the last good reading is re-classified against the current time, so it ages into STALE instead of freezing on screen, and the last line says "Nightscout unreachable". The same status can be written as SVG and JSON and published to Home Assistant; under systemd, each finished cycle also pets the watchdog, so a hung cycle is restarted rather than left frozen.

Glucose data is classified Restricted at every step, and the token is Confidential. [[Security and Privacy]] has the classification table and the threat model.

## Layer boundaries

The Python package has three layers with dependencies that point inward only. A constitution CI check (`constitution-architecture.yml`) fails the build if an import crosses the wrong way.

| Layer | Path | May depend on | What lives there |
| --- | --- | --- | --- |
| domain | `src/lightkeeper/domain/` | nothing | `glucose.py` (parsing, `Trend`, `GlucoseReading`) and `status.py` (`Thresholds`, `Level`, `classify`). No I/O, no clock, no network. |
| application | `src/lightkeeper/application/` | domain | `monitor.py`: `current_status` (fetch, parse, classify, degrade) and `render_lines`. |
| infrastructure | `src/lightkeeper/infrastructure/` | domain | `nightscout.py` (the HTTPS client), `svg_display.py` and `epaper_bitmap.py` (the panel renderers), `mqtt.py` and `home_assistant.py` (publishing to Home Assistant, ADR-0010), and `systemd_notify.py` (the service watchdog). |
| composition root | `src/lightkeeper/cli.py` | all of the above | Reads the environment, builds the client and thresholds, runs the loop. |

The domain layer takes `now` as an argument rather than reading a clock, which lets every safety rule be tested with plain data and a fixed time.

## The four places the rules live

Display behavior is implemented more than once because the targets cannot share a runtime: a Raspberry Pi runs Python, an ESP32-C3 cannot, and an iPhone wants Swift. Four artifacts must agree.

1. **Python**, `src/lightkeeper/domain/`. The reference implementation and the one the bedside display runs.
2. **C++17**, `firmware/xteink/lib/glucose_rules/`. A line-for-line port with fixed-size buffers and no heap, for the Xteink pocket reader. Function names mirror the Python (`parse_entry`, `classify`, `render`) so reviewers can read the two side by side. See [[Firmware]].
3. **Swift**, `apps/ios/LightkeeperCore/`. The same rules and a read-only Nightscout client for the companion app. See [[Companion App]].
4. **The shared vectors**, `spec/display_vectors.json`. Thirty-nine cases, each one raw Nightscout entry (or none) or a list of entries, each entry with its age in minutes or seconds, optional custom thresholds, an optional fetch error, and the exact expected level and lines. The Python suite, the C++ host tests, and the Swift XCTest target all run every case, must render identical output, and assert the file's `spec_version`.

The vectors are the source of truth. A rule change touches the three implementations and the vectors in the same commit, then `python tools/gen_display_gallery.py` regenerates the gallery in `docs/DISPLAY_STATES.md` and the demo page from the same file. That is how parity is enforced by tests rather than by discipline, and the vectors have already caught real divergences. [[Testing and Quality]] describes the parity check, and [[Contributing]] the one-commit rule.

## What the renderer promises

Every screen is at most four lines of plain ASCII, sized for a 296 by 128 pixel panel. Fresh readings show the level, the value with a trend arrow, and the age. STALE leads with "STALE - DO NOT TRUST", then the last value, its age, and "Confirm on primary device". Sentinels render as words, never numbers. The SVG version adds a "written HH:MM UTC" stamp so a dashboard can tell a live writer from a dead one. Every screen is pictured in [[Display States]].

Back to [[Home]], or continue to [[Safety]].
