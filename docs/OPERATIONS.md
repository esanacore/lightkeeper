# Operations

Operational procedures for the parts of the stack we run. Health data is involved, so every procedure favors "safe and visible" over "convenient."

## Deployment

- **Environments**: local development (demo mode and a test Nightscout), and production (the household's real Nightscout and display devices). There is no staging for the therapy half; Trio's open-loop phase plays that role (ADR-0002).
- **Deployment Procedure**: `lightkeeper` is installed on a display device with `pip install` from a tagged release and run as a service (systemd on a Pi). Nightscout deployment is documented when hosting is chosen (Phase 1).
- **Approvals / Gates**: tests and constitution checks green in CI; any change touching parsing, classification, rendering, or the client gets a hazard review against `docs/SAFETY.md`; Trio rebuilds happen only after reading release notes and checking community reports.
- **Rollback**: reinstall the previous `lightkeeper` tag. For Trio, keep the previous build archived; for pods, the official Omnipod 5 app or Controller is the fallback.

## Monitoring & Observability

- **Logs**: `lightkeeper` prints to stdout; under systemd, `journalctl -u lightkeeper`. Logs never contain the token.
- **Liveness**: under `deploy/lightkeeper.service`, each finished refresh pets the systemd watchdog (`WatchdogSec=180`); a hung refresh gets the service restarted, which shows in the journal as a watchdog timeout. `systemctl status lightkeeper` shows the current level in its Status line.
- **Metrics**: Nightscout's own reports, plus Trio's loop status uploads.
- **Alerts**: the primary CGM app's alarms are the safety net. Home Assistant alerts (FR-008) are an extra layer, never a replacement.

## Safe Operations

- **Retention**: Lightkeeper keeps only the newest reading, in memory; the optional `--svg` file holds one screen and is overwritten each refresh (delete the file to remove it). Nightscout's retention period and deletion path are set and recorded here when hosting is chosen in Phase 1. Classification details: `docs/SECURITY_MODEL.md`.
- **Backup/Restore**: back up the Nightscout database on a schedule and test a restore at least once (ADR-0003 promotion criteria).
- **Maintenance Mode**: before taking Nightscout down, tell the person with diabetes; displays will show STALE, which is expected.
- **Stateful Changes**: never edit or delete Nightscout entries by hand; never write treatments from this repo.

## Incident Response

1. Make sure the person with diabetes is safe and using the primary app. Everything else waits.
2. Identify the impact: wrong number, frozen display, missed alert, or therapy issue.
3. Check Nightscout, the phone, and recent changes.
4. Roll back the last change if it could be the cause.
5. For any incident or near miss, write a postmortem from `constitution/templates/docs/INCIDENT_POSTMORTEM.md` into `docs/incidents/YYYY-MM-DD-short-name.md`, add a hazard to `docs/SAFETY.md`, and turn corrective actions into `TODO.md` items. Report therapy-side bugs upstream to Trio with logs.
