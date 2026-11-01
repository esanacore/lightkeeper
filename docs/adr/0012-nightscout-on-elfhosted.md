# ADR-0012: Host Nightscout on ElfHosted

Status: Accepted

Date: 2026-11-01

## Relationships

- Extends: ADR-0003
- Supersedes: none
- Related: ADR-0009, docs/SETUP.md ("Choosing a host"), docs/OPERATIONS.md, GAP-003

## Context

ADR-0003 makes Nightscout the data hub every display reads, and its first promotion criterion is a deployment with HTTPS, a strong `API_SECRET` and authentication defaulted to deny. Phase 1 of `docs/SETUP.md` asks for the host to be picked and recorded in an ADR before anything is deployed.

Nightscout has to be reachable from the phone anywhere, so it runs in the cloud, not on a machine at home. Lightkeeper needs two settings from the host: `AUTH_DEFAULT_ROLES=denied`, so nothing is public, and a token for a `readable` subject, which every display sends in the `api-secret` header (ADR-0009). The household wants the least upkeep that still keeps the site private.

The options compared in `docs/SETUP.md` ("Choosing a host", prices as listed there):

1. **ElfHosted** (managed). About $9 a month, or $7.20 a month paid yearly, with a $1 seven-day trial. The host does updates, TLS and nightly database backups. Its documentation confirms both settings Lightkeeper needs. Private by default. The data region is not stated.
2. **A VPS with the official Docker Compose setup** (DigitalOcean or Hetzner). About $6 to $8 a month with provider backups. Full control and a data region we choose, but about an hour a month of upkeep: OS patches, image updates, backups and MongoDB upgrades.
3. **ns.10be.de** (managed). €5.99 a month, servers in Germany, backups every 4 to 6 hours kept 47 days. Custom environment variables are supported, but `AUTH_DEFAULT_ROLES` needs confirming with their support first.
4. T1Pal, Nightscout Pro, Railway, Fly.io or Heroku Eco, or the Oracle Always Free VM. Each is either unconfirmed on the settings above or mostly our own upkeep. The free tiers that sleep or throttle are ruled out for a closed loop.

## Decision

Option 1: host Nightscout on ElfHosted (Eric, 2026-11-01).

- Use the seven-day trial first. From a display over HTTPS, check that a `readable` token returns entries in the `api-secret` header and that a request with no credentials gets 401 (the ADR-0009 real-instance check). Only then point Trio at the site.
- The settings in `docs/SETUP.md` Phase 1 still apply in full: a long random `API_SECRET` that never goes on a display, `AUTH_DEFAULT_ROLES=denied`, HTTPS only, and one `readable` subject for the displays.
- Record ElfHosted's backup retention in `docs/OPERATIONS.md`. Restore once from a backup before relying on the site, which is ADR-0003's third criterion.

## Consequences

- The least upkeep of the options: the host patches Nightscout and MongoDB, renews TLS and takes backups.
- A third party holds the glucose data. ADR-0003 named managed hosting the acceptable fallback; this makes it the plan. Leaving later means a MongoDB export and a new site address on every display.
- The data region is not stated. If that matters later, the VPS option is the way to choose one.
- `docs/SETUP.md` Phase 1 gets exact ElfHosted steps once the trial has been walked through.
- The displays need no change. The iOS and Android apps accept only a site root, not a sub-path, so the trial must also confirm that ElfHosted serves the site at a root (`https://host/`). If it uses a path, the phones' sub-path rule is revisited before they can read it.

## Alternatives Considered

Options 2 to 4 above. The VPS stays the runner-up: it is the move to make if ElfHosted's region, uptime or support becomes a problem. ns.10be.de is the cheaper EU option once its support confirms `AUTH_DEFAULT_ROLES`.
