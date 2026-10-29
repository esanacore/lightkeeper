package com.esanacore.lightkeeper

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URISyntaxException
import java.net.URLConnection
import javax.net.ssl.HttpsURLConnection

/**
 * Read-only Nightscout client: one GET for the newest sgv entries, made fresh
 * for every fetch and closed when it ends.
 *
 * The same contract as the Python and iOS clients: HTTPS only (the address is
 * a checked [SiteAddress], and cleartext is off for the whole app in
 * network_security_config.xml); a readable-role token sent in the
 * `api-secret` header and never in a URL (ADR-0009); timeouts on connecting
 * and reading; a response size cap. It is stricter about redirects than
 * either: it follows none, and any redirect is a failed fetch, so the token
 * can never be carried to another address. Nothing here logs, and no error
 * message quotes the token, the address or a platform message.
 *
 * [open] makes the connection; tests pass a fake one.
 */
class NightscoutClient(
    private val site: SiteAddress,
    private val token: String?,
    private val timeoutMs: Int = TIMEOUT_MS,
    private val open: (String) -> URLConnection = { URI(it).toURL().openConnection() },
) {
    /** What went wrong, in the terms a person can act on. */
    enum class Failure {
        /** No answer: no network, a name that does not resolve, a timeout, TLS, or a 5xx. */
        UNREACHABLE,

        /** Nightscout refused the token (HTTP 401 or 403). */
        TOKEN_REJECTED,

        /** The site refused to be read (HTTP 401 or 403) and no token was sent. */
        NEEDS_TOKEN,

        /** The site answered with a redirect, which is never followed. */
        REDIRECTED,

        /** The site answered, but not with an entries body: another status, or too large. */
        NOT_NIGHTSCOUT,
    }

    /** A failed fetch. The message is fixed text: never the token, the address or a raw error. */
    class FetchException(val failure: Failure) : IOException("Nightscout fetch failed: $failure")

    /** True when requests carry the token header: a token was given and it is not empty. */
    val sendsToken: Boolean
        get() = !token.isNullOrEmpty()

    /**
     * The raw body of the newest [count] sgv entries. Blocking: call it off
     * the main thread. Throws [FetchException] for every failure.
     */
    fun fetchEntries(count: Int = DEFAULT_COUNT): ByteArray {
        require(count in 1..MAX_COUNT) { "count must be between 1 and $MAX_COUNT" }
        val connection =
            try {
                open(site.entriesUrl(count))
            } catch (_: IOException) {
                throw FetchException(Failure.UNREACHABLE)
            } catch (_: IllegalArgumentException) {
                // URI and URL refuse nothing a checked SiteAddress builds; were
                // they to, it is a failed fetch like any other.
                throw FetchException(Failure.NOT_NIGHTSCOUT)
            } catch (_: URISyntaxException) {
                throw FetchException(Failure.NOT_NIGHTSCOUT)
            }
        try {
            // The address is https by construction; anything else is refused
            // before a byte is sent.
            if (connection !is HttpsURLConnection) throw FetchException(Failure.NOT_NIGHTSCOUT)
            prepare(connection)
            val status =
                try {
                    connection.responseCode
                } catch (_: IOException) {
                    throw FetchException(Failure.UNREACHABLE)
                }
            failureFor(status)?.let { throw FetchException(it) }
            return readBody(connection)
        } finally {
            if (connection is HttpURLConnection) connection.disconnect()
        }
    }

    /** Sets up the GET: no redirects, no cache, timeouts, and the token in its header. */
    private fun prepare(connection: HttpsURLConnection) {
        connection.requestMethod = "GET"
        connection.instanceFollowRedirects = false
        connection.useCaches = false
        connection.connectTimeout = timeoutMs
        connection.readTimeout = timeoutMs
        connection.setRequestProperty("Accept", "application/json")
        token?.takeIf { it.isNotEmpty() }?.let { connection.setRequestProperty(TOKEN_HEADER, it) }
    }

    /** The failure an HTTP status means, or null for a 2xx. */
    internal fun failureFor(status: Int): Failure? =
        when (status) {
            in 200..299 -> null
            in 300..399 -> Failure.REDIRECTED
            401, 403 -> if (sendsToken) Failure.TOKEN_REJECTED else Failure.NEEDS_TOKEN
            in 500..599 -> Failure.UNREACHABLE
            else -> Failure.NOT_NIGHTSCOUT
        }

    /** The body, refused once it passes [MAX_RESPONSE_BYTES]. */
    private fun readBody(connection: HttpsURLConnection): ByteArray {
        try {
            connection.inputStream.use { input ->
                val out = ByteArrayOutputStream()
                val buffer = ByteArray(BUFFER_BYTES)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    out.write(buffer, 0, read)
                    if (out.size() > MAX_RESPONSE_BYTES) {
                        throw FetchException(Failure.NOT_NIGHTSCOUT)
                    }
                }
                return out.toByteArray()
            }
        } catch (failed: FetchException) {
            throw failed
        } catch (_: IOException) {
            throw FetchException(Failure.UNREACHABLE)
        }
    }

    companion object {
        /**
         * Nightscout's v1 API reads an access token from this header as well
         * as from `?token=`; a plaintext API_SECRET here does not match (ADR-0009).
         */
        const val TOKEN_HEADER = "api-secret"

        /** Seconds, as the Python and iOS clients use, in milliseconds. */
        const val TIMEOUT_MS = 10_000

        /** 288 entries of about 200 bytes is about 60 KB; near a megabyte is not Nightscout. */
        const val MAX_RESPONSE_BYTES = 1_000_000

        /** An hour of 5-minute readings, as every client asks for. */
        const val DEFAULT_COUNT = 12

        private const val MAX_COUNT = 288
        private const val BUFFER_BYTES = 8192
    }
}
