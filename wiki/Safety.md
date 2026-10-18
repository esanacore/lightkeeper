# Safety

Lightkeeper touches a real person's diabetes care, so its limits are written down and enforced by tests.

## What Lightkeeper never does

- It never sends a command to an insulin pump or calculates a dose. That is Trio's job.
- It never talks to the sensor directly.
- It never writes to Nightscout.
- It never replaces the primary app's alarms.

Changing any of these needs a new architecture decision, a hazard review, and Kaitlin's agreement. The full boundary and hazard log are `docs/SAFETY.md` in the repository; the security and privacy model is `docs/SECURITY_MODEL.md`.

## How it avoids misleading you

- Readings older than 15 minutes, or dated in the future, show STALE instead of a number that looks current.
- Entries that are out of range, fractional, or the wrong type are dropped, never "fixed".
- Sensor out-of-range values show as words ("LOW (<40)"), not as precise numbers.
- If Nightscout goes down, the screen says so and the last reading ages into STALE on its own.

Back to [[Home]] or [[Getting Started]].
