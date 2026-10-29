package com.esanacore.lightkeeper

/**
 * The firmware's C++ rules, JSON reader and panel rasterizer
 * (firmware/xteink/lib), reached through src/main/cpp/jni_bridge.cpp.
 *
 * Every line the app shows and every panel pixel it draws comes from here,
 * the same code the bedside device runs; the instrumented tests run every
 * case in spec/display_vectors.json and spec/panel_vectors.json through it.
 */
object NativeRules : Rules {
    init {
        System.loadLibrary("lightkeeper")
    }

    /** nativeReadBody's slots, in jni_bridge.cpp's BodyField order. */
    private const val STATUS = 0
    private const val FOUND = 1
    private const val MGDL = 2
    private const val TIMESTAMP = 3
    private const val TREND = 4
    private const val FIELD_COUNT = 6

    /** lk::JsonStatus::Ok: the body was a JSON list. */
    private const val STATUS_OK = 0L

    override fun readBody(body: ByteArray): BodyReading {
        val fields = nativeReadBody(body)
        if (fields == null || fields.size != FIELD_COUNT || fields[STATUS] != STATUS_OK) {
            return BodyReading(isList = false, reading = null)
        }
        val reading =
            if (fields[FOUND] == 1L) {
                Reading(fields[MGDL].toInt(), fields[TIMESTAMP], fields[TREND].toInt())
            } else {
                null
            }
        return BodyReading(isList = true, reading = reading)
    }

    override fun lines(
        reading: Reading?,
        nowMs: Long,
        thresholds: Thresholds,
        fetchError: Boolean,
    ): List<String> {
        val lines =
            nativeRenderLines(
                reading != null,
                reading?.mgdl ?: 0,
                reading?.timestampMs ?: 0L,
                reading?.trendCode ?: 0,
                nowMs,
                thresholds.staleAfterMs,
                thresholds.urgentLow,
                thresholds.low,
                thresholds.high,
                thresholds.urgentHigh,
                fetchError,
            )
        // Only an allocation failure in the bridge returns null; there are no
        // lines to show then, and the most cautious screen has none of the
        // reading in it.
        return lines?.toList() ?: listOf(NO_DATA_HEADLINE)
    }

    /**
     * The 1-bit panel image for [lines] on a [width] x [height] panel, as
     * packed rows (1 = ink, leftmost pixel in the most significant bit), or
     * null when the rasterizer refuses: then nothing is drawn, never the
     * previous image. [stamp] is null or a 24-hour "HH:MM".
     */
    fun panel(lines: List<String>, width: Int, height: Int, stamp: String?): ByteArray? =
        nativeRenderPanel(lines.toTypedArray(), width, height, stamp)

    private const val NO_DATA_HEADLINE = "NO DATA"

    @JvmStatic private external fun nativeReadBody(body: ByteArray): LongArray?

    @JvmStatic
    private external fun nativeRenderLines(
        hasReading: Boolean,
        mgdl: Int,
        timestampMs: Long,
        trend: Int,
        nowMs: Long,
        staleAfterMs: Long,
        urgentLow: Int,
        low: Int,
        high: Int,
        urgentHigh: Int,
        fetchError: Boolean,
    ): Array<String>?

    @JvmStatic
    private external fun nativeRenderPanel(
        lines: Array<String>,
        width: Int,
        height: Int,
        stamp: String?,
    ): ByteArray?
}
