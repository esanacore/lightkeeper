# Architecture Decision Records

Every significant architecture or safety decision, numbered in the order it was made. Use `constitution/templates/ADR.md` for new records, and never reuse a number. A change to the safety boundary (ADR-0004) needs a new ADR, a hazard review in `docs/SAFETY.md`, and Kaitlin's agreement.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record Architecture Decisions | Accepted | 2026-10-17 |
| [0002](0002-trio-on-iphone-as-dosing-controller.md) | Trio on Kaitlin's iPhone Is the Dosing Controller | Proposed | 2026-10-17 |
| [0003](0003-self-hosted-nightscout-as-data-hub.md) | Self-Hosted Nightscout Is the Data Hub | Proposed | 2026-10-17 |
| [0004](0004-no-insulin-delivery-code-in-this-repo.md) | No Insulin Delivery Code or Hardware in This Repository | Accepted | 2026-10-17 |
| [0005](0005-read-only-display-layer-in-python.md) | Read-Only Display Layer in Python, Standard Library at Runtime | Accepted | 2026-10-17 |
| [0006](0006-xteink-esp32-display-with-shared-vectors.md) | Xteink ESP32-C3 Pocket Display, Kept in Lockstep with Python by Shared Vectors | Proposed | 2026-10-17 |
| [0007](0007-cpp-style-google-base-mirrored-naming.md) | C++ Style, Google Base with Naming That Mirrors the Python | Accepted | 2026-10-24 |
| [0008](0008-companion-app-and-bolus-requests-via-trio.md) | Companion App, with Bolus Requests Only Through Trio's Remote Protocol | Proposed | 2026-10-18 |
| [0009](0009-nightscout-token-in-a-header-not-the-url.md) | Send the Nightscout Readable Token in a Header, Not the URL | Accepted | 2026-10-25 |
| [0010](0010-home-assistant-via-mqtt-discovery.md) | Publish to Home Assistant over MQTT Discovery | Accepted | 2026-10-26 |
| [0011](0011-screen-text-v2.md) | Screen Text v2: No Arrow on STALE, the Failing Link Named, and a STALE Age No Fresh Screen Shows | Proposed | 2026-10-27 |
