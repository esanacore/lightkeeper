package com.esanacore.lightkeeper

/**
 * One trustworthy reading, as the firmware's parser returned it.
 *
 * The app never builds one from anything else: it holds the reading only to
 * hand it back to [Rules.lines], which checks it again before classifying it.
 * [trendCode] is opaque here; only the native rules read it.
 */
data class Reading(val mgdl: Int, val timestampMs: Long, val trendCode: Int)

/**
 * What a Nightscout entries body held. [isList] is false when the body was
 * not a JSON list at all (an error page, an error object, garbage), which the
 * app treats as a failed fetch. [reading] is the newest trustworthy reading,
 * or null when the list held none.
 */
data class BodyReading(val isList: Boolean, val reading: Reading?)

/**
 * The display thresholds in mg/dL and the stale limit, as every port takes
 * them. [Settings] builds these only from a valid set; the native rules
 * classify an invalid set as NO DATA anyway.
 */
data class Thresholds(
    val urgentLow: Int = 55,
    val low: Int = 70,
    val high: Int = 180,
    val urgentHigh: Int = 250,
    val staleAfterMs: Long = 15L * 60 * 1000,
)

/**
 * The display rules: in the app, the firmware's C++ through JNI
 * ([NativeRules]), so there is no separate Kotlin implementation of them.
 * The JVM tests pass a recorder in their place to check what the model asks.
 */
interface Rules {
    /** The newest trustworthy reading in a raw Nightscout entries body. */
    fun readBody(body: ByteArray): BodyReading

    /**
     * The exact display lines for [reading] (null: no reading) at [nowMs],
     * judged against [thresholds]. [fetchError] is true when the latest fetch
     * failed, which adds "Nightscout unreachable".
     */
    fun lines(
        reading: Reading?,
        nowMs: Long,
        thresholds: Thresholds,
        fetchError: Boolean,
    ): List<String>
}
