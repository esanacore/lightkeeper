// Read-only Nightscout client. Ships on Apple platforms; also builds with the
// Linux and Windows Swift toolchains so the package tests run anywhere.
//
// Same contract as the Python client: HTTPS only, a readable-role token sent
// in the `api-secret` header and never in a URL (ADR-0009), GET on the sgv
// entries endpoint only, a bounded count, a response size cap, and no
// redirects that change scheme or host (a downgrade to http would send the
// token in the clear).
//
// The base URL is stricter here than in Python, because the app's settings
// screen validates what a person types through this initializer and shows
// the reason inline: the site and nothing else, so a pasted entries path or a
// `?token=` link is refused rather than fetched.

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum NightscoutError: Error, Equatable {
    /// The base URL cannot be used; the reason is in plain words, for Settings.
    case badURL(String)
    case unreachable(String)
    case notJSON
    case notAList
    case tooLarge
    case httpStatus(Int)
}

extension NightscoutError {
    /// What went wrong, in the terms a person can act on.
    public enum Kind: Equatable, Sendable {
        /// The address itself cannot be used.
        case badURL
        /// The site could not be reached: a name that does not resolve, a
        /// refused or timed-out connection, a TLS failure, or a 5xx from the
        /// host (the host answered, but the Nightscout behind it did not).
        case unreachable
        /// Nightscout refused the token (HTTP 401 or 403).
        case tokenRejected
        /// The site answered, but not with a Nightscout entries list: another
        /// HTTP status, a body that is not JSON or not a list, or one too large.
        case notNightscout
    }

    public var kind: Kind {
        switch self {
        case .badURL: return .badURL
        case .unreachable: return .unreachable
        case .httpStatus(401), .httpStatus(403): return .tokenRejected
        case .httpStatus(let code) where (500..<600).contains(code): return .unreachable
        case .httpStatus, .notJSON, .notAList, .tooLarge: return .notNightscout
        }
    }
}

public final class NightscoutClient: NSObject, URLSessionTaskDelegate {
    public static let maxResponseBytes = 1_000_000
    /// Nightscout's v1 API reads an access token from this header as well as
    /// from `?token=`; a plaintext API_SECRET here does not match (ADR-0009).
    public static let tokenHeader = "api-secret"
    public static let defaultTimeout: TimeInterval = 10

    private let baseURL: URL
    private let token: String?
    private let timeout: TimeInterval

    /// `token` must have the readable role only. `allowHTTP` exists for localhost tests.
    ///
    /// Throws `NightscoutError.badURL` with the reason in plain words unless
    /// `baseURL` is just a site: https, a host name, an optional port, and
    /// no path, query, fragment or login.
    public init(baseURL: String, token: String?, timeout: TimeInterval = defaultTimeout,
                allowHTTP: Bool = false) throws {
        guard !baseURL.contains(where: \.isWhitespace) else {
            throw NightscoutError.badURL("The address has a space in it. Remove the space.")
        }
        guard let url = URL(string: baseURL), let scheme = url.scheme?.lowercased(),
              let host = url.host, !host.isEmpty else {
            throw NightscoutError.badURL(
                "Enter the full address, starting with https://, like https://my-nightscout.example")
        }
        guard scheme == "https" || (scheme == "http" && allowHTTP) else {
            throw NightscoutError.badURL(
                "The address must start with https://, so glucose data and the token are never "
                    + "sent in the clear.")
        }
        guard url.query == nil, url.fragment == nil, url.user == nil, url.password == nil else {
            throw NightscoutError.badURL("Enter just the site, with no ?, # or login in the address.")
        }
        guard url.path.isEmpty || url.path == "/" else {
            throw NightscoutError.badURL(
                "Enter just the site, with nothing after its name, like https://my-nightscout.example")
        }
        guard Self.isSiteName(host) else {
            throw NightscoutError.badURL(
                "The site name can only have letters, digits, hyphens, and single dots between its "
                    + "parts. Check it for typos.")
        }
        self.baseURL = url
        self.token = token
        self.timeout = timeout
        super.init()
    }

