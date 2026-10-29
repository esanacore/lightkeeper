# Security Model

Data classification, retention, and the threat model for Lightkeeper, following `constitution/SECURITY.md` ("Data Classification" and "Threat Modeling Triggers"). Safety hazards, the things that could hurt the person with diabetes through a wrong or missing number, are in `docs/SAFETY.md`; this document covers who could see, change, or block the data.

## Data Classification

| Data | Level | Where it lives | Notes |
| --- | --- | --- | --- |
| Glucose readings, trend, and timestamps | Restricted | Nightscout (source of truth); `lightkeeper` process memory (latest reading only); the iOS app's memory (latest reading only); the panel; the optional `--svg`, `--json`, `--png` and `--bmp` files; the MQTT broker and Home Assistant when `LK_MQTT_HOST` is set | Personal health data. Never in logs, test fixtures, docs, or bug reports; all of those use synthetic values. |
| Nightscout readable token | Confidential | Environment (`NIGHTSCOUT_TOKEN`), typically from `/etc/lightkeeper.env` under systemd (there is no `.env` loader), or the iOS Keychain | Read-only scope. Redacted from every error. |
| MQTT broker password | Confidential | Environment (`LK_MQTT_PASSWORD`), typically from `/etc/lightkeeper.env` | Scope it with the broker's ACL to Lightkeeper's topics. Redacted from every error. |
| Nightscout API_SECRET | Restricted | Nightscout server only | Grants write access to treatments. Never given to Lightkeeper. |
| Thresholds and stale limit | Internal | Environment (`LK_*`); the iOS app's settings (UserDefaults, with the Nightscout address) | Display settings, not therapy settings. |
| Display vectors, gallery images, demo | Public | This repository | Synthetic data only. |

## Data Flows Across Boundaries

| Flow | From | To | Classification | Protection |
| --- | --- | --- | --- | --- |
| Glucose upload | Trio on the primary iPhone | Nightscout | Restricted | HTTPS; Nightscout auth (outside this repo) |
| Glucose fetch | Nightscout | `lightkeeper` | Restricted | HTTPS only, readable token, GET only, bounded count, 10 s timeout |
| Screen output | `lightkeeper` | Panel, terminal, `--svg`, `--json`, `--png` or `--bmp` file | Restricted (one reading) | Local only; no network listener; atomic writes into a private runtime directory under systemd |
| Home Assistant publish (ADR-0010) | `lightkeeper` | MQTT broker, then Home Assistant | Restricted (one reading) | TLS with certificate checks by default, plain MQTT only to localhost, ACL-scoped broker user, publish-only client, state never retained, no number for a reading that is not current (HAZ-013) |
| Companion app fetch | Nightscout | iOS app | Restricted | HTTPS only, a site address only (no path, query, fragment or login), readable token from the Keychain in the `api-secret` header, redirect guard; Check connection is one read-only GET with the same request |
| Firmware fetch (planned) | Nightscout | Xteink over Wi-Fi | Restricted | Same rules as the Python client, enforced in ADR-0006's promotion criteria; the build-only skeleton has no network code, no clock and no credentials |

## Retention and Deletion

Lightkeeper keeps the newest reading in memory and nothing else; it is gone when the process exits. The optional `--svg`, `--json`, `--png` and `--bmp` files each hold one screen and are overwritten on every refresh; delete them to remove them. Nightscout's own retention is configured on the Nightscout server, and its retention period and deletion path are recorded in `docs/OPERATIONS.md` when hosting is chosen (Phase 1).

## Threat Model (STRIDE)

Trigger: a new outbound egress path (Nightscout) carrying Restricted data, with a credential.

Assets: the glucose data, the readable token, and above all the integrity of what the display shows.

Trust boundaries: the network between the display device and Nightscout; the device's own environment and filesystem.

| Threat | Example | Mitigation | Verified by |
| --- | --- | --- | --- |
| **S**poofing | A fake server pretends to be Nightscout and serves made-up readings | HTTPS required, so the server's certificate is checked; plain HTTP refused unless explicitly enabled for localhost tests | `test_nfr001_rejects_non_https_urls` |
| **T**ampering | Readings altered in transit or a malformed entry injected | TLS; strict parsing rejects anything out of range, non-integer, non-`sgv`, or badly dated; stale and future data never shown as current | FR-001, FR-003 tests |
| **R**epudiation | Unclear what the display showed during an incident | Exit codes and stdout give a record when run under a service manager; incident process in `docs/OPERATIONS.md`; exported PNG and BMP images carry the local time they were drawn, the SVG its written stamp | Process |
| **I**nformation disclosure | Token or readings leak through logs, errors, or the repo | Token redacted from errors; readings never logged beyond the screen; secrets sweep and `.gitignore` coverage; synthetic data only in tests and docs; the CLI's stderr diagnostics are redacted (`test_nfr001_diagnostics_never_contain_the_token`) | NFR-001 tests, `check_secrets.sh` |
| **D**enial of service | Nightscout down or slow, display freezes on an old value | 10 s timeout; failures degrade to NO DATA or age into STALE; refresh no faster than every 15 s so we never hammer the server | FR-005 tests |
| **E**levation of privilege | Lightkeeper used to change therapy data | Readable-role token only; client issues GET to one endpoint; no dosing code exists (ADR-0004) | NFR-003 tests |

On a Pi, `deploy/lightkeeper.service` runs Lightkeeper as an unprivileged `lightkeeper` user with no capabilities, a read-only system, no home directories, private devices and `/tmp`, a system-call filter, and network families limited to IPv4, IPv6, and the local notify socket (`systemd-analyze security` exposure about 1.2). `tests/test_deploy.py` fails if any of those settings is dropped.

Residual risks: the token travels in the `api-secret` request header (ADR-0009), so it is not in any URL, proxy log, or hosting access log; it is exposed only inside the TLS session and on the device itself. A compromised display device exposes one reading and a read-only token, not therapy control.
