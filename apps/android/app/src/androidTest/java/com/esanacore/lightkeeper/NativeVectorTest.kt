package com.esanacore.lightkeeper

import java.util.zip.CRC32
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The firmware's C++, built into the app and reached through JNI, gives
 * exactly what the shared vectors pin: every display vector's lines, every
 * response vector's reading, and every panel vector's pixels. These run on
 * the device's own ABI, so the phone shows what the Python reference, the
 * firmware and the iOS app show.
 */
class NativeVectorTest {
    /** lk::Trend's order, which jni_bridge.cpp uses for its trend codes. */
    private val trendNames =
        listOf(
            "DoubleUp",
            "SingleUp",
            "FortyFiveUp",
            "Flat",
            "FortyFiveDown",
            "SingleDown",
            "DoubleDown",
            "Unknown",
        )

    @Test
    fun testTheVectorsAreTheVersionThisSuiteWasWrittenFor() {
        assertEquals(1, Spec.load("display_vectors.json").getInt("spec_version"))
        assertEquals(1, Spec.load("response_vectors.json").getInt("spec_version"))
        assertEquals(1, Spec.load("panel_vectors.json").getInt("panel_spec_version"))
    }

    @Test
    fun testEveryDisplayVectorGivesItsExactLinesThroughJni() {
        val cases = Spec.cases("display_vectors.json")
        assertTrue("the vectors were copied into the test assets", cases.size >= 39)
        for (case in cases) {
            val name = case.getString("name")
            // The app's own path: the body through the firmware's parser,
            // then the reading through classify and render.
            val read = NativeRules.readBody(Spec.body(case))
            assertTrue(name, read.isList)
            val thresholds = Spec.thresholds(case)
            val error = Spec.fetchError(case)
            val lines = NativeRules.lines(read.reading, Spec.NOW_MS, thresholds, error)
            assertEquals(name, Spec.strings(case.getJSONArray("lines")), lines)
        }
    }

    @Test
    fun testEveryResponseVectorGivesItsReadingThroughJni() {
        for (case in Spec.cases("response_vectors.json")) {
            val name = case.getString("name")
            val read = NativeRules.readBody(case.getString("body").toByteArray(Charsets.UTF_8))
            when {
                case.isNull("expect") -> {
                    assertTrue(name, read.isList)
                    assertNull(name, read.reading)
                }
                case.optString("expect") == "error" -> assertFalse(name, read.isList)
                else -> {
                    val expect = case.getJSONObject("expect")
                    val reading = read.reading!!
                    assertTrue(name, read.isList)
                    assertEquals(name, expect.getInt("mgdl"), reading.mgdl)
                    assertEquals(name, expect.getLong("date"), reading.timestampMs)
                    assertEquals(name, expect.getString("trend"), trendNames[reading.trendCode])
                }
            }
        }
    }

    @Test
    fun testNoReadingIsNoDataWithOrWithoutAFetchError() {
        assertEquals(
            listOf("NO DATA", "Check sensor and phone", "Confirm on primary device"),
            NativeRules.lines(null, Spec.NOW_MS, Thresholds(), fetchError = false),
        )
        assertEquals(
            listOf(
                "NO DATA",
                "Check sensor and phone",
                "Confirm on primary device",
                "Nightscout unreachable",
            ),
            NativeRules.lines(null, Spec.NOW_MS, Thresholds(), fetchError = true),
        )
    }

    @Test
    fun testAReadingTheParserWouldRefuseShowsNoData() {
        val noData = NativeRules.lines(null, Spec.NOW_MS, Thresholds(), fetchError = false)
        val outOfRange = Reading(mgdl = 5000, timestampMs = Spec.NOW_MS, trendCode = 3)
        assertEquals(noData, NativeRules.lines(outOfRange, Spec.NOW_MS, Thresholds(), false))
        val secondsNotMs = Reading(mgdl = 120, timestampMs = Spec.NOW_MS / 1000, trendCode = 3)
        assertEquals(noData, NativeRules.lines(secondsNotMs, Spec.NOW_MS, Thresholds(), false))
        // An unknown trend code is drawn as "?", never as another arrow.
        val oddTrend = Reading(mgdl = 120, timestampMs = Spec.NOW_MS, trendCode = 99)
        val value = NativeRules.lines(oddTrend, Spec.NOW_MS, Thresholds(), false)[1]
        assertEquals("120 mg/dL ?", value)
    }

