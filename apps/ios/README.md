# Lightkeeper for iOS

The companion app from ADR-0008. This is the read-only layer (Phase 5a): the same status every Lightkeeper display shows, big and calm, with the same rules. It talks to Nightscout only. There is no pump or sensor code here, and the bolus request screen (Phase 5b) does not exist yet; it is gated by the promotion criteria in ADR-0008.

## Layout

- `LightkeeperCore/`: a Swift package with the display rules (parse, classify, render), the spoken form, the glance timeline, the phone's screen hierarchy and the read-only Nightscout client. It builds and tests on macOS, Linux and Windows.
  - `VectorTests` runs every case in `spec/display_vectors.json`, so the Swift rules are held identical to the Python and C++ ones.
  - `SpokenVectorTests` runs every sentence in `spec/spoken_vectors.json`, so VoiceOver hears exactly what the Python spoken form says (FR-017).
  - `GlanceTimeline.swift` works out every frame a widget will need ahead of time, with STALE among them at the first stale millisecond (FR-019); `GlanceTimelineTests` holds it to those rules.
  - `Presentation.swift` decides how the phone arranges one status (`ScreenPresentation`): the status word and its shape, the hero, the struck `last:` line, the age, the context lines, the text style of each, and the VoiceOver label. `PresentationTests` checks it against every display vector, so the hierarchy is tested without a Mac.
  - `NightscoutClient.swift` also validates a typed address with the reason in plain words, and runs the settings screen's one-GET connection check.
- `Lightkeeper/`: the SwiftUI app. `project.yml` is an XcodeGen spec; the `.xcodeproj` is generated, not committed.

## The glance screen

Top to bottom, in the Keeper's Logbook order (docs/BRAND.md): the status, the number with its arrow, the age, the context lines, then the chrome. Every word comes from the vector lines (`renderLines`), and every status has its word and a shape, so color is only the second cue.

- **IN RANGE, LOW, HIGH**: the status word in Ink on its tint with a 2 pt status-color border, never smaller than `.title3`. The number is the hero: it scales with Dynamic Type from 96 pt (relative to `.largeTitle`), heavy, with monospaced digits; the arrow keeps its 40/96 proportion; only the number may shrink to fit.
- **URGENT LOW, URGENT HIGH**: a full-width Ink band with the word in Band text and a 4 pt status-color leading rule, at `.title`. The number stays the hero, and the band is never shorter than it: its minimum height is the number's 96 pt, scaled by the same Dynamic Type factor, so the full-width band is the largest element on the screen.
- **STALE - DO NOT TRUST**: a full-width Ink band at `.title`, with a hatch in the margin (a solid rule under Increase Contrast), and the largest text on the screen. There is no big number, no separate arrow and no unit: the `last:` line is shown verbatim at body size, struck through, in Muted (HAZ-001, HAZ-008).
- **NO DATA**, and any headline nobody planned for: a dashed frame at `.title` and `--` where a number would be.
- The age line is Ink, semibold, monospaced. Below it, `checked HH:MM` and, during an outage, `Nightscout unreachable since HH:MM`: absolute times, so nothing on screen ticks.
- VoiceOver reads the glance as one element, in sentences: `spokenText(status:error:)`, for example "In range. 112 milligrams per deciliter, steady. 3 minutes ago."
- Pull to refresh fetches at once and shows a static `checking Nightscout...` while it runs. Nothing animates, blinks or makes a sound; a change is one redraw.
- Below the glance, the panel preview draws `renderLines` exactly, on Paper by day and on Night paper in dark mode.
- Until a usable Nightscout address is saved, the glance is replaced by a setup card ("Add your Nightscout site to start") with a button to Settings. It has no number and no level word, and the app makes no fetch.

The app re-ages the last reading against the clock the moment it returns to the foreground, before any fetch (`testReclassifyTurnsAnOldReadingStaleWithoutFetching`).

## Settings

- The address is checked as it is typed, by the same `NightscoutClient` initializer every fetch goes through: https only, just the site (no path, query, fragment or login), and a well-formed site name. The reason shows under the field, and Save stays disabled while the address cannot be used.
- **Check connection** makes one read-only GET with what is typed (token in the `api-secret` header, redirect guard intact) and says in plain words what happened: connected and how old the newest reading is, token refused (401 or 403), a token needed (401 or 403 with the token field empty), the site could not be reached, or the answer was not a Nightscout one. Each fetch uses its own URLSession, invalidated when the fetch ends, so neither the timer nor a check keeps a client alive.
- The thresholds step by 5 mg/dL (urgent low 40 to 100, low 45 to 150, high 100 to 350, urgent high 105 to 400), Stale after by 1 minute (6 to 60), and **Reset to defaults** restores 55 / 70 / 180 / 250 and 15 minutes. Above 15 minutes a caution explains that an old reading looks current for longer. An impossible set cannot be saved, and one found on disk is reset (HAZ-006, HAZ-012).

## Colors and the icon

`Lightkeeper/Sources/Palette.swift` mirrors `assets/brand/tokens.json`, one color per token in light and dark, and `tests/test_ios_palette.py` holds every value to that file and keeps hex colors out of the other sources. The asset catalog (`Lightkeeper/Sources/Assets.xcassets`) holds the app icon, `assets/brand/png/app-icon.png` at 1024 px (the brand PNG is 512 px, so each of its pixels is a 2x2 block), and the accent color, Beam text (Beam in dark mode), which tints control text; the same test checks both. It also holds the status shapes in `Presentation.swift` to the status table in `tokens.json`. `PresentationTests` reads that table too, so a change to it is caught in the Full Python suite even when `ios.yml` does not run.

## Building without a Mac

`.github/workflows/ios.yml` runs the package tests on GitHub's macOS runners and in a Linux Swift container, and builds the app and runs its unit tests (`Lightkeeper/Tests/`: settings persistence and validation, foreground re-classification, the outage start time, and the setup state that never fetches) on an iOS simulator, whenever iOS code or the vectors change. That is the project's build machine. TestFlight distribution will use the same path with signing secrets added, the way Trio's browser build does.

On Windows, `swift test` in `LightkeeperCore` runs the package tests with the Swift for Windows toolchain. The SwiftUI app target needs a Mac; a look at the glance at the largest accessibility text size (AX5) is a step for the first device or TestFlight install.

## Building with a Mac

```bash
brew install xcodegen
cd apps/ios/LightkeeperCore && swift test
cd ../Lightkeeper && xcodegen generate && open Lightkeeper.xcodeproj
```

## Settings and secrets

The Nightscout URL and display thresholds live in UserDefaults. The readable token lives in the Keychain (`Keychain.swift`), protected until first unlock, and is never written to UserDefaults or logs. It travels only in the `api-secret` request header, never in an address (ADR-0009). Use a token with the readable role only, never the API secret.

## What's next

Widgets and a watch complication (same core, same rules, built on the glance timeline), background refresh, mmol/L, delta and IOB from Nightscout's device status, then the bolus request path once ADR-0008 is accepted.
