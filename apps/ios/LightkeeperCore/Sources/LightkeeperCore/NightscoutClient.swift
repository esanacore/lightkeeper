// Read-only Nightscout client. Ships on Apple platforms; also builds with the
// Linux and Windows Swift toolchains so the package tests run anywhere.
//
// Same contract as the Python client: HTTPS only, a readable-role token sent
// in the `api-secret` header and never in a URL (ADR-0009), GET on the sgv
// entries endpoint only, a bounded count, a response size cap, and no
// redirects that change scheme or host (a downgrade to http would send the
// token in the clear).

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum NightscoutError: Error, Equatable {
    case badURL(String)
    case unreachable(String)
    case notJSON
    case notAList
    case tooLarge
    case httpStatus(Int)
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
    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout * 2
        config.urlCache = nil
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    /// `token` must have the readable role only. `allowHTTP` exists for localhost tests.
    public init(baseURL: String, token: String?, timeout: TimeInterval = defaultTimeout,
                allowHTTP: Bool = false) throws {
        guard let url = URL(string: baseURL), let scheme = url.scheme?.lowercased(),
              let host = url.host, !host.isEmpty else {
            throw NightscoutError.badURL("base URL must be a full URL like https://my-nightscout.example")
        }
        guard scheme == "https" || (scheme == "http" && allowHTTP) else {
            throw NightscoutError.badURL("base URL must use https")
        }
        guard url.query == nil, url.fragment == nil, url.user == nil, url.password == nil else {
            throw NightscoutError.badURL("base URL must be just the site, with no query, fragment, or login")
        }
        self.baseURL = url
        self.token = token
        self.timeout = timeout
        super.init()
    }

    /// The entries URL. It never carries the token, so the token stays out of
    /// proxy and hosting access logs (ADR-0009).
    func entriesURL(count: Int) -> URL {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/entries/sgv.json"),
                                       resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "count", value: String(count))]
        return components.url!
    }

    /// The GET request for the newest `count` entries, token in the header.
    func entriesRequest(count: Int) -> URLRequest {
        var request = URLRequest(url: entriesURL(count: count))
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token, !token.isEmpty { request.setValue(token, forHTTPHeaderField: Self.tokenHeader) }
        return request
    }

    /// Never let the token escape in an error message.
    func redact(_ text: String) -> String {
        guard let token, !token.isEmpty else { return text }
        return text.replacingOccurrences(of: token, with: "***")
    }

    /// Return the newest `count` raw entries as parsed JSON (an array of dictionaries).
    public func fetchEntries(count: Int = 12) async throws -> [Any] {
        precondition((1...288).contains(count), "count must be between 1 and 288")
        let request = entriesRequest(count: count)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw NightscoutError.unreachable(redact(error.localizedDescription))
        }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NightscoutError.httpStatus(http.statusCode)
        }
        guard data.count <= Self.maxResponseBytes else { throw NightscoutError.tooLarge }
        guard let json = try? JSONSerialization.jsonObject(with: data) else { throw NightscoutError.notJSON }
        guard let list = json as? [Any] else { throw NightscoutError.notAList }
        return list
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
