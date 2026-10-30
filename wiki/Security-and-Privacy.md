# Security and Privacy

Lightkeeper handles glucose readings, which are personal health data, and a credential for the Nightscout site that holds them. This page summarizes `docs/SECURITY_MODEL.md` in the repository, which follows the constitution's security standard, and `.github/SECURITY.md`, the reporting policy. Safety hazards, the things that could hurt someone through a wrong or missing number, are in [[Safety]]; this page is about who could see, change, or block the data.

## Data classification

| Data | Level | Where it lives | Notes |
| --- | --- | --- | --- |
| Glucose readings, trend, timestamps | Restricted | Nightscout; `lightkeeper` process memory, the desktop window's included (latest reading only); the iOS app's memory (latest reading only); the Android app's memory (the last good reading, never written to its storage); the panel; the optional `--svg`, `--json`, `--png` and `--bmp` files; the MQTT broker and Home Assistant when `LK_MQTT_HOST` is set | Health data. Never in logs, fixtures, docs, or bug reports; all of those use synthetic values. |
| Nightscout readable token | Confidential | Environment (`NIGHTSCOUT_TOKEN`, which the desktop window reads too), a root-only env file on a Pi, the iOS Keychain, or on Android only as AES-256-GCM ciphertext in app-private storage, sealed under an Android Keystore key | Read-only scope. Redacted from every error. |
| MQTT broker password | Confidential | Environment (`LK_MQTT_PASSWORD`), the root-only env file on a Pi | Scope it with the broker's ACL to Lightkeeper's topics. Redacted from every error. |
| Nightscout `API_SECRET` | Restricted | Nightscout server, and Trio so it can upload | Grants write access. Never given to Lightkeeper. |
| Thresholds and stale limit | Internal | Environment (`LK_*`); the iOS app's settings (UserDefaults, with the Nightscout address); the Android app's settings (app-private storage, with the Nightscout address) | Display settings, not therapy settings. |
| Display vectors, gallery images, demo | Public | The repository | Synthetic data only. |

## Data flows across boundaries

| Flow | From | To | Protection |
| --- | --- | --- | --- |
| Glucose upload | Trio on the primary iPhone | Nightscout | HTTPS; Nightscout authentication (outside this repository) |
| Glucose fetch | Nightscout | `lightkeeper` (the CLI, the service and the desktop window) | HTTPS only, readable token, GET only, bounded count (1 to 288), 10 second timeout, 1 MB response cap, no redirect that changes scheme or host |
| Screen output | `lightkeeper` | Panel, terminal, `--svg`, `--json`, `--png` or `--bmp` file | Local only; no network listener; files written atomically into a private runtime directory under systemd |
| Home Assistant publish (ADR-0010) | `lightkeeper` | MQTT broker, then Home Assistant | TLS with certificate checks by default (plain MQTT only to localhost), broker user limited by ACL, publish-only client, state never retained, no glucose number for a reading that is not current (HAZ-013) |
| Companion app fetch | Nightscout | iOS app | Same rules; a site address only; token in the Keychain, sent in the `api-secret` header; Check connection is one read-only GET |
| Android app fetch | Nightscout | Android app | HTTPS only, cleartext off, only the system's certificate authorities trusted; a site address only; one GET of 12 entries; token only in the `api-secret` header; 10 second connect and read timeouts and a 20 second limit on the whole fetch; 1 MB response cap; no redirect followed at all |
| Firmware fetch (planned) | Nightscout | Xteink over Wi-Fi | Same rules, enforced by ADR-0006's promotion criteria; the build-only skeleton has no network, clock or credentials |

## Retention and deletion

Lightkeeper keeps the newest reading in memory and nothing else; it is gone when the process exits. The optional `--svg`, `--json`, `--png` and `--bmp` files each hold one screen and are overwritten on every refresh; delete a file to remove it. The desktop window writes no files. The Android app keeps its readings in memory only; its settings and the sealed token stay in app-private storage until the app is uninstalled or its storage cleared, and clearing the token field and saving deletes the token. Nightscout's own retention is configured on the Nightscout server, and its retention period and deletion path get recorded in `docs/OPERATIONS.md` when hosting is chosen in Phase 1.

