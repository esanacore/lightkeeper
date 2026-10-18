# Environment & Configuration Contract

All environment variables read by `lightkeeper`. If you add a variable to the code or to an `.env.example`, document it here in the same pull request.

## Required Variables

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `NIGHTSCOUT_URL` | Base URL of the Nightscout site. Must be HTTPS. Not needed with `--demo`. | `https://ns.example.com` |

## Optional Variables

| Variable | Description | Default Value | Example Value |
| :--- | :--- | :--- | :--- |
| `NIGHTSCOUT_TOKEN` | Nightscout access token with the **readable** role only. Never the API_SECRET. Treat as a secret: keep it out of shell history, screenshots, and commits. | none | `readable-0123456789abcdef` |
| `LK_URGENT_LOW` | Urgent low threshold in mg/dL (at or below) | `55` | `55` |
| `LK_LOW` | Low threshold in mg/dL (below) | `70` | `75` |
| `LK_HIGH` | High threshold in mg/dL (above) | `180` | `200` |
| `LK_URGENT_HIGH` | Urgent high threshold in mg/dL (at or above) | `250` | `250` |
| `LK_STALE_MINUTES` | Minutes before a reading is shown as STALE | `15` | `12` |

Thresholds must satisfy `40 <= LK_URGENT_LOW < LK_LOW < LK_HIGH < LK_URGENT_HIGH <= 400`, or the program exits at startup. Threshold values are display settings to agree with Kaitlin and her care team; they do not affect dosing.
