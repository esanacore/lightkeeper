// FR-001 / FR-005 / FR-012: raw Nightscout responses lead to the same
// conclusion in Swift as in Python and the firmware (spec/response_vectors.json).
// The path under test is the app's own: JSONSerialization, then parseEntries.

import Foundation
import XCTest
@testable import LightkeeperCore

final class ResponseVectorTests: XCTestCase {
    struct Expected: Decodable, Equatable {
        let mgdl: Int
        let date: Int64
        let trend: String
    }

    enum Expect: Decodable, Equatable {
        case error
        case none
        case reading(Expected)

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if container.decodeNil() {
                self = .none
            } else if let text = try? container.decode(String.self), text == "error" {
                self = .error
            } else {
                self = .reading(try container.decode(Expected.self))
            }
        }
    }

    struct Case: Decodable {
        let name: String
        let body: String
        let expect: Expect
        /// Safe alternatives where Foundation's JSON parser differs from Python's.
        let swift_also_accepts: [Expect]?
    }

    struct Spec: Decodable {
        let spec_version: Int
        let cases: [Case]
    }

    func loadSpec() throws -> Spec {
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        while !FileManager.default.fileExists(atPath: url.appendingPathComponent("spec").path),
              url.path != "/" {
            url.deleteLastPathComponent()
        }
        let path = url.appendingPathComponent("spec/response_vectors.json")
        return try JSONDecoder().decode(Spec.self, from: Data(contentsOf: path))
    }

    /// What the app concludes from one response body.
    func conclude(_ body: String) -> Expect {
        guard let json = try? JSONSerialization.jsonObject(with: Data(body.utf8)),
              let list = json as? [Any] else {
            return .error
        }
        guard let newest = parseEntries(list).first else { return .none }
        return .reading(Expected(mgdl: newest.mgdl, date: newest.timestampMs, trend: newest.trend.rawValue))
    }

    func testEveryResponseVectorMatches() throws {
        let spec = try loadSpec()
        XCTAssertEqual(spec.spec_version, 1, "bump this assertion when an existing case changes")
        XCTAssertGreaterThan(spec.cases.count, 30)
        for c in spec.cases {
            let allowed = [c.expect] + (c.swift_also_accepts ?? [])
            let got = conclude(c.body)
            XCTAssertTrue(allowed.contains(got), "response \(c.name): got \(got), allowed \(allowed)")
        }
    }
}
