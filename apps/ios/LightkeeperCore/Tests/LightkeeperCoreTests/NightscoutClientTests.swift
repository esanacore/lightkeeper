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

    // MARK: The base URL, as the settings screen validates it

    func reason(_ baseURL: String) -> String? {
        do {
            _ = try NightscoutClient(baseURL: baseURL, token: nil)
            return nil
        } catch NightscoutError.badURL(let reason) {
            return reason
        } catch {
            XCTFail("\(baseURL): \(error)")
            return nil
        }
    }

    func testBaseURLIsRejectedWithAReasonForHTTPAPathAQueryOrATypo() {
        let rejected: [(String, String)] = [
            ("http://ns.example.com", "must start with https://"),
            ("https://ns.example.com/api/v1/entries", "nothing after its name"),
            ("https://ns.example.com/nightscout/", "nothing after its name"),
            ("https://ns.example.com/?token=abc123", "no ?, # or login"),
            ("https://ns.example.com#top", "no ?, # or login"),
            ("https://me:pw@ns.example.com", "no ?, # or login"),
            ("htps://ns.example.com", "must start with https://"),
            ("https//ns.example.com", "full address"),
            ("https:/ns.example.com", "full address"),
            ("ns.example.com", "full address"),
            ("", "full address"),
            ("https://ns,example.com", "Check it for typos"),
            ("https://ns..example.com", "Check it for typos"),
            ("https://ns_example.com", "Check it for typos"),
            ("https://-ns.example.com", "Check it for typos"),
            ("https://ns.example.com ", "space"),
            ("https://ns example.com", "space"),
        ]
        for (url, expected) in rejected {
            let why = reason(url)
            XCTAssertNotNil(why, url)
            XCTAssertTrue(why?.contains(expected) ?? false, "\(url): \(why ?? "accepted")")
        }
    }

    func testJustTheSiteIsAccepted() {
        for url in ["https://ns.example.com", "https://ns.example.com/", "HTTPS://NS.Example.COM",
                    "https://ns.example.com:8443", "https://my-ns.herokuapp.com", "https://ns.example.com."] {
            XCTAssertNil(reason(url), url)
        }
        XCTAssertNoThrow(try NightscoutClient(baseURL: "http://localhost:1337", token: nil, allowHTTP: true))
    }

    func testSiteNames() {
        XCTAssertTrue(NightscoutClient.isSiteName("ns.example.com"))
        XCTAssertTrue(NightscoutClient.isSiteName("localhost"))
        XCTAssertTrue(NightscoutClient.isSiteName("::1"))
        XCTAssertTrue(NightscoutClient.isSiteName("[::1]"))
        XCTAssertFalse(NightscoutClient.isSiteName("."))
        XCTAssertFalse(NightscoutClient.isSiteName("ns-.example.com"))
        XCTAssertFalse(NightscoutClient.isSiteName(String(repeating: "a", count: 64) + ".example"))
        XCTAssertFalse(NightscoutClient.isSiteName("ns%20x.example"))
        XCTAssertFalse(NightscoutClient.isSiteName("bücher.example"))
    }

    // MARK: Error kinds, for the settings screen's connection check

    func response(_ status: Int) throws -> HTTPURLResponse {
        try XCTUnwrap(HTTPURLResponse(url: URL(string: "https://ns.example.com/api/v1/entries/sgv.json")!,
                                      statusCode: status, httpVersion: "HTTP/1.1", headerFields: nil))
    }

    func kind(status: Int, body: String = "[]") throws -> NightscoutError.Kind? {
        do {
            _ = try NightscoutClient.entries(from: Data(body.utf8), response: response(status))
            return nil
        } catch let error as NightscoutError {
            return error.kind
        }
    }

    func testUnauthorizedIsTokenRejected() throws {
        XCTAssertEqual(try kind(status: 401), .tokenRejected)
    }

    func testForbiddenIsTokenRejected() throws {
        XCTAssertEqual(try kind(status: 403), .tokenRejected)
    }

    func testServerErrorIsUnreachable() throws {
        for status in [500, 502, 503, 599] {
            XCTAssertEqual(try kind(status: status), .unreachable, "\(status)")
        }
    }

    func testNonJSONIsNotNightscout() throws {
        XCTAssertEqual(try kind(status: 200, body: "<html>Hello</html>"), .notNightscout)
        XCTAssertEqual(try kind(status: 200, body: "{\"status\": 200}"), .notNightscout, "JSON, but not a list")
        XCTAssertEqual(try kind(status: 404), .notNightscout)
        XCTAssertEqual(try kind(status: 302), .notNightscout, "a redirect the guard refused")
        let huge = "[" + String(repeating: " ", count: NightscoutClient.maxResponseBytes) + "]"
        XCTAssertEqual(try kind(status: 200, body: huge), .notNightscout)
    }

    func testAnEntriesListIsReturned() throws {
        let list = try NightscoutClient.entries(from: Data("[{\"sgv\": 120}]".utf8), response: response(200))
        XCTAssertEqual(list.count, 1)
        XCTAssertNil(try kind(status: 204, body: "[]"))
    }

    func testEveryErrorHasAKind() {
        XCTAssertEqual(NightscoutError.badURL("x").kind, .badURL)
        XCTAssertEqual(NightscoutError.unreachable("x").kind, .unreachable)
        XCTAssertEqual(NightscoutError.notJSON.kind, .notNightscout)
        XCTAssertEqual(NightscoutError.notAList.kind, .notNightscout)
        XCTAssertEqual(NightscoutError.tooLarge.kind, .notNightscout)
        struct Other: Error {}
        XCTAssertEqual(NightscoutClient.kind(of: Other()), .unreachable)
        XCTAssertEqual(NightscoutClient.kind(of: NightscoutError.httpStatus(403)), .tokenRejected)
    }

    /// A real lookup of a name that can never resolve (RFC 6761 reserves
    /// `.invalid`): the whole path, from the GET to the report, with the token
    /// kept out of the error.
    func testUnresolvableNameIsUnreachable() async throws {
        let client = try NightscoutClient(baseURL: "https://lightkeeper-check.invalid", token: token,
                                          timeout: 5)
        do {
            _ = try await client.fetchEntries()
            XCTFail("a .invalid name resolved")
        } catch let error as NightscoutError {
            XCTAssertEqual(error.kind, .unreachable)
            XCTAssertFalse("\(error)".contains(token), "the token never appears in an error")
        }
        let check = await client.checkConnection()
        XCTAssertEqual(check, .failed(.unreachable))
    }

    // MARK: The connection report, in plain words

    let nowMs: Int64 = 1_792_324_800_000

    func report(_ check: ConnectionCheck) -> String {
        connectionReport(check, nowMs: nowMs, thresholds: .defaults)
    }

    func reading(minutesAgo: Int64) -> GlucoseReading {
        GlucoseReading(mgdl: 112, timestampMs: nowMs - minutesAgo * 60_000, trend: .flat)
    }

    func testConnectedReportsTheNewestReadingsAge() {
        XCTAssertEqual(report(.connected(newest: reading(minutesAgo: 3))),
                       "Connected. The newest reading came in 3 minutes ago.")
        XCTAssertEqual(report(.connected(newest: reading(minutesAgo: 0))),
                       "Connected. The newest reading came in just now.")
        XCTAssertEqual(report(.connected(newest: reading(minutesAgo: 15))),
                       "Connected. The newest reading came in 15 minutes ago.", "at the limit is fresh")
        XCTAssertEqual(report(.connected(newest: reading(minutesAgo: 16))),
                       "Connected, but the newest reading came in 16 minutes ago, "
                           + "so the display shows STALE until a new one arrives.")
        XCTAssertEqual(report(.connected(newest: reading(minutesAgo: 3 * 60 + 10))),
                       "Connected, but the newest reading came in 3 hours ago, "
                           + "so the display shows STALE until a new one arrives.")
        XCTAssertTrue(report(.connected(newest: reading(minutesAgo: -3))).contains("dated in the future"))
        XCTAssertEqual(report(.connected(newest: nil)),
                       "Connected, but Nightscout has no glucose readings to show yet.")
    }

    func testTheReportFollowsTheStaleLimit() throws {
        let ten = try Thresholds(staleAfterMs: 10 * 60_000)
        XCTAssertTrue(connectionReport(.connected(newest: reading(minutesAgo: 11)), nowMs: nowMs,
                                       thresholds: ten).contains("STALE"))
    }

    func testFailuresAreReportedInPlainWords() {
        XCTAssertTrue(report(.failed(.tokenRejected)).hasPrefix("Nightscout refused the token."))
        XCTAssertTrue(report(.failed(.unreachable)).hasPrefix("Could not reach the site."))
        XCTAssertTrue(report(.failed(.notNightscout)).hasPrefix("The site answered, but not"))
        XCTAssertTrue(report(.failed(.badURL)).hasPrefix("That address cannot be used."))
    }

    func testElapsedWords() {
        XCTAssertEqual(elapsedWords(0), "just now")
        XCTAssertEqual(elapsedWords(119 * 60_000), "119 minutes ago")
        XCTAssertEqual(elapsedWords(120 * 60_000), "2 hours ago")
        XCTAssertEqual(elapsedWords(47 * 3_600_000 + 59 * 60_000), "47 hours ago")
        XCTAssertEqual(elapsedWords(48 * 3_600_000), "2 days ago")
    }
}
