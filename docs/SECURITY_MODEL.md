# Security Model

Data classification, retention, and the threat model for Lightkeeper, following `constitution/SECURITY.md` ("Data Classification" and "Threat Modeling Triggers"). Safety hazards, the things that could hurt the person with diabetes through a wrong or missing number, are in `docs/SAFETY.md`; this document covers who could see, change, or block the data.

## Data Classification

| Data | Level | Where it lives | Notes |
| --- | --- | --- | --- |
| Glucose readings, trend, and timestamps | Restricted | Nightscout (source of truth); `lightkeeper` process memory (latest reading only); the iOS app's memory (latest reading only); the desktop window's process memory (latest reading only); the Android app's memory (latest reading only, never written to storage); the panel; the optional `--svg`, `--json`, `--png` and `--bmp` files; the MQTT broker and Home Assistant when `LK_MQTT_HOST` is set | Personal health data. Never in logs, test fixtures, docs, or bug reports; all of those use synthetic values. |
| Nightscout readable token | Confidential | Environment (`NIGHTSCOUT_TOKEN`), typically from `/etc/lightkeeper.env` under systemd (there is no `.env` loader), or the iOS Keychain, or on Android only as AES-256-GCM ciphertext in the app's private storage (`lightkeeper.token`), sealed by a key the Android Keystore holds and never exports | Read-only scope. Redacted from every error. On Android it is never logged, never offered to an autofill service or kept in saved view state, and excluded from backups and device transfers. |
| MQTT broker password | Confidential | Environment (`LK_MQTT_PASSWORD`), typically from `/etc/lightkeeper.env` | Scope it with the broker's ACL to Lightkeeper's topics. Redacted from every error. |
| Nightscout API_SECRET | Restricted | Nightscout server only | Grants write access to treatments. Never given to Lightkeeper. |
| Thresholds and stale limit | Internal | Environment (`LK_*`); the iOS app's settings (UserDefaults, with the Nightscout address); the Android app's private settings (`lightkeeper.settings`, with the Nightscout address) | Display settings, not therapy settings. |
| Display vectors, gallery images, demo | Public | This repository | Synthetic data only. |

## Data Flows Across Boundaries

| Flow | From | To | Classification | Protection |
| --- | --- | --- | --- | --- |
| Glucose upload | Trio on the primary iPhone | Nightscout | Restricted | HTTPS; Nightscout auth (outside this repo) |
| Glucose fetch | Nightscout | `lightkeeper` (the CLI and the desktop window) | Restricted | HTTPS only, readable token, GET only, bounded count, 10 s timeout |
| Screen output | `lightkeeper` | Panel, terminal, desktop window, `--svg`, `--json`, `--png` or `--bmp` file | Restricted (one reading) | Local only; no network listener; atomic writes into a private runtime directory under systemd; the desktop window draws on screen only and writes no file |
| Home Assistant publish (ADR-0010) | `lightkeeper` | MQTT broker, then Home Assistant | Restricted (one reading) | TLS with certificate checks by default, plain MQTT only to localhost, ACL-scoped broker user, publish-only client, state never retained, no number for a reading that is not current (HAZ-013) |
| iOS app fetch | Nightscout | iOS app | Restricted | HTTPS only, a site address only (no path, query, fragment or login), readable token from the Keychain in the `api-secret` header, redirect guard; Check connection is one read-only GET with the same request |
| Android app fetch | Nightscout | Android app | Restricted | HTTPS only, with cleartext off for the whole app and only the system's certificate authorities trusted; a site address only; one GET of `/api/v1/entries/sgv.json?count=12` with the readable token in the `api-secret` header; no redirect followed (any redirect is a failed fetch); 10 s connect and read timeouts, a 20 s limit on the whole fetch, a 1 MB cap |
| Firmware fetch (planned) | Nightscout | Xteink over Wi-Fi | Restricted | Same rules as the Python client, enforced in ADR-0006's promotion criteria; the build-only skeleton has no network code, no clock and no credentials |

## Retention and Deletion

Lightkeeper keeps the newest reading in memory and nothing else; it is gone when the process exits. The optional `--svg`, `--json`, `--png` and `--bmp` files each hold one screen and are overwritten on every refresh; delete them to remove them. Nightscout's own retention is configured on the Nightscout server, and its retention period and deletion path are recorded in `docs/OPERATIONS.md` when hosting is chosen (Phase 1).

The desktop window, like the CLI, keeps only the newest reading in memory and writes no file. The Android app keeps its readings in memory only; its settings and its sealed token stay in the app's private storage until the app is uninstalled or its storage is cleared, and clearing the token field and saving deletes the sealed token. Backup and device transfer are off (`allowBackup="false"` and `data_extraction_rules.xml`).

