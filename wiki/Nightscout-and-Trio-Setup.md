# Nightscout and Trio Setup

The therapy half of the stack is community software, and its setup belongs to the person with diabetes and their care team. The community documentation for Nightscout (nightscout.github.io) and Trio (triodocs.org) changes often, so this page does not duplicate its steps. It records the phased plan, the choices this project has made, and where to go for each step. The source is Part 2 of `docs/SETUP.md` in the repository, with the phase gates in `docs/ROADMAP.md`.

Lightkeeper is a secondary display and not a medical device. Nothing on this page is medical advice; the decisions it describes are made with an endocrinologist.

## The phases

| Phase | What happens | Exit evidence | Who decides |
| --- | --- | --- | --- |
| 1 Data hub | Self-hosted Nightscout over HTTPS, a readable token, backups | Trio uploads; one restore tested; `lightkeeper` reads real data | Eric |
| 2 Open loop | Trio on the primary iPhone with the G7 and Omnipod 5 pods, suggestions only | Two weeks of logs; settings validated with the endocrinologist | The person with diabetes and their care team |
| 3 Closed loop | Trio automates, with weekly review at first | ADR-0002 promotion criteria: endocrinologist review, two weeks of open loop, five pod changes without unresolved faults | The person with diabetes and their care team |

None of the three has started as of 0.1.0; they do not block the display work.

## Phase 1: Nightscout

Nightscout is the data hub every Lightkeeper display reads from (ADR-0003). It has to live somewhere the phone can reach from anywhere, which means a cloud VPS or a managed Nightscout host, not a machine at home.

- Hosting: a small VPS (1 vCPU and 1 GB is enough) running the official Docker Compose setup behind a TLS proxy, or a managed host; the choice gets its own ADR. Follow the install guide at https://nightscout.github.io. `docs/SETUP.md` ("Choosing a host") compares the options as of October 2026: ElfHosted (about $9 a month, managed, and documented to support `AUTH_DEFAULT_ROLES` and readable tokens) is the low-upkeep pick, and a VPS (about $6 to $8 a month) is the full-control runner-up. Never use Render's free tier, Azure F1, or a MongoDB Atlas M0 database for a loop.
- Security settings that are not optional here: a long random `API_SECRET` (at least 24 characters, generated, never reused), `AUTH_DEFAULT_ROLES=denied` so nothing is public, and HTTPS only.
- The read-only token: in Nightscout, open the menu, Admin Tools, Subjects, and add a subject named `lightkeeper-displays` with the role `readable`. The token Nightscout shows is what every display uses as `NIGHTSCOUT_TOKEN`. The `API_SECRET` never goes on a display.
- Backups: a nightly `mongodump` to object storage, restored once to a scratch instance to prove it works. The retention period gets recorded in `docs/OPERATIONS.md`.
- Verification: with `NIGHTSCOUT_URL` and `NIGHTSCOUT_TOKEN` set, `python -m lightkeeper` should print NO DATA until an uploader exists, not a configuration error. [[Getting Started]] has the commands.

## Phases 2 and 3: Trio

Trio is the open source automated insulin delivery app that runs on the iPhone and talks to the pump. It is not Lightkeeper code. Read https://triodocs.org end to end and talk with the endocrinologist before starting. Our choices:

- **Build method: Trio's browser build.** GitHub Actions builds the app and uploads it to TestFlight, so no Mac is needed. It requires a paid Apple Developer account (in place) and follows the "Build with Browser" guide at triodocs.org exactly. The fork's default branch stays on `main`.
- **CGM: Dexcom G7 via the Dexcom G7 app on the same phone.** On iPhone, Trio reads G7 data from the Dexcom app, so that app stays installed as a background radio. Turn off iOS automatic app updates, and update the Dexcom app only after the Trio community confirms compatibility. The first G7 sensor session must start in the country of the App Store the Dexcom app came from (the geofence).
- **Pump: Omnipod 5 pods.** Supported on Trio's `main` branch since v1.0.0, released September 15, 2026, after an open beta. The switching steps are on the compatibility page at https://nightscout.github.io/omnipod-five. Three rules from that page and the community: keep a backup DASH pod for the first switch, do not fill a new pod until Trio shows the pairing screen, and have internet available because the first pod needs a certificate step. Once paired with Trio, a pod stops talking to the CGM and only takes commands from Trio, so pod and sensor must both be in Bluetooth range of the phone.
- **Nightscout in Trio:** the site URL and the `API_SECRET`, so Trio can upload. Trio writes; displays only read.
- **Open loop first.** Trio only suggests for at least two weeks while settings are validated with the care team. Closed loop comes when ADR-0002's promotion criteria are met.
- **Fallback:** keep the official Omnipod 5 app or Controller. Pairing a fresh pod with it restores the stock algorithm.

Log every pod change, fault, and suggestion mismatch during open loop; those logs are the evidence the phases gate on, and driver bugs go upstream to Trio. Omnipod 5 support is new, which is why HAZ-009 in [[Safety]] treats Trio misconfiguration as a process hazard. [[Community Research]] collects early user reports.

## Alternatives on the table

ADR-0002 deferred AndroidAPS (no Omnipod 5 support yet), Loop (kept as a fallback), DASH pods (a prescription change), and FreeStyle Libre 3 Plus, which Trio reads directly with no vendor app but which is open beta as of October 2026. The Libre question belongs to the person with diabetes and their care team. See [[Architecture Decisions]].

## After the therapy half is running

Run through [[Display States]] with the real system: a fresh reading, a sensor warm-up, the phone out of range, the phone offline, and Nightscout stopped. Every display must show STALE or NO DATA within the stale limit. Hardware is in [[Hardware]]; failure modes are in [[Troubleshooting]].