## Token handling

The only credential Lightkeeper ever holds is a Nightscout access token for a subject with the **readable** role. The `API_SECRET` is never used, because it grants write access and Lightkeeper has nothing to write.

- Only `https://` base URLs are accepted. Plain HTTP is refused unless `allow_http=True` is passed in code, which exists only for the localhost tests. A base URL with a query, fragment, or embedded login is rejected.
- Redirects to a different scheme or host are refused, so a redirect can never send the token in the clear or to another site.
- The token is redacted from every error message, raw and URL-encoded, so logs and bug reports are safe to share.
- The iOS app accepts only a site address, so a `?token=` link is refused, and the CLI's stderr lines about a failed fetch are redacted like every other error.
- On a Raspberry Pi the token lives in `/etc/lightkeeper.env` with mode 600, read by systemd. On iOS it lives in the Keychain. There is no `.env` loader in the Python package. The setup instructions use `read -rs` and `Read-Host` to keep it out of shell history.
- On Android the token is sealed with AES-256-GCM under a key in the Android Keystore, and only the sealed bytes sit in the app's private storage. It travels only in the `api-secret` header; the app follows no redirect at all, so the token is never carried anywhere else. It is never logged or offered to an autofill service, it is kept out of backups and device transfers, and it is deleted only on proof of damage, never because the Keystore could not be reached for a moment.

The token travels in the `api-secret` request header, which Nightscout's v1 API accepts, and never in a URL, so it stays out of proxy and hosting logs (ADR-0009). A compromised display device exposes one reading and a read-only token, not therapy control.

## STRIDE summary

Assets: the glucose data, the readable token, and above all the integrity of what the display shows. Lightkeeper opens no ports; its only network activity is outbound HTTPS GET to one site.

| Threat | Example | Mitigation | Verified by |
| --- | --- | --- | --- |
| Spoofing | A fake server pretends to be Nightscout | HTTPS required, so the certificate is checked | `test_nfr001_rejects_non_https_urls` |
| Tampering | Readings altered in transit or a malformed entry injected | TLS; strict parsing rejects anything out of range, non-finite, non-integer, non-`sgv`, or badly dated; one poisoned entry never discards its neighbors | FR-001, FR-003, HAZ-011 tests |
| Repudiation | Unclear what the display showed during an incident | Exit codes and flushed stdout give a live record under systemd; the SVG carries a "written" stamp; exported PNG and BMP images carry the time they were drawn; incident process in `docs/OPERATIONS.md` | Process |
| Information disclosure | Token or readings leak through logs, errors, or the repository | Token redacted; readings never logged beyond the screen; secrets sweep; synthetic data only | NFR-001 tests, `check_secrets.sh` |
| Denial of service | Nightscout down or slow; display freezes on an old value | 10 second timeout; failures degrade to NO DATA or age into STALE; refresh no faster than every 15 seconds | FR-005 tests |
| Elevation of privilege | Lightkeeper used to change therapy data | Readable-role token only; GET to one endpoint; no dosing code exists (ADR-0004) | NFR-003 tests |

`lightkeeper` has no runtime dependencies; the desktop window uses the Tcl/Tk that comes with Python, which the repository neither ships nor pins. Development tools, system-level components (including Nightscout, Trio, the Dexcom app, and the Omnipod 5 driver), and the Android app's build components (only the Kotlin standard library and its annotations ship in the APK) are inventoried in `docs/OTS_SOFTWARE.md` with risk, verification, and update policy. Dependabot watches pip, GitHub Actions, and the constitution submodule; the Android build's Gradle pins are moved by review.

## Reporting a vulnerability

Report security issues privately, not in a public issue. Use GitHub's **Report a vulnerability** button on the repository's Security tab, or email the maintainer at esanacore@gmail.com with "Lightkeeper security" in the subject. Expect an acknowledgment within 7 days. Anything that could change what number or status a display shows is treated as a safety issue as well and gets a hazard review in `docs/SAFETY.md`. Never include real glucose data in a report.

See also [[Testing and Quality]] for the tests named above, and [[Contributing]] for the hooks that run the secrets sweep locally.