    @Test
    fun testInvalidThresholdsShowNoData() {
        val reading = Reading(mgdl = 120, timestampMs = Spec.NOW_MS, trendCode = 3)
        val inverted = Thresholds(urgentLow = 55, low = 200, high = 180, urgentHigh = 250)
        assertEquals("NO DATA", NativeRules.lines(reading, Spec.NOW_MS, inverted, false)[0])
        val noStale = Thresholds(staleAfterMs = 0)
        assertEquals("NO DATA", NativeRules.lines(reading, Spec.NOW_MS, noStale, false)[0])
    }

    @Test
    fun testABodyThatIsNotAListIsAFailedFetch() {
        for (body in listOf("", "<html>Bad gateway</html>", "{\"status\":401}", "[", "[[[[")) {
            assertFalse(body, NativeRules.readBody(body.toByteArray()).isList)
        }
        val empty = BodyReading(isList = true, reading = null)
        assertEquals(empty, NativeRules.readBody("[]".toByteArray()))
    }

    @Test
    fun testEveryPanelVectorMatchesItsCrcAndInkCount() {
        val shownSize = mutableSetOf<String>()
        for (case in Spec.cases("panel_vectors.json")) {
            val width = case.getInt("width")
            val height = case.getInt("height")
            val stamp = if (case.has("stamp")) case.getString("stamp") else null
            val label = "${case.getString("vector")} ${case.getString("profile")} $stamp"
            val lines = Spec.strings(case.getJSONArray("lines"))
            val rows = NativeRules.panel(lines, width, height, stamp)
            assertEquals(label, (width + 7) / 8 * height, rows!!.size)
            val crc = CRC32().apply { update(rows) }.value
            assertEquals(label, case.getLong("crc32"), crc)
            val ink = rows.sumOf { Integer.bitCount(it.toInt() and 0xFF).toLong() }
            assertEquals(label, case.getLong("ink"), ink)
            val atAppSize = width == MainActivity.PANEL_WIDTH && height == MainActivity.PANEL_HEIGHT
            if (atAppSize && stamp == null) shownSize += case.getString("vector")
        }
        // Every display vector is pinned, and matched, at the size the app shows.
        val vectors = Spec.cases("display_vectors.json").map { it.getString("name") }.toSet()
        assertEquals(vectors, shownSize)
    }

    @Test
    fun testARefusedPanelGivesNoImage() {
        val lines = listOf("IN RANGE", "112 mg/dL ->", "3 min ago")
        assertNull(NativeRules.panel(lines, 10, 10, null))
        assertNull(NativeRules.panel(lines, 296, 128, "25:00"))
        assertNull(NativeRules.panel(lines, 296, 128, "12:00:00"))
        assertNull(NativeRules.panel(emptyList(), 296, 128, null))
        assertNull(NativeRules.panel(List(9) { "IN RANGE" }, 296, 128, null))
        assertNull(NativeRules.panel(listOf("x".repeat(65)), 296, 128, null))
        assertNull(NativeRules.panel(listOf("café"), 296, 128, null))
        assertNull(NativeRules.panel(lines, 0, 128, null))
        assertNull(NativeRules.panel(lines, 296, 5000, null))
        assertNull(NativeRules.panel(lines, Int.MAX_VALUE, Int.MAX_VALUE, null))
    }

    @Test
    fun testTheSameLinesGiveTheSamePixels() {
        val lines = listOf("IN RANGE", "112 mg/dL ->", "3 min ago")
        val first = NativeRules.panel(lines, 296, 128, "02:14")
        assertArrayEquals(first, NativeRules.panel(lines, 296, 128, "02:14"))
    }
}
