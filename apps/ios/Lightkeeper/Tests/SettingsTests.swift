// HAZ-006 / HAZ-012: the app never runs on thresholds other than the ones its
// settings screen shows. An impossible set found on disk is reset to the
// defaults, and the reset is written back.

import LightkeeperCore
import XCTest
@testable import Lightkeeper

final class SettingsTests: XCTestCase {
    private var defaults: UserDefaults!
    private var suiteName: String!

    override func setUp() {
        super.setUp()
        suiteName = "SettingsTests-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        super.tearDown()
    }

    func testEmptyStoreLoadsTheDefaults() {
        let s = Settings.load(from: defaults)
        XCTAssertEqual([s.urgentLow, s.low, s.high, s.urgentHigh, s.staleMinutes], [55, 70, 180, 250, 15])
        XCTAssertEqual(s.thresholds, .defaults)
    }

    func testValidStoredSetIsKept() {
        var custom = Settings()
        custom.nightscoutURL = "https://ns.example.com"
        custom.urgentLow = 60; custom.low = 80; custom.high = 160; custom.urgentHigh = 220
        custom.staleMinutes = 10
        XCTAssertTrue(custom.save(to: defaults))

        let s = Settings.load(from: defaults)
        XCTAssertEqual([s.urgentLow, s.low, s.high, s.urgentHigh, s.staleMinutes], [60, 80, 160, 220, 10])
        XCTAssertEqual(s.nightscoutURL, "https://ns.example.com")
    }

    func testInvalidStoredSetIsResetAndWrittenBack() {
        // Low above high: would hide lows if it were ever used.
        defaults.set("https://ns.example.com", forKey: "nightscoutURL")
        defaults.set(55, forKey: "urgentLow")
        defaults.set(200, forKey: "low")
        defaults.set(180, forKey: "high")
        defaults.set(250, forKey: "urgentHigh")
        defaults.set(15, forKey: "staleMinutes")

        let s = Settings.load(from: defaults)
        XCTAssertTrue(s.isValid)
        XCTAssertEqual([s.urgentLow, s.low, s.high, s.urgentHigh, s.staleMinutes], [55, 70, 180, 250, 15])
        XCTAssertEqual(s.nightscoutURL, "https://ns.example.com", "only the thresholds are reset")
        XCTAssertEqual(defaults.integer(forKey: "low"), 70, "the reset is saved, so the next launch agrees")
    }

    func testZeroStaleLimitOnDiskIsReset() {
        defaults.set(0, forKey: "staleMinutes")
        let s = Settings.load(from: defaults)
        XCTAssertEqual(s.staleMinutes, 15)
        XCTAssertEqual(defaults.integer(forKey: "staleMinutes"), 15)
    }

    func testSaveRefusesAnInvalidSetAndWritesNothing() {
        var bad = Settings()
        bad.low = 300
        XCTAssertFalse(bad.save(to: defaults))
        XCTAssertNil(defaults.object(forKey: "low"))
        XCTAssertNotNil(bad.validationMessage)
    }
}
