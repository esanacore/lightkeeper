# Operations

Operational procedures for the parts of the stack we run. Health data is involved, so every procedure favors "safe and visible" over "convenient."

## Deployment

- **Environments**: local development (demo mode and a test Nightscout), and production (the household's real Nightscout and display devices). There is no staging for the therapy half; Trio's open-loop phase plays that role (ADR-0002).
- **Deployment Procedure**: `lightkeeper` is installed on a display device with `pip install` from a tagged release (v0.2.0 or later) and run as the hardened service in `deploy/lightkeeper.service`; `docs/SETUP.md` has the steps and the upgrade procedure. Nightscout deployment is documented when hosting is chosen (Phase 1). The desktop window installs with the same package and runs as `python -m lightkeeper.desktop` or the `lightkeeper-window` launcher (D12, pending Eric's review). The Android app is a debug APK built from `apps/android` and sideloaded with `adb install -r` (`apps/android/README.md`); there is no store listing or release signing.
- **Approvals / Gates**: tests and constitution checks green in CI; any change touching parsing, classification, rendering, the client, the desktop window or the Android app gets a hazard review against `docs/SAFETY.md`; Trio rebuilds happen only after reading release notes and checking community reports.
- **Rollback**: reinstall the previous `lightkeeper` tag. For Trio, keep the previous build archived; for pods, the official Omnipod 5 app or Controller is the fallback. For the Android app, reinstall the previous debug APK; if Android refuses it (an APK signed on another machine), uninstall first, which clears the app's settings and sealed token.

## Monitoring & Observability

- **Logs**: `lightkeeper` prints the screen to stdout and, when Nightscout fails, one line to stderr naming the link that failed, once per change (`docs/TROUBLESHOOTING.md` lists them); under systemd, `journalctl -u lightkeeper`. Logs never contain the token. The desktop window writes nothing to stdout, and to stderr only one line when it cannot start (a configuration error, no Tk, or no display), the line saying it drew the panel smaller to fit, `lightkeeper: stopped`, or the traceback of an unexpected error; it does not print the CLI's fetch diagnostics. The Android app writes no logs.
- **Liveness**: under `deploy/lightkeeper.service`, each finished refresh pets the systemd watchdog (`WatchdogSec=180`); a hung refresh gets the service restarted, which shows in the journal as a watchdog timeout. `systemctl status lightkeeper` shows the current level in its Status line.
- **Metrics**: Nightscout's own reports, plus Trio's loop status uploads.
- **Alerts**: the primary CGM app's alarms are the safety net. Home Assistant alerts (FR-008) are an extra layer, never a replacement.

## Safe Operations

- **Retention**: Lightkeeper keeps only the newest reading, in memory; the optional `--svg`, `--json`, `--png` and `--bmp` files each hold one screen and are overwritten each refresh (delete a file to remove it). Nightscout's retention period and deletion path are set and recorded here when hosting is chosen in Phase 1. The desktop window keeps only the newest reading in memory. The Android app keeps readings in memory only; its settings and its sealed token stay in the app's private storage until the app is uninstalled or its storage is cleared. To delete the token, clear the token field and Save (the sealed token is deleted), or uninstall. Nothing goes to a cloud backup or a device transfer (`data_extraction_rules.xml`). Classification details: `docs/SECURITY_MODEL.md`.
- **Backup/Restore**: back up the Nightscout database on a schedule and test a restore at least once (ADR-0003 promotion criteria).
- **Maintenance Mode**: before taking Nightscout down, tell the person with diabetes; displays will show STALE, which is expected.
- **Stateful Changes**: never edit or delete Nightscout entries by hand; never write treatments from this repo.

## Incident Response

1. Make sure the person with diabetes is safe and using the primary app. Everything else waits.
2. Identify the impact: wrong number, frozen display, missed alert, or therapy issue.
3. Check Nightscout, the phone, and recent changes.
4. Roll back the last change if it could be the cause.
5. For any incident or near miss, write a postmortem from `constitution/templates/docs/INCIDENT_POSTMORTEM.md` into `docs/incidents/YYYY-MM-DD-short-name.md`, add a hazard to `docs/SAFETY.md`, and turn corrective actions into `TODO.md` items. Report therapy-side bugs upstream to Trio with logs.
