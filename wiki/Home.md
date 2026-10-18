# Lightkeeper

Current version: 0.1.0

Lightkeeper is an open source type 1 diabetes project, built by Eric and Kaitlin alongside the #WeAreNotWaiting community. It sits next to Nightscout and turns Kaitlin's glucose data into calm, glanceable screens: e-ink displays, bedside clocks, and Home Assistant alerts. It is read-only by design. It never talks to the pump or the sensor; insulin dosing stays in Trio, a mature community app, set up with Kaitlin's care team.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Where to start

- [[Getting Started]]: install it, try the demo, point it at Nightscout.
- [[How It Works]]: the whole stack in one picture, and where Lightkeeper fits.
- [[Safety]]: what Lightkeeper will never do, and how it avoids showing a misleading number.

## The rule that matters most

Old data is never shown as current. A reading older than 15 minutes, or dated in the future, shows **STALE - DO NOT TRUST**, even if the number looks fine. Every screen Lightkeeper can show is pictured in `docs/DISPLAY_STATES.md` in the repository.

## Project status

Version 0.1.0 has the Python display tool with full test coverage and the safety rules ported to C++ for an Xteink pocket e-ink display. Next up: a self-hosted Nightscout, Trio on Kaitlin's iPhone in open loop, and the first real e-ink hardware. The roadmap is `docs/MVP_BACKLOG.md`.
