package com.esanacore.lightkeeper

/**
 * The Nightscout address and the display thresholds. The token is not here:
 * it lives encrypted in [TokenStore].
 *
 * The rules match the other ports (`Thresholds` in
 * src/lightkeeper/domain/status.py and Status.swift: 40 <= urgent low < low
 * < high < urgent high <= 400, and a stale limit above zero) and the iOS
 * settings screen (the stepper ranges, the steps, the caution above 15
 * minutes, word for word). The settings screen refuses to save an invalid
 * set, and [restore] resets one it finds on disk, so the display never runs
 * on numbers other than the ones the settings screen shows (HAZ-006).
 */
data class Settings(
    val nightscoutUrl: String = "",
    val urgentLow: Int = 55,
    val low: Int = 70,
    val high: Int = 180,
    val urgentHigh: Int = 250,
    val staleMinutes: Int = 15,
) {
    /** Why the thresholds are not a valid set, in plain words, or null when they are. */
    val validationMessage: String?
        get() =
            when {
                !(40 <= urgentLow && urgentLow < low && low < high && high < urgentHigh &&
                    urgentHigh <= 400) -> OUT_OF_ORDER
                staleMinutes <= 0 -> STALE_NOT_POSITIVE
                else -> null
            }

    val isValid: Boolean
        get() = validationMessage == null

    /**
     * The thresholds the rules run on. Only a valid set reaches the screen
     * (save refuses an invalid one and [restore] resets one), so the
     * defaults here are for a set that should never exist.
     */
    val thresholds: Thresholds
        get() =
            if (isValid) {
                Thresholds(urgentLow, low, high, urgentHigh, staleMinutes * MINUTE_MS)
            } else {
                Thresholds()
            }

    /** Why the address cannot be used, or null when it can or is not entered yet. */
    val urlProblem: String?
        get() = if (nightscoutUrl.isEmpty()) null else SiteAddress.problem(nightscoutUrl)

    /** True once a usable address is set: the only state in which the app fetches. */
    val isConfigured: Boolean
        get() = nightscoutUrl.isNotEmpty() && urlProblem == null

    /** The site to fetch from, or null when not configured. */
    val site: SiteAddress?
        get() = if (nightscoutUrl.isEmpty()) null else SiteAddress.parse(nightscoutUrl)

    /** Save is allowed only for valid thresholds and an address that is usable or empty. */
    val canSave: Boolean
        get() = isValid && urlProblem == null

    /** A caution for a long stale limit, or null at 15 minutes or less. */
    val staleCaution: String?
        get() = if (staleMinutes > STALE_CAUTION_ABOVE) STALE_CAUTION else null

    /** These settings with the default thresholds and stale limit, and the same address. */
    fun resettingThresholds(): Settings = Settings(nightscoutUrl = nightscoutUrl)

    /** The values to persist, by key. */
    fun toStored(): Map<String, Any> =
        mapOf(
            KEY_URL to nightscoutUrl,
            KEY_URGENT_LOW to urgentLow,
            KEY_LOW to low,
            KEY_HIGH to high,
            KEY_URGENT_HIGH to urgentHigh,
            KEY_STALE_MINUTES to staleMinutes,
        )

    /** What [restore] found: the settings to run on, and whether they must be written back. */
    data class Restored(val settings: Settings, val wasReset: Boolean)

    companion object {
        const val OUT_OF_ORDER = "Thresholds must increase: urgent low < low < high < urgent high."
        const val STALE_NOT_POSITIVE = "Stale limit must be at least one minute."
        const val STALE_CAUTION =
            "Above 15 minutes, an old reading keeps looking current for longer before " +
                "this display says STALE. The primary CGM app's signal-loss alert is the one to " +
                "rely on."

        /** The thresholds step this far, in mg/dL, on the settings screen. */
        const val THRESHOLD_STEP = 5

        /** Stale after steps one minute at a time. */
        const val STALE_STEP = 1

        /**
         * The settings screen's stepper bounds, in mg/dL, as on iOS. Each
         * starts on the 5 mg/dL grid the defaults sit on, so a step never
         * lands on an odd value at a bound. [validationMessage] still decides
         * which sets are valid.
         */
        val URGENT_LOW_RANGE = 40..100
        val LOW_RANGE = 45..150
        val HIGH_RANGE = 100..350
        val URGENT_HIGH_RANGE = 105..400

        /**
         * Stale after, in minutes: never below one reading interval plus a
         * minute, and never above an hour (D16 decides whether to lower it).
         */
        val STALE_RANGE = 6..60

        /** Above this many minutes the settings screen shows [STALE_CAUTION]. */
        const val STALE_CAUTION_ABOVE = 15

        const val KEY_URL = "nightscoutURL"
        const val KEY_URGENT_LOW = "urgentLow"
        const val KEY_LOW = "low"
        const val KEY_HIGH = "high"
        const val KEY_URGENT_HIGH = "urgentHigh"
        const val KEY_STALE_MINUTES = "staleMinutes"

        private const val MINUTE_MS = 60_000L

        /** [value] moved by [delta] and kept inside [range]: one stepper press. */
        fun step(value: Int, delta: Int, range: IntRange): Int = (value + delta).coerceIn(range)

        /**
         * The settings stored under each key. A missing or mistyped value
         * takes its default; an invalid threshold set is reset to the
         * defaults and must be written back, so the screen and the rules
         * agree. The stored address is kept even when the app cannot use it,
         * for the settings screen to explain.
         */
        fun restore(stored: Map<String, *>): Restored {
            val defaults = Settings()
            fun int(key: String, default: Int): Int = stored[key] as? Int ?: default
            val found =
                Settings(
                    nightscoutUrl = stored[KEY_URL] as? String ?: defaults.nightscoutUrl,
                    urgentLow = int(KEY_URGENT_LOW, defaults.urgentLow),
                    low = int(KEY_LOW, defaults.low),
                    high = int(KEY_HIGH, defaults.high),
                    urgentHigh = int(KEY_URGENT_HIGH, defaults.urgentHigh),
                    staleMinutes = int(KEY_STALE_MINUTES, defaults.staleMinutes),
                )
            return if (found.isValid) {
                Restored(found, wasReset = false)
            } else {
                Restored(found.resettingThresholds(), wasReset = true)
            }
        }
    }
}
