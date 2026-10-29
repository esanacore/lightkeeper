package com.esanacore.lightkeeper

import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/**
 * The glance's captions and the panel stamp, as absolute local times: nothing
 * on screen counts seconds, so nothing has to tick once a second to stay
 * true. The same words as the iOS app (Presentation.swift).
 */
object Captions {
    /** Shown before the first answer. Static: no spinner, no animation, no ticking. */
    const val CHECKING = "checking Nightscout..."

    /** "HH:MM", 24-hour, in [zone]. Also the panel stamp the rasterizer accepts. */
    fun clockText(ms: Long, zone: ZoneId = ZoneId.systemDefault()): String {
        val time = Instant.ofEpochMilli(ms).atZone(zone)
        return String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)
    }

    /** "checked HH:MM": when the app last heard back from Nightscout. */
    fun checked(ms: Long, zone: ZoneId = ZoneId.systemDefault()): String =
        "checked ${clockText(ms, zone)}"

    /** "Nightscout unreachable since HH:MM": the first failed fetch of the current outage. */
    fun offlineSince(ms: Long, zone: ZoneId = ZoneId.systemDefault()): String =
        "Nightscout unreachable since ${clockText(ms, zone)}"

    /** The first caption line: [CHECKING] until a fetch has answered, then [checked]. */
    fun status(lastRefreshMs: Long?, zone: ZoneId = ZoneId.systemDefault()): String =
        lastRefreshMs?.let { checked(it, zone) } ?: CHECKING
}
