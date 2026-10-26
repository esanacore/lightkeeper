# ADR-0009: Send the Nightscout Readable Token in a Header, Not the URL

Status: Proposed

Date: 2026-10-25

## Relationships

- Extends: ADR-0003, ADR-0005
- Supersedes: none
- Related: docs/SECURITY_MODEL.md (residual risks), docs/SETUP.md (Phase 1), NFR-001

## Promotion Criteria

- Eric accepts the chosen option. Gate: Eric.
- On a real Nightscout (handoff step 7), with `AUTH_DEFAULT_ROLES=denied`, a GET of `/api/v1/entries/sgv.json` with the readable token in the `api-secret` header returns entries, and the same request with no credentials returns 401. Gate: an agent, recorded in `docs/TEST_PLAN.md`.

## Context

Every display reads Nightscout's v1 API with a `readable` role access token, passed today as `?token=...`. A query string is part of the URL, so the token can land in reverse-proxy and hosting access logs, browser history, and error reports (`docs/SECURITY_MODEL.md`, residual risks). The token can only read glucose data, but glucose data is health data, and a token that leaks into logs stays valid until someone revokes it.

`AUTH_DEFAULT_ROLES=denied` is already required by `docs/SETUP.md`. It makes the token mandatory for every read, so how the token travels matters for every request.

This ADR evaluates the request: move to the v3 API with JWT bearer auth. The facts below come from the Nightscout source at the v15.0.9 release (October 21, 2026), `lib/authorization/index.js`, `lib/authorization/endpoints.js`, `lib/server/enclave.js`, and `lib/api3/security.js`.

- The v1 API resolves credentials through `resolveWithRequest`, which accepts three forms. It takes an `Authorization: Bearer <JWT>` header first, then a `?token=<access token>` query parameter (or a `token` field in a body). Separately, it reads an `api-secret` header: if the value is not the hashed API secret but matches a stored access token (`storage.doesAccessTokenExist`), that subject's roles apply.
- A JWT comes from `GET /api/v2/authorization/request/<access token>`, which puts the access token in the URL path. JWTs expire after 8 hours by default. The signing key is read from `node_modules/.cache/_ns_cache/randomString`, so a reinstall or redeploy can invalidate every outstanding JWT.
- The v3 API accepts only `Authorization: Bearer <JWT>`. It returns different document shapes and paths from v1.

## Options

1. **Keep `?token=` (status quo).** No work. The token stays in URLs and logs.
2. **Send the access token in the `api-secret` header on the v1 API.** One request header in each of the three clients (Python, firmware, Swift), with the same endpoint, response, and parsing. No token in any URL, no expiry to manage, no extra round trip. It is a less familiar use of a header whose name suggests the admin secret. A plaintext `API_SECRET` sent there does not match, because Nightscout compares that header against the secret's SHA-1 or SHA-512 hash, so a mix-up does not quietly grant admin rights.
3. **Exchange the access token for a JWT and send `Authorization: Bearer` on the v1 API.** Standard bearer auth. But the exchange itself carries the access token in a URL path every 8 hours, so it still reaches logs, just less often. Every client then has to cache the JWT, track its expiry, and redo the exchange on a 401. On the ESP32 that means extra state that has to survive deep sleep, and a redeploy that rotates the signing key breaks every display until each one re-exchanges.
4. **Move to the v3 API with JWT bearer auth (the request as written).** It brings all of option 3's costs, plus rewriting the entries query and the parsing in three implementations for a different response shape, while the displays gain nothing besides the auth change.

## Decision

Proposed: option 2. Send the readable access token in the `api-secret` request header, keep the v1 entries endpoint, and stop putting the token in the URL. Option 3 is the fallback if Nightscout ever drops the header path. Option 4 is not pursued unless Lightkeeper needs something only v3 offers.

When accepted, the implementation is one change across all three clients, in a single commit per the parity rule:

- Python `NightscoutClient`, firmware (once the device HTTP layer exists, FR-010), and Swift `NightscoutClient` send `api-secret: <token>` and no `token` query parameter.
- Tests assert that the token appears in no request URL and that the header is present. The existing redaction tests (NFR-001) keep covering error messages.
- The same-scheme, same-host redirect rule matters more now that a header carries the credential, and it already exists in all clients.
- Update the residual-risk line in `docs/SECURITY_MODEL.md`, the token note in `docs/ENV_VARS.md`, and `docs/SETUP.md` step 6.

## Consequences

- The readable token no longer appears in URLs, proxy logs, or hosting logs. The remaining exposure is the TLS session and the device itself.
- No new state, timers, or round trips. Firmware stays simple, and a Nightscout redeploy cannot strand the displays.
- The project depends on an undocumented but long-standing v1 behaviour: an access token is accepted in the `api-secret` header. The real-instance promotion check above confirms it once. After that, repeat the check on every Nightscout upgrade (already a review trigger in `docs/SAFETY.md`): a regression would show as 401s and the screen would go NO DATA, the safe direction. If Nightscout removes the path, option 3 is the move.
- `AUTH_DEFAULT_ROLES=denied` stays required. Without it, an unauthenticated read succeeds anyway and the token's transport matters less.

## Alternatives Considered

Options 1, 3, and 4 above. A personal reverse proxy that strips `token` from logged URLs was also considered and rejected: it depends on every hosting option's logging configuration, and managed hosts (see `docs/SETUP.md`, "Choosing a host") don't offer that control.
