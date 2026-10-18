# ADR-0002: Trio on Kaitlin's iPhone Is the Dosing Controller

Status: Proposed

Date: 2026-10-17

## Relationships

- Extends: none
- Supersedes: none
- Related: ADR-0004, docs/SAFETY.md, https://triodocs.org, https://nightscout.github.io/omnipod-five/

## Promotion Criteria

- Kaitlin's endocrinologist has reviewed the plan and her therapy settings for Trio.
- Trio has run in open loop for at least two weeks with settings validated against her current results.
- Omnipod 5 pod support in Trio has been exercised through at least five pod changes without unresolved faults, and any issues were reported upstream with logs.

## Context

Kaitlin uses a Dexcom G7 and Omnipod 5 pods with an iPhone, and wants to move to open source tools. As of October 2026:

- Trio (iOS) lists Omnipod 5 pods as compatible in open beta, alongside DASH, Eros, and Dana-i.
- Loop supports Omnipod 5 only in development branches.
- AndroidAPS support for Omnipod 5 is earlier stage, expected late 2026 or early 2027.
- When paired with Trio, an Omnipod 5 pod stops talking to the CGM and only takes commands from Trio, so pod and sensor must both be in range of the phone.
- On iPhone, Trio reads G7 data by intercepting the Dexcom G7 app on the same phone, so that app stays installed as a background radio.

## Decision

Use Trio, built from source on Kaitlin's iPhone, as the only component that makes dosing decisions. Keep the Dexcom G7 app installed only as the sensor radio. Keep the official Omnipod 5 app or Controller available as a fallback, since pairing a fresh pod with it restores the stock algorithm.

Roll out in phases: CGM and Nightscout only, then open loop (suggestions only), then closed loop after settings are validated with her care team.

## Consequences

- Kaitlin keeps her phone, sensor, and pods; no prescription change is needed to start.
- Dosing logic stays in a reviewed community project, not in our code.
- We depend on a beta pump driver; our QA effort goes into testing and reporting upstream.
- We need a paid Apple Developer account. Eric has no Mac, so Trio is built with the browser build method (GitHub Actions uploading to TestFlight), and builds must be refreshed before TestFlight expiry.
- The Dexcom app is not fully eliminated on iPhone.

## Alternatives Considered

- **Android collector plus AndroidAPS:** fully removes the Dexcom app via xDrip+, but AndroidAPS does not yet support Omnipod 5. Revisit when it does.
- **Loop:** Omnipod 5 only in development branches today.
- **Switch to Omnipod DASH pods:** mature support in all three apps, but requires a prescription change and loses nothing we need yet.
- **Switch the CGM to FreeStyle Libre 3 Plus:** Kaitlin is considering this. Trio's docs say it connects to Libre 3/3 Plus directly (NFC pairing, then Bluetooth) with no Abbott app, in all regions, which would remove the last proprietary app from the phone. As of October 2026 that support is open beta, dev branch only, and needs a paid Apple Developer account. Deferred so we don't stack two betas (pump driver and CGM driver) at once; revisit after closed loop is stable, or sooner if Kaitlin and her endo prefer Libre for other reasons. US Libre 2 sensors are not supported for direct connection.
- **Stay on stock Omnipod 5 SmartAdjust:** no change, but doesn't meet the goal of open source control.