    /// True for dot-separated labels of ASCII letters, digits and inner
    /// hyphens (with an optional final dot), or an IPv6 literal.
    static func isSiteName(_ host: String) -> Bool {
        var name = Substring(host)
        if name.hasPrefix("["), name.hasSuffix("]") { name = name.dropFirst().dropLast() }
        if name.contains(":") {
            return name.allSatisfy { $0.isHexDigit || $0 == ":" || $0 == "." }
        }
        var labels = name.split(separator: ".", omittingEmptySubsequences: false)
        if labels.count > 1, labels.last?.isEmpty == true { labels.removeLast() }
        return labels.allSatisfy { label in
            (1...63).contains(label.count) && label.first != "-" && label.last != "-"
                && label.allSatisfy { ($0.isASCII && ($0.isLetter || $0.isNumber)) || $0 == "-" }
        }
    }

    /// The entries URL. It never carries the token, so the token stays out of
    /// proxy and hosting access logs (ADR-0009).
    func entriesURL(count: Int) -> URL {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/entries/sgv.json"),
                                       resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "count", value: String(count))]
        return components.url!
    }

    /// True when requests carry the token header: a token was given and it
    /// is not empty.
    var sendsToken: Bool { !(token ?? "").isEmpty }

    /// The GET request for the newest `count` entries, token in the header.
    func entriesRequest(count: Int) -> URLRequest {
        var request = URLRequest(url: entriesURL(count: count))
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token, sendsToken { request.setValue(token, forHTTPHeaderField: Self.tokenHeader) }
        return request
    }

    /// Never let the token escape in an error message.
    func redact(_ text: String) -> String {
        guard let token, sendsToken else { return text }
        return text.replacingOccurrences(of: token, with: "***")
    }

    /// A session for one fetch: ephemeral, uncached, with this client as its
    /// delegate for the redirect guard. A URLSession holds its delegate
    /// strongly until it is invalidated, so every session made here is
    /// invalidated when its fetch ends; otherwise each fetch would keep its
    /// client and session alive for as long as the app runs.
    func makeSession() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout * 2
        config.urlCache = nil
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }

    /// Return the newest `count` raw entries as parsed JSON (an array of dictionaries).
    public func fetchEntries(count: Int = 12) async throws -> [Any] {
        precondition((1...288).contains(count), "count must be between 1 and 288")
        let request = entriesRequest(count: count)
        let session = makeSession()
        defer { session.finishTasksAndInvalidate() }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw unreachable(error)
        }
        return try Self.entries(from: data, response: response)
    }

    /// What a transport failure becomes: a name that does not resolve, a
    /// refused or timed-out connection, a TLS failure. Its message is the
    /// platform's, with the token redacted.
    func unreachable(_ error: Error) -> NightscoutError {
        .unreachable(redact(error.localizedDescription))
    }

    /// The entries in a response, or the error that says what is wrong with it.
    static func entries(from data: Data, response: URLResponse) throws -> [Any] {
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NightscoutError.httpStatus(http.statusCode)
        }
        guard data.count <= maxResponseBytes else { throw NightscoutError.tooLarge }
        guard let json = try? JSONSerialization.jsonObject(with: data) else { throw NightscoutError.notJSON }
        guard let list = json as? [Any] else { throw NightscoutError.notAList }
        return list
    }

    /// One read-only GET, the same request the display makes, reported for
    /// the settings screen: the newest reading, or what went wrong.
    public func checkConnection() async -> ConnectionCheck {
        await Self.check(sentToken: sendsToken) { try await self.fetchEntries() }
    }

    /// The outcome of one fetch, for the connection check. A refusal when no
    /// token was sent asks for one rather than saying a token was refused.
    static func check(sentToken: Bool, _ fetch: () async throws -> [Any]) async -> ConnectionCheck {
        do {
            return .connected(newest: parseEntries(try await fetch()).first)
        } catch {
            let found = Self.kind(of: error)
            if found == .tokenRejected && !sentToken { return .needsToken }
            return .failed(found)
        }
    }

    /// The kind for any error a fetch throws; anything unexpected counts as unreachable.
    static func kind(of error: Error) -> NightscoutError.Kind {
        (error as? NightscoutError)?.kind ?? .unreachable
    }

    // MARK: URLSessionTaskDelegate

    /// Refuse redirects that change scheme or host. A same-site redirect keeps
    /// the token header, set explicitly rather than trusting the platform to
    /// carry custom headers across a redirect.
    public func urlSession(_ session: URLSession, task: URLSessionTask,
                           willPerformHTTPRedirection response: HTTPURLResponse,
                           newRequest request: URLRequest,
                           completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(Self.redirect(from: task.originalRequest, to: request, token: token))
    }

    /// The request to follow for a redirect, or nil to refuse it.
    static func redirect(from original: URLRequest?, to request: URLRequest, token: String?) -> URLRequest? {
        let old = original?.url
        let new = request.url
        guard old?.scheme?.lowercased() == new?.scheme?.lowercased(), old?.host == new?.host else {
            return nil
        }
        var followed = request
        if let token, !token.isEmpty { followed.setValue(token, forHTTPHeaderField: tokenHeader) }
        return followed
    }
}

