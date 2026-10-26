// NFR-001 / ADR-0009: the readable token travels in the `api-secret` header
// and never in a URL, so it stays out of proxy and hosting access logs.

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import XCTest
@testable import LightkeeperCore

final class NightscoutClientTests: XCTestCase {
    let token = "readable-abc123secret"

    func client(token: String?) throws -> NightscoutClient {
        try NightscoutClient(baseURL: "https://ns.example.com", token: token)
    }

    func testTokenTravelsInAHeaderNeverTheURL() throws {
        let request = try client(token: token).entriesRequest(count: 5)
        let url = try XCTUnwrap(request.url).absoluteString
        XCTAssertEqual(url, "https://ns.example.com/api/v1/entries/sgv.json?count=5")
        XCTAssertFalse(url.contains(token))
        XCTAssertFalse(url.contains("token="))
        XCTAssertEqual(request.value(forHTTPHeaderField: "api-secret"), token)
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Accept"), "application/json")
    }

    func testNoTokenMeansNoHeader() throws {
        let request = try client(token: nil).entriesRequest(count: 12)
        XCTAssertNil(request.value(forHTTPHeaderField: "api-secret"))
        XCTAssertFalse(try XCTUnwrap(request.url).absoluteString.contains("token"))
    }

    func testSameSiteRedirectKeepsTheHeader() throws {
        let original = try client(token: token).entriesRequest(count: 1)
        let next = URLRequest(url: URL(string: "https://ns.example.com/api/v1/entries/sgv.json?count=1&r=1")!)
        let followed = try XCTUnwrap(NightscoutClient.redirect(from: original, to: next, token: token))
        XCTAssertEqual(followed.value(forHTTPHeaderField: "api-secret"), token)
        XCTAssertFalse(try XCTUnwrap(followed.url).absoluteString.contains(token))
    }

    func testRedirectToAnotherSchemeOrHostIsRefused() throws {
        let original = try client(token: token).entriesRequest(count: 1)
        for target in ["http://ns.example.com/api/v1/entries/sgv.json",
                       "https://evil.example.net/api/v1/entries/sgv.json"] {
            let next = URLRequest(url: URL(string: target)!)
            XCTAssertNil(NightscoutClient.redirect(from: original, to: next, token: token), target)
        }
    }

    func testRedactHidesTheToken() throws {
        XCTAssertEqual(try client(token: token).redact("failed: \(token)"), "failed: ***")
    }
}
