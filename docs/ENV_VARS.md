# Environment & Configuration Contract

All environment variables read by `lightkeeper`. If you add a variable to the code or to an `.env.example`, document it here in the same pull request.

## Required Variables

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `NIGHTSCOUT_URL` | Base URL of the Nightscout site, the address you open it at in a browser. Must be HTTPS, with no spaces, query, fragment, or login in it. Not needed with `--demo`. | `https://ns.example.com` |

## Optional Variables

| Variable | Description | Default Value | Example Value |
| :--- | :--- | :--- | :--- |
| `NIGHTSCOUT_TOKEN` | Nightscout access token with the **readable** role only. Never the API_SECRET. Sent in the `api-secret` request header, never in a URL (ADR-0009). Treat as a secret: keep it out of shell history, screenshots, and commits. Optional only for a public Nightscout site, which this project does not recommend; with `AUTH_DEFAULT_ROLES=denied` (the setting in `docs/SETUP.md`) it is required. Printable ASCII on one line; anything else is refused at startup without echoing it. | none | `readable-0123456789abcdef` |
| `LK_URGENT_LOW` | Urgent low threshold in mg/dL (at or below) | `55` | `55` |
| `LK_LOW` | Low threshold in mg/dL (below) | `70` | `75` |
| `LK_HIGH` | High threshold in mg/dL (above) | `180` | `200` |
| `LK_URGENT_HIGH` | Urgent high threshold in mg/dL (at or above) | `250` | `250` |
| `LK_STALE_MINUTES` | Minutes before a reading is shown as STALE; at least 1 | `15` | `12` |
| `LK_MQTT_HOST` | MQTT broker for Home Assistant (ADR-0010). Publishing is off unless this is set. | none | `homeassistant.local` |
| `LK_MQTT_PORT` | Broker port, 1 to 65535 | `8883` with TLS, `1883` without | `8883` |
| `LK_MQTT_TLS` | `true` or `false`. TLS with certificate checks is the default; `false` is refused unless the host is `localhost`, `127.0.0.1`, or `::1`. | `true` | `true` |
| `LK_MQTT_USERNAME` | Broker user. Give it its own account, limited by the broker's ACL to the `lightkeeper/#` and `homeassistant/sensor/<node id>/#` topics. | none | `lightkeeper` |
| `LK_MQTT_PASSWORD` | Broker password. Treat as a secret, like the Nightscout token; it is never printed in errors. Needs `LK_MQTT_USERNAME`: MQTT 3.1.1 sends a password only with a user name. | none | `generated-long-random` |
| `LK_MQTT_DISCOVERY_PREFIX` | Home Assistant's MQTT discovery prefix (letters, digits, `_`, `-`) | `homeassistant` | `homeassistant` |
| `LK_MQTT_NODE_ID` | Names this display's device and topics; one per display (letters, digits, `_`, `-`) | `lightkeeper` | `bedside` |
| `NO_COLOR` | Set to anything but empty to turn color off in the interactive `--watch` frame ([no-color.org](https://no-color.org)), as `--no-color` does. Reverse video, underline and strike stay, so every status keeps its shape. Piped and systemd output never has color or escape codes either way. | unset (color on) | `1` |
| `TERM` | Set by the terminal; read only to choose the `--watch` view. `dumb` gets the plain vector lines with no escape codes, as a pipe does. The frame's width follows the terminal (or `COLUMNS`, which Python reads). | set by the terminal | `dumb` |

Thresholds must satisfy `40 <= LK_URGENT_LOW < LK_LOW < LK_HIGH < LK_URGENT_HIGH <= 400`. Each is a whole number in plain digits, and an empty variable means the default, as an unset one does.

Every setting is checked before anything is shown. An unusable one stops the program with exit code 2 and a message naming the variable, its value, and what it clashes with, for example `Configuration error: LK_LOW=200 must be below LK_HIGH=180 (the default)` or `Configuration error: LK_MQTT_PORT='abc' must be a whole number`. `NIGHTSCOUT_URL`, `NIGHTSCOUT_TOKEN` and `LK_MQTT_PASSWORD` are named in these messages but their values never are.

Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

The desktop window (`python -m lightkeeper.desktop`, or `lightkeeper-window`) reads `NIGHTSCOUT_URL`, `NIGHTSCOUT_TOKEN`, the four thresholds and `LK_STALE_MINUTES` exactly as the CLI does, and stops with the same `Configuration error:` line and exit 2 (the `lightkeeper-window` launcher on Windows has no console, so it exits 2 without the line; run `python -m lightkeeper.desktop` in a terminal to read it, D12). It does not publish to Home Assistant, so it never reads the `LK_MQTT_*` settings, and it has no color view, so `NO_COLOR` and `TERM` do not apply. The Android app reads no environment variables: its Settings screen holds the address, the token and the thresholds.
