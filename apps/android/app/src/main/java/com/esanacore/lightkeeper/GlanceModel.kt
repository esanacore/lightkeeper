package com.esanacore.lightkeeper

/**
 * Everything the glance shows, from one place.
 *
 * [lines] are exactly what the rules rendered: the status area, the panel
 * and the accessibility description are all drawn from them. [drawnAtMs] is
 * when they were rendered (the panel's stamp); [lastRefreshMs] when the app
 * last heard back from a fetch; [offlineSinceMs] the first failed fetch of the
 * current outage, cleared by the next good one.
 */
data class GlanceState(
    val configured: Boolean,
    val lines: List<String>,
    val fetchError: Boolean,
    val drawnAtMs: Long,
    val lastRefreshMs: Long?,
    val offlineSinceMs: Long?,
)

/**
 * The app's single source of truth: keeps the last good reading, so a
 * Nightscout outage ages into STALE instead of freezing, and re-ages it
 * against the clock without a fetch whenever asked. Main thread only; the
 * fetch itself runs elsewhere and comes back through [finishFetch].
 *
 * Mirrors the iOS GlucoseModel: a fetch that finds a list replaces the last
 * good reading (with nothing, if the list held no trustworthy reading, which
 * shows NO DATA); a failed fetch, or a body that is not a list, keeps it and
 * re-ages it with "Nightscout unreachable". Fetches are numbered as they
 * start, and an answer is applied only when no later fetch has been applied
 * and the site has not changed meanwhile.
 */
class GlanceModel(
    settings: Settings,
    private val rules: Rules,
    private val now: () -> Long,
) {
    /** One fetch in flight: its number, and the settings it was asked with. */
    class Ticket internal constructor(val number: Int, val settings: Settings)

    var settings: Settings = settings
        private set

    var state: GlanceState
        private set

    private var lastGood: Reading? = null
    private var fetchError = false
    private var lastRefreshMs: Long? = null
    private var offlineSinceMs: Long? = null
    private var fetchesStarted = 0
    private var newestApplied = 0

    init {
        state = render(now())
    }

    /**
     * Switches to [updated] settings. Another site's last reading must never
     * age on this site's screen, so a new address forgets everything;
     * otherwise the last reading is re-aged against the new thresholds.
     */
    fun updateSettings(updated: Settings) {
        val siteChanged = updated.nightscoutUrl != settings.nightscoutUrl
        settings = updated
        if (siteChanged) forget() else reage()
    }

    /**
     * Re-runs the rules on the last good reading at the current time, with
     * no network round trip. Called on a timer and whenever the screen comes
     * back, so the screen turns STALE on time even when fetches stop
     * (HAZ-008).
     */
    fun reage() {
        state = render(now())
    }

    /**
     * Starts a fetch, or returns null when no usable address is set: then
     * there is nothing to ask, the screen is the setup card, and a failed
     * fetch would only read as an outage.
     */
    fun startFetch(): Ticket? {
        if (!settings.isConfigured) {
            forget()
            return null
        }
        fetchesStarted += 1
        return Ticket(fetchesStarted, settings)
    }

    /** Applies a fetch's answer: the raw body, or null when the fetch failed. */
    fun finishFetch(ticket: Ticket, body: ByteArray?) {
        // The site changed while this fetch ran: its answer belongs to the old site.
        if (ticket.settings.nightscoutUrl != settings.nightscoutUrl) return
        // A fetch that started later has already answered: this one is older news.
        if (ticket.number <= newestApplied) return
        newestApplied = ticket.number

        val nowMs = now()
        val read = body?.let(rules::readBody)
        if (read == null || !read.isList) {
            fetchError = true
            if (offlineSinceMs == null) offlineSinceMs = nowMs
        } else {
            lastGood = read.reading
            fetchError = false
            offlineSinceMs = null
        }
        lastRefreshMs = nowMs
        state = render(nowMs)
    }

    /** Drops everything learned from the current site: back to the first-launch screen. */
    private fun forget() {
        lastGood = null
        fetchError = false
        lastRefreshMs = null
        offlineSinceMs = null
        state = render(now())
    }

    private fun render(nowMs: Long): GlanceState =
        GlanceState(
            configured = settings.isConfigured,
            lines = rules.lines(lastGood, nowMs, settings.thresholds, fetchError),
            fetchError = fetchError,
            drawnAtMs = nowMs,
            lastRefreshMs = lastRefreshMs,
            offlineSinceMs = offlineSinceMs,
        )
}
