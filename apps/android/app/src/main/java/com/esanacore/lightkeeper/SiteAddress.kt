package com.esanacore.lightkeeper

import java.net.URI
import java.net.URISyntaxException
import java.util.Locale

/**
 * A Nightscout site address the app can use: https, a host name, an optional
 * port, and nothing else.
 *
 * The check and its plain-words reasons mirror the iOS app's
 * (`NightscoutClient.init` and `isSiteName` in
 * apps/ios/LightkeeperCore/Sources/LightkeeperCore/NightscoutClient.swift),
 * step for step and word for word, so a pasted entries path or a `?token=`
 * link is refused with the same reason on both phones. Where java.net.URI and
 * Foundation's URL parse an odd address differently (a percent sign or a
 * non-ASCII letter in the host), this refuses, never the other way round.
 */
class SiteAddress private constructor(private val origin: String) {
    /** The URL of the newest [count] sgv entries. It never carries the token (ADR-0009). */
    fun entriesUrl(count: Int): String = "$origin/api/v1/entries/sgv.json?count=$count"

    override fun toString(): String = origin

    /** The outcome of checking an address: a usable site, or the reason it is not. */
    sealed interface Check {
        data class Usable(val site: SiteAddress) : Check

        data class Unusable(val reason: String) : Check
    }

    companion object {
        const val SPACE = "The address has a space in it. Remove the space."
        const val FULL_ADDRESS =
            "Enter the full address, starting with https://, like https://my-nightscout.example"
        const val HTTPS_ONLY =
            "The address must start with https://, so glucose data and the token are never " +
                "sent in the clear."
        const val NO_EXTRAS = "Enter just the site, with no ?, # or login in the address."
        const val NO_PATH =
            "Enter just the site, with nothing after its name, like https://my-nightscout.example"
        const val SITE_NAME =
            "The site name can only have letters, digits, hyphens, and single dots between its " +
                "parts. Check it for typos."

        private const val MAX_PORT = 65535

        /** Checks [address] exactly as typed (the settings screen trims it first). */
        fun check(address: String): Check {
            if (address.any { it.isWhitespace() }) return Check.Unusable(SPACE)
            val uri =
                try {
                    URI(address)
                } catch (_: URISyntaxException) {
                    return Check.Unusable(FULL_ADDRESS)
                }
            val scheme = uri.scheme?.lowercase(Locale.ROOT)
            val authority = uri.rawAuthority
            if (scheme == null || authority.isNullOrEmpty()) return Check.Unusable(FULL_ADDRESS)
            val at = authority.lastIndexOf('@')
            val hostAndPort = splitHostAndPort(authority.substring(at + 1))
            if (hostAndPort == null || hostAndPort.first.isEmpty()) {
                return Check.Unusable(FULL_ADDRESS)
            }
            if (scheme != "https") return Check.Unusable(HTTPS_ONLY)
            if (uri.rawQuery != null || uri.rawFragment != null || at >= 0) {
                return Check.Unusable(NO_EXTRAS)
            }
            val path = uri.rawPath.orEmpty()
            if (path.isNotEmpty() && path != "/") return Check.Unusable(NO_PATH)
            val (host, port) = hostAndPort
            if (!isSiteName(host)) return Check.Unusable(SITE_NAME)
            val origin = if (port.isEmpty()) "https://$host" else "https://$host:$port"
            return Check.Usable(SiteAddress(origin))
        }

        /** Why [address] cannot be used, in plain words, or null when it can. */
        fun problem(address: String): String? = (check(address) as? Check.Unusable)?.reason

        /** The usable site for [address], or null. */
        fun parse(address: String): SiteAddress? = (check(address) as? Check.Usable)?.site

        /**
         * True for dot-separated labels of ASCII letters, digits and inner
         * hyphens (with an optional final dot), or an IPv6 literal.
         */
        fun isSiteName(host: String): Boolean {
            var name = host
            if (name.startsWith("[") && name.endsWith("]") && name.length >= 2) {
                name = name.substring(1, name.length - 1)
            }
            if (name.contains(':')) {
                return name.all { it.isAsciiHexDigit() || it == ':' || it == '.' }
            }
            val labels = name.split('.').toMutableList()
            if (labels.size > 1 && labels.last().isEmpty()) labels.removeAt(labels.size - 1)
            return labels.all { label ->
                label.length in 1..63 &&
                    !label.startsWith("-") &&
                    !label.endsWith("-") &&
                    label.all { it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' || it == '-' }
            }
        }

        /**
         * Splits an authority (no login) into its host and port text, or
         * returns null when the port is not a number up to 65535 or the host
         * holds a colon outside IPv6 brackets. An empty port ("site:") is no
         * port, as Foundation reads it.
         */
        private fun splitHostAndPort(text: String): Pair<String, String>? {
            val host: String
            val rest: String
            if (text.startsWith("[")) {
                val close = text.indexOf(']')
                if (close < 0) return null
                host = text.substring(0, close + 1)
                rest = text.substring(close + 1)
                if (rest.isNotEmpty() && !rest.startsWith(":")) return null
            } else {
                val colon = text.indexOf(':')
                if (colon >= 0 && text.indexOf(':', colon + 1) >= 0) return null
                host = if (colon < 0) text else text.substring(0, colon)
                rest = if (colon < 0) "" else text.substring(colon)
            }
            val port = rest.removePrefix(":")
            val numeric = port.length <= 5 && port.all { it in '0'..'9' }
            if (port.isNotEmpty() && (!numeric || port.toInt() > MAX_PORT)) return null
            return host to port
        }

        private fun Char.isAsciiHexDigit(): Boolean =
            this in '0'..'9' || this in 'a'..'f' || this in 'A'..'F'
    }
}
