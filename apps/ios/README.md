# Lightkeeper for iOS

The companion app from ADR-0008. This is the read-only layer (Phase 5a): the same status every Lightkeeper display shows, big and calm, with the same rules. It talks to Nightscout only. There is no pump or sensor code here, and the bolus request screen (Phase 5b) does not exist yet; it is gated by the promotion criteria in ADR-0008.

## Layout

- `LightkeeperCore/`: a Swift package with the display rules (parse, classify, render) and the read-only Nightscout client. `VectorTests` runs every case in `spec/display_vectors.json`, so the Swift rules are held identical to the Python and C++ ones.
- `Lightkeeper/`: the SwiftUI app. `project.yml` is an XcodeGen spec; the `.xcodeproj` is generated, not committed.

## Building without a Mac

`.github/workflows/ios.yml` runs the package tests on GitHub's macOS runners and in a Linux Swift container, and builds the app and runs its unit tests (`Lightkeeper/Tests/`: settings persistence and foreground re-classification) on an iOS simulator, whenever iOS code or the vectors change. That is the project's build machine. TestFlight distribution will use the same path with signing secrets added, the way Trio's browser build does.

## Building with a Mac

```bash
brew install xcodegen
cd apps/ios/LightkeeperCore && swift test
cd ../Lightkeeper && xcodegen generate && open Lightkeeper.xcodeproj
```

## Settings and secrets

The Nightscout URL and display thresholds live in UserDefaults. The readable token lives in the Keychain (`Keychain.swift`), protected until first unlock, and is never written to UserDefaults or logs. Use a token with the readable role only, never the API secret.

## What's next

Widgets and a watch complication (same core, same rules), background refresh, mmol/L, delta and IOB from Nightscout's device status, then the bolus request path once ADR-0008 is accepted.
