# Environment & Configuration Contract

All environment variables read by `lightkeeper`. If you add a variable to the code or to an `.env.example`, document it here in the same pull request.

## Required Variables

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `NIGHTSCOUT_URL` | Base URL of the Nightscout site. Must be HTTPS. Not needed with `--demo`. | `https://ns.example.com` |

## Optional Variables

| Variable | Description | Default Value | Example Value |
| :--- | :--- | :--- | :--- |
| `NIGHTSCOUT_TOKEN` | Nightscout access token with the **readable** role only. Never the API_SECRET. Sent in the `api-secret` request header, never in a URL (ADR-0009). Treat as a secret: keep it out of shell history, screenshots, and commits. Optional only for a public Nightscout site, which this project does not recommend; with `AUTH_DEFAULT_ROLES=denied` (the setting in `docs/SETUP.md`) it is required. | none | `readable-0123456789abcdef` |
| `LK_URGENT_LOW` | Urgent low threshold in mg/dL (at or below) | `55` | `55` |
| `LK_LOW` | Low threshold in mg/dL (below) | `70` | `75` |
| `LK_HIGH` | High threshold in mg/dL (above) | `180` | `200` |
| `LK_URGENT_HIGH` | Urgent high threshold in mg/dL (at or above) | `250` | `250` |
| `LK_STALE_MINUTES` | Minutes before a reading is shown as STALE | `15` | `12` |
| `LK_MQTT_HOST` | MQTT broker for Home Assistant (ADR-0010). Publishing is off unless this is set. | none | `homeassistant.local` |
| `LK_MQTT_PORT` | Broker port | `8883` with TLS, `1883` without | `8883` |
| `LK_MQTT_TLS` | `true` or `false`. TLS with certificate checks is the default; `false` is refused unless the host is `localhost`, `127.0.0.1`, or `::1`. | `true` | `true` |
| `LK_MQTT_USERNAME` | Broker user. Give it its own account, limited by the broker's ACL to the `lightkeeper/#` and `homeassistant/sensor/<node id>/#` topics. | none | `lightkeeper` |
| `LK_MQTT_PASSWORD` | Broker password. Treat as a secret, like the Nightscout token; it is never printed in errors. | none | `generated-long-random` |
| `LK_MQTT_DISCOVERY_PREFIX` | Home Assistant's MQTT discovery prefix | `homeassistant` | `homeassistant` |
| `LK_MQTT_NODE_ID` | Names this display's device and topics; one per display (letters, digits, `_`, `-`) | `lightkeeper` | `bedside` |

Thresholds must satisfy `40 <= LK_URGENT_LOW < LK_LOW < LK_HIGH < LK_URGENT_HIGH <= 400`, or the program exits at startup. Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.
