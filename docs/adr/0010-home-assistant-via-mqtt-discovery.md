# ADR-0010: Publish to Home Assistant over MQTT Discovery

Status: Proposed

Date: 2026-10-25

## Relationships

- Extends: ADR-0005
- Supersedes: none
- Related: FR-008, GAP-002, docs/SAFETY.md (Intended Use, "No alarms"), ADR-0009

## Promotion Criteria

- Eric picks the transport. Gate: Eric.
- Because Home Assistant automations can alert on what this publishes, `docs/SAFETY.md` gets a hazard entry for the Home Assistant path, with a tested mitigation for each failure below, before the feature ships. Gate: Eric, with the person with diabetes informed.

## Context

FR-008: Home Assistant shows a sensor with level, value, and age, and can trigger an automation on URGENT LOW or STALE.

Home Assistant already ships a Nightscout integration. It creates `sensor.blood_glucose` with the last reading as its state and the trend in its attributes. It has no notion of staleness: its documented example turns on lights when the value drops low, and that automation would fire on a reading that is 40 minutes old. Lightkeeper's value here is the same classification every display uses (STALE before any range check, NO DATA when unsure), not another copy of the number.

So the hazard that decides the design is a Home Assistant entity that keeps showing a fresh-looking level after the publisher dies (a Pi loses power, Wi-Fi drops, the process crashes). A display that freezes is HAZ-002. An automation input that freezes is the same hazard one step removed.

## Options

1. **MQTT discovery.** Publish a retained discovery config under `homeassistant/sensor/lightkeeper/.../config`, then retained state on each refresh: level as the state, value, age in minutes, trend, and the fetch error as attributes. Register an MQTT Last Will so the broker publishes `offline` to an availability topic the moment the connection drops, and set `expire_after` so Home Assistant marks the entity unavailable if updates stop for any other reason. The credential is an MQTT user that the broker's ACL can limit to publishing on Lightkeeper's topics. Cost: an MQTT client. A third-party library (paho-mqtt) breaks ADR-0005's standard-library rule. The alternative is a minimal MQTT 3.1.1 publisher over `socket` and `ssl` (CONNECT with a will, PUBLISH QoS 0 retained, PINGREQ, DISCONNECT), roughly 150 lines with its own tests against a fake broker. It needs a broker; most Home Assistant installs already run the Mosquitto add-on.
2. **Push to Home Assistant's REST API** (`POST /api/states/sensor.lightkeeper`). Standard library only, no broker. But the display device then holds a long-lived Home Assistant token, which carries the full rights of the user who created it, and nothing marks the entity unavailable when pushes stop: the last state just sits there looking current. That is exactly the deciding hazard.
3. **Home Assistant polls Lightkeeper** (a `rest` sensor reading a small JSON endpoint served by `lightkeeper --watch`). Home Assistant would mark the entity unavailable when the endpoint stops answering, and no Home Assistant credential lives on the device. But it opens an unauthenticated port on the LAN that serves health data, and the display device becomes a server.
4. **Only Home Assistant's Nightscout integration.** No work, and no staleness: rejected as the sole path for the reason above. It can stay alongside for graphs.

In every option, the same JSON status object (level, value, age, trend, fetch error, generated-at time) is the payload. A `--json PATH` output, written atomically like `--svg`, is cheap, testable, and useful for dashboards on its own.

## Decision

Proposed: option 1, MQTT discovery with a minimal standard-library MQTT 3.1.1 publisher, availability through Last Will, and `expire_after` set to the stale limit plus one refresh interval. TLS on by default, plain MQTT only when explicitly enabled for a broker on localhost (mirroring `allow_http`). Plus `--json PATH` as the shared payload and a standalone feature.

The published level never looks better than the displays: when the publisher can't fetch, it publishes what the displays would show (STALE or NO DATA with the error attribute), and when it can't publish at all, the broker's will and `expire_after` make the entity unavailable. Example automations in the docs trigger on `URGENT LOW`, on `STALE`, and on `unavailable`, and say plainly that the primary app's alarms stay primary.

## Consequences

- Home Assistant can never act on a fresh-looking level from a dead publisher: the entity goes `unavailable` within one will delivery or one `expire_after` period.
- A small protocol client becomes ours to maintain and test (GAP-002). It publishes only, never subscribes, and ignores anything the broker sends besides acknowledgements.
- New configuration: broker host, port, username, password (secret), TLS on/off, topic prefix. These go into `docs/ENV_VARS.md` and the env-contract check.
- This is the first path by which Lightkeeper output can drive an alert, even if Home Assistant sounds it and not us. Before shipping, the classification rationale in `docs/SAFETY.md` is re-read and a hazard entry is added, as that section requires.

## Alternatives Considered

Options 2 to 4 above. paho-mqtt was weighed for option 1 and set aside only because of ADR-0005. If maintaining the minimal client turns out to cost more than expected, revisiting ADR-0005 for this one dependency is the fallback, with an OTS entry.