/// The outcome of a settings-screen connection check.
public enum ConnectionCheck: Equatable, Sendable {
    /// Nightscout answered with an entries list. `newest` is its newest
    /// reading that passes parseEntries, or nil when there is none.
    case connected(newest: GlucoseReading?)
    /// The site refused to be read (HTTP 401 or 403) and no token was sent.
    case needsToken
    case failed(NightscoutError.Kind)
}

/// A connection check in plain words, for the settings screen. Judged with
/// classify(), so "too old" here means exactly what STALE means on the
/// display. Never quotes the token, the address or a raw error message.
public func connectionReport(_ check: ConnectionCheck, nowMs: Int64, thresholds: Thresholds) -> String {
    switch check {
    case .connected(nil):
        return "Connected, but Nightscout has no glucose readings to show yet."
    case .connected(let reading?):
        let status = classify(reading, nowMs: nowMs, thresholds: thresholds)
        let ageMs = status.ageMs ?? 0
        if status.level == .stale && ageMs < 0 {
            return "Connected, but the newest reading is dated in the future. "
                + "Check the clock on the phone that uploads to Nightscout."
        }
        if status.level == .stale {
            return "Connected, but the newest reading came in \(elapsedWords(ageMs)), "
                + "so the display shows STALE until a new one arrives."
        }
        return "Connected. The newest reading came in \(spokenAge(status.ageMinutes ?? 0))."
    case .needsToken:
        return "This Nightscout needs a token to be read. Add a token with the readable role, "
            + "made in this site's Admin Tools."
    case .failed(.tokenRejected):
        return "Nightscout refused the token. Use a token with the readable role, "
            + "made in this site's Admin Tools."
    case .failed(.unreachable):
        return "Could not reach the site. Check the address and the phone's connection; "
            + "if both are right, the site may be down."
    case .failed(.notNightscout):
        return "The site answered, but not the way Nightscout does. Check the address."
    case .failed(.badURL):
        return "That address cannot be used. Check it for typos."
    }
}

/// A non-negative age in whole minutes, hours past two hours, days past two days.
func elapsedWords(_ ageMs: Int64) -> String {
    let minutes = Int(ageMs / 60_000)
    if minutes < 120 { return spokenAge(minutes) }
    let hours = minutes / 60
    if hours < 48 { return "\(hours) hours ago" }
    return "\(hours / 24) days ago"
}
