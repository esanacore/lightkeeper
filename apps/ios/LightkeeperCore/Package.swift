// swift-tools-version: 5.9
// LightkeeperCore: the display rules and the read-only Nightscout client,
// as a Swift package shared by the iOS app, its widgets, and the watch app.
//
// The rules must stay identical to src/lightkeeper (Python) and
// firmware/xteink/lib/glucose_rules (C++). VectorTests runs every case in
// spec/display_vectors.json against this package to prove it.

import PackageDescription

let package = Package(
    name: "LightkeeperCore",
    platforms: [.iOS(.v17), .macOS(.v13), .watchOS(.v10)],
    products: [
        .library(name: "LightkeeperCore", targets: ["LightkeeperCore"])
    ],
    targets: [
        .target(name: "LightkeeperCore", path: "Sources/LightkeeperCore"),
        .testTarget(
            name: "LightkeeperCoreTests",
            dependencies: ["LightkeeperCore"],
            path: "Tests/LightkeeperCoreTests"
        ),
    ]
)
