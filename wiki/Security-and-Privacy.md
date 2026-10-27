# Security and Privacy

Lightkeeper handles glucose readings, which are personal health data, and a credential for the Nightscout site that holds them. This page summarizes `docs/SECURITY_MODEL.md` in the repository, which follows the constitution's security standard, and `.github/SECURITY.md`, the reporting policy. Safety hazards, the things that could hurt someone through a wrong or missing number, are in [[Safety]]; this page is about who could see, change, or block the data.

## Data classification

| Data | Level | Where it lives | Notes |
| --- | --- | --- | --- |
| Glucose readings, trend, timestamps | Restricted | Nightscout; `lightkeeper` process memory (latest reading only); the panel; the optional `--svg` and `--json` files; the MQTT broker and Home Assistant when `LK_MQTT_HOST` is set | Health data. Never in logs, fixtures, docs, or bug reports; all of those use synthetic values. |
| Nightscout readable token | Confidential | Environment (`NIGHTSCOUT_TOKEN`), a root-only env file on a Pi, or the iOS Keychain | Read-only scope. Redacted from every error. |
| MQTT broker password | Confidential | Environment (`LK_MQTT_PASSWORD`), the root-only env file on a Pi | Scope it with the broker's ACL to Lightkeeper's topics. Redacted from every error. |
| Nightscout `API_SECRET` | Restricted | Nightscout server, and Trio so it can upload | Grants write access. Never given to Lightkeeper. |
| Thresholds and stale limit | Internal | Environment (`LK_*`) | Display settings, not therapy settings. |
| Display vectors, gallery images, demo | Public | The repository | Synthetic data only. |

## Data flows across boundaries

| Flow | From | To | Protection |
| --- | --- | --- | --- |
| Glucose upload | Trio on the primary iPhone | Nightscout | HTTPS; Nightscout authentication (outside this repository) |
| Glucose fetch | Nightscout | `lightkeeper` | HTTPS only, readable token, GET only, bounded count (1 to 288), 10 second timeout, 1 MB response cap, no redirect that changes scheme or host |
| Screen output | `lightkeeper` | Panel, terminal, `--svg` or `--json` file | Local only; no network listener; files written atomically into a private runtime directory under systemd |
| Home Assistant publish (ADR-0010) | `lightkeeper` | MQTT broker, then Home Assistant | TLS with certificate checks by default (plain MQTT only to localhost), broker user limited by ACL, publish-only client, state never retained, no glucose number for a reading that is not current (HAZ-013) |
| Companion app fetch | Nightscout | iOS app | Same rules; token in the Keychain |
| Firmware fetch (planned) | Nightscout | Xteink over Wi-Fi | Same rules, enforced by ADR-0006's promotion criteria |

## Retention and deletion

Lightkeeper keeps the newest reading in memory and nothing else; it is gone when the process exits. The `--svg` file holds one screen and is overwritten on every refresh; delete the file to remove it. Nightscout's own retention is configured on the Nightscout server, and its retention period and deletion path get recorded in `docs/OPERATIONS.md` when hosting is chosen in Phase 1.

## Token handling

The only credential Lightkeeper ever holds is a Nightscout access token for a subject with the **readable** role. The `API_SECRET` is never used, because it grants write access and Lightkeeper has nothing to write.

- Only `https://` base URLs are accepted. Plain HTTP is refused unless `allow_http=True` is passed in code, which exists only for the localhost tests. A base URL with a query, fragment, or embedded login is rejected.
- Redirects to a different scheme or host are refused, so a redirect can never send the token in the clear or to another site.
- The token is redacted from every error message, raw and URL-encoded, so logs and bug reports are safe to share.
- On a Raspberry Pi the token lives in `/etc/lightkeeper.env` with mode 600, read by systemd. On iOS it lives in the Keychain. There is no `.env` loader in the Python package. The setup instructions use `read -rs` and `Read-Host` to keep it out of shell history.

The token travels in the `api-secret` request header, which Nightscout's v1 API accepts, and never in a URL, so it stays out of proxy and hosting logs (ADR-0009). A compromised display device exposes one reading and a read-only token, not therapy control.

## STRIDE summary

Assets: the glucose data, the readable token, and above all the integrity of what the display shows. Lightkeeper opens no ports; its only network activity is outbound HTTPS GET to one site.

| Threat | Example | Mitigation | Verified by |
| --- | --- | --- | --- |
| Spoofing | A fake server pretends to be Nightscout | HTTPS required, so the certificate is checked | `test_nfr001_rejects_non_https_urls` |
| Tampering | Readings altered in transit or a malformed entry injected | TLS; strict parsing rejects anything out of range, non-finite, non-integer, non-`sgv`, or badly dated; one poisoned entry never discards its neighbors | FR-001, FR-003, HAZ-011 tests |
| Repudiation | Unclear what the display showed during an incident | Exit codes and flushed stdout give a live record under systemd; the SVG carries a "written" stamp; incident process in `docs/OPERATIONS.md` | Process |
| Information disclosure | Token or readings leak through logs, errors, or the repository | Token redacted; readings never logged beyond the screen; secrets sweep; synthetic data only | NFR-001 tests, `check_secrets.sh` |
| Denial of service | Nightscout down or slow; display freezes on an old value | 10 second timeout; failures degrade to NO DATA or age into STALE; refresh no faster than every 15 seconds | FR-005 tests |
| Elevation of privilege | Lightkeeper used to change therapy data | Readable-role token only; GET to one endpoint; no dosing code exists (ADR-0004) | NFR-003 tests |

`lightkeeper` has no runtime dependencies. Development tools and system-level components (including Nightscout, Trio, the Dexcom app, and the Omnipod 5 driver) are inventoried in `docs/OTS_SOFTWARE.md` with risk, verification, and update policy, and Dependabot watches pip, GitHub Actions, and the constitution submodule.

## Reporting a vulnerability

Report security issues privately, not in a public issue. Use GitHub's **Report a vulnerability** button on the repository's Security tab, or email the maintainer at esanacore@gmail.com with "Lightkeeper security" in the subject. Expect an acknowledgment within 7 days. Anything that could change what number or status a display shows is treated as a safety issue as well and gets a hazard review in `docs/SAFETY.md`. Never include real glucose data in a report.

See also [[Testing and Quality]] for the tests named above, and [[Contributing]] for the hooks that run the secrets sweep locally.
