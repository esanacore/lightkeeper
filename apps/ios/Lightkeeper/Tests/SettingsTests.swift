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

    // MARK: The Nightscout address

    func testTheURLIsRejectedInlineForHTTPAPathAQueryOrATypo() {
        let rejected = [
            "http://ns.example.com",                  // http://
            "https://ns.example.com/nightscout",      // a path
            "https://ns.example.com/api/v1/entries",  // a pasted endpoint
            "https://ns.example.com/?token=abc123",   // a query, here with a token in it
            "htps://ns.example.com",                  // typos
            "https//ns.example.com",
            "https://ns,example.com",
            "ns.example.com",
        ]
        for url in rejected {
            var s = Settings()
            s.nightscoutURL = url
            XCTAssertNotNil(s.urlProblem, url)
            XCTAssertFalse(s.urlProblem?.isEmpty ?? true, "\(url): the reason is shown")
            XCTAssertFalse(s.isConfigured, url)
            XCTAssertFalse(s.canSave, "\(url): Save is disabled")
            XCTAssertFalse(s.save(to: defaults), url)
            XCTAssertNil(defaults.object(forKey: "nightscoutURL"), "\(url): nothing is written")
        }
    }

    func testAUsableURLSaves() {
        for url in ["https://ns.example.com", "https://ns.example.com/", "https://ns.example.com:8443"] {
            var s = Settings()
            s.nightscoutURL = url
            XCTAssertNil(s.urlProblem, url)
            XCTAssertTrue(s.isConfigured, url)
            XCTAssertTrue(s.save(to: defaults), url)
            XCTAssertEqual(defaults.string(forKey: "nightscoutURL"), url)
        }
    }

    func testAnEmptyURLIsNotConfiguredAndNotAnError() {
        let s = Settings()
        XCTAssertNil(s.urlProblem, "nothing typed yet is not a mistake")
        XCTAssertFalse(s.isConfigured)
        XCTAssertTrue(s.canSave, "thresholds can be saved before the site")
    }

    func testAnUnusableStoredURLIsKeptForSettingsToExplain() {
        // An address an older build accepted, with thresholds that need a reset.
        defaults.set("https://ns.example.com/nightscout", forKey: "nightscoutURL")
        defaults.set(300, forKey: "low")
        let s = Settings.load(from: defaults)
        XCTAssertFalse(s.isConfigured)
        XCTAssertNotNil(s.urlProblem)
        XCTAssertEqual(s.nightscoutURL, "https://ns.example.com/nightscout")
        XCTAssertEqual(defaults.integer(forKey: "low"), 70, "the threshold reset is still written back")
    }

    // MARK: Thresholds

    func testResetRestoresTheDefaults() {
        var s = Settings()
        s.nightscoutURL = "https://ns.example.com"
        s.urgentLow = 60; s.low = 85; s.high = 160; s.urgentHigh = 220; s.staleMinutes = 40
        let reset = s.resettingThresholds()
        XCTAssertEqual([reset.urgentLow, reset.low, reset.high, reset.urgentHigh, reset.staleMinutes],
                       [55, 70, 180, 250, 15])
        XCTAssertEqual(reset.thresholds, .defaults)
        XCTAssertEqual(reset.nightscoutURL, "https://ns.example.com", "the site is not a threshold")
    }

    func testTheCautionShowsAboveFifteenMinutes() {
        var s = Settings()
        for minutes in [6, 10, 15] {
            s.staleMinutes = minutes
            XCTAssertNil(s.staleCaution, "\(minutes) min")
        }
        for minutes in [16, 30, 60] {
            s.staleMinutes = minutes
            XCTAssertNotNil(s.staleCaution, "\(minutes) min")
        }
    }

    func testTheStepsAndTheCapAreUnchangedRules() {
        XCTAssertEqual(Settings.thresholdStep, 5)
        XCTAssertEqual(Settings.staleRange, 6...60, "the 60-minute cap stays until D16 decides")
        XCTAssertEqual(Settings.staleCautionAbove, 15)
    }
}
