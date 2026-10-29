package com.esanacore.lightkeeper

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject

/**
 * The shared vectors, read from the test APK's assets. The copySpecVectors
 * Gradle task copies them there from the repository's spec/ folder at build
 * time, so these tests always run the checked-in vectors.
 */
object Spec {
    /** 2026-10-18T12:00:00Z, the instant every vector's ages count back from. */
    const val NOW_MS = 1_792_324_800_000L

    fun load(name: String): JSONObject {
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val text = assets.open("spec/$name").use { it.readBytes().toString(Charsets.UTF_8) }
        return JSONObject(text)
    }

    fun cases(name: String): List<JSONObject> {
        val cases = load(name).getJSONArray("cases")
        return List(cases.length()) { cases.getJSONObject(it) }
    }

    fun strings(array: JSONArray): List<String> = List(array.length()) { array.getString(it) }

    /** An item's age in milliseconds, from `minutes_ago` or `seconds_ago`. */
    fun ageMs(item: JSONObject): Long =
        if (item.has("seconds_ago")) {
            item.getLong("seconds_ago") * 1000
        } else {
            item.getLong("minutes_ago") * 60_000
        }

    /**
     * A display vector's entries as a raw Nightscout response body, each
     * dated its age before [NOW_MS], exactly as the Python suite builds them.
     * A null entry is left out.
     */
    fun body(case: JSONObject): ByteArray {
        val items =
            if (case.has("entries")) {
                val list = case.getJSONArray("entries")
                List(list.length()) { list.getJSONObject(it) }
            } else {
                listOf(case)
            }
        val entries = JSONArray()
        for (item in items) {
            if (item.isNull("entry")) continue
            val entry = JSONObject(item.getJSONObject("entry").toString())
            entry.put("date", NOW_MS - ageMs(item))
            entries.put(entry)
        }
        return entries.toString().toByteArray(Charsets.UTF_8)
    }

    /** A display vector's thresholds, or the defaults. */
    fun thresholds(case: JSONObject): Thresholds {
        if (!case.has("thresholds")) return Thresholds()
        val t = case.getJSONObject("thresholds")
        return Thresholds(
            urgentLow = t.getInt("urgent_low"),
            low = t.getInt("low"),
            high = t.getInt("high"),
            urgentHigh = t.getInt("urgent_high"),
            staleAfterMs = t.getLong("stale_after_minutes") * 60_000,
        )
    }

    /** True when the case's fetch failed (its `error` is not null). */
    fun fetchError(case: JSONObject): Boolean = !case.isNull("error")
}