## Threat Model (STRIDE)

Trigger: a new outbound egress path (Nightscout) carrying Restricted data, with a credential. Re-checked 2026-10-28 for the desktop window, which uses the same egress path, client and credential as the CLI, and for the Android app, a new client with a credential stored at rest on a phone.

Assets: the glucose data, the readable token, and above all the integrity of what the display shows.

Trust boundaries: the network between the display device and Nightscout; the device's own environment and filesystem; on Android, the app's private storage and the Keystore.

| Threat | Example | Mitigation | Verified by |
| --- | --- | --- | --- |
| **S**poofing | A fake server pretends to be Nightscout and serves made-up readings | HTTPS required, so the server's certificate is checked; plain HTTP refused unless explicitly enabled for localhost tests; the Android app trusts only the system's certificate authorities, with cleartext off for the whole app | `test_nfr001_rejects_non_https_urls`, `tests/test_android.py` (nfr001), Kotlin `testAConnectionThatIsNotHttpsSendsNothing` |
| **T**ampering | Readings altered in transit or a malformed entry injected | TLS; strict parsing rejects anything out of range, non-integer, non-`sgv`, or badly dated; stale and future data never shown as current; the Android app checks a reading from Kotlin again in the firmware's parser; install only a debug APK built from this repository (Android refuses to update an app with an APK signed by another key) | FR-001, FR-003 tests, Kotlin `testAReadingTheParserWouldRefuseShowsNoData` |
| **R**epudiation | Unclear what the display showed during an incident | Exit codes and stdout give a record when run under a service manager; incident process in `docs/OPERATIONS.md`; exported PNG and BMP images carry the local time they were drawn, the SVG its written stamp; the desktop window and the Android panel image carry the local time they were drawn | Process |
| **I**nformation disclosure | Token or readings leak through logs, errors, or the repo | Token redacted from errors; readings never logged beyond the screen; secrets sweep and `.gitignore` coverage; synthetic data only in tests and docs; the CLI's stderr diagnostics are redacted (`test_nfr001_diagnostics_never_contain_the_token`); on Android the token is sealed by a Keystore key, never logged, never offered to autofill, kept out of backups, and deleted only on proof of damage, so a Keystore that cannot be reached for a moment never loses it | NFR-001 tests, `check_secrets.sh`, Kotlin `testTheTokenRoundTripsAndIsNeverStoredInTheClear`, `testAKeystoreThatCannotBeReachedNowKeepsTheToken`, `testReadsDuringWritesNeverDeleteAJustSavedToken`, `testSaveLeavesAnUntouchedTokenAsItWas`, `test_nfr001_no_app_source_logs`, autofill off by review of `SettingsActivity.kt` |
| **D**enial of service | Nightscout down or slow, display freezes on an old value | 10 s timeout; failures degrade to NO DATA or age into STALE; refresh no faster than every 15 s so we never hammer the server; the desktop window counts a fetch with no answer after two intervals as unreachable and retries on a new worker, with at most 8 stuck threads; the Android app limits a whole fetch to 20 seconds and runs one at a time | FR-005 tests, `test_haz002_threads_stuck_on_hung_fetches_are_capped`, Kotlin `testAFetchPastItsDeadlineIsCancelledAndShownAsUnreachable` |
| **E**levation of privilege | Lightkeeper used to change therapy data | Readable-role token only; client issues GET to one endpoint; no dosing code exists (ADR-0004); the Android app asks only for `INTERNET` and exports only its launcher activity | NFR-003 tests, `test_nfr001_manifest_asks_for_internet_and_nothing_else`, `test_nfr001_only_the_launcher_activity_is_exported` |

On a Pi, `deploy/lightkeeper.service` runs Lightkeeper as an unprivileged `lightkeeper` user with no capabilities, a read-only system, no home directories, private devices and `/tmp`, a system-call filter, and network families limited to IPv4, IPv6, and the local notify socket (`systemd-analyze security` exposure about 1.2). `tests/test_deploy.py` fails if any of those settings is dropped.

Residual risks: the token travels in the `api-secret` request header (ADR-0009), so it is not in any URL, proxy log, or hosting access log; it is exposed only inside the TLS session and on the device itself. A compromised display device exposes one reading and a read-only token, not therapy control. On Android, a phone whose lock and Keystore are compromised exposes one reading and a read-only token, as any display device does; the token store gets a security review at the pull request (pending Eric).
