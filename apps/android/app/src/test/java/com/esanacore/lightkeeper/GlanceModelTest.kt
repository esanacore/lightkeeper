package com.esanacore.lightkeeper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The model's bookkeeping, with a recorder in place of the native rules: what
 * it asks the rules, when it keeps or drops the last good reading, and which
 * fetch answers it applies. The rules themselves run through JNI in the
 * instrumented tests, against every shared vector.
 */
class GlanceModelTest {
    private val site = "https://ns.example.com"
    private val reading = Reading(mgdl = 112, timestampMs = 1_000_000L, trendCode = 3)

    /** Writes its inputs as the "lines", so a test can read back what was asked. */
    private class Recorder(private val reading: Reading) : Rules {
        var asked = 0

        override fun readBody(body: ByteArray): BodyReading =
            when (String(body)) {
                "list" -> BodyReading(isList = true, reading = reading)
                "empty" -> BodyReading(isList = true, reading = null)
                else -> BodyReading(isList = false, reading = null)
            }

        override fun lines(
            reading: Reading?,
            nowMs: Long,
            thresholds: Thresholds,
            fetchError: Boolean,
        ): List<String> {
            asked += 1
            return listOf(
                "mgdl=${reading?.mgdl}",
                "now=$nowMs",
                "error=$fetchError",
                "stale=${thresholds.staleAfterMs}",
            )
        }
    }

    private var clock = 2_000_000L
    private val rules = Recorder(reading)

    private fun model(url: String = site, stale: Int = 15) =
        GlanceModel(Settings(nightscoutUrl = url, staleMinutes = stale), rules) { clock }

    @Test
    fun testFirstRunMakesNoFetchAndHasNoReading() {
        val glance = model(url = "")
        assertNull(glance.startFetch())
        assertFalse(glance.state.configured)
        assertEquals("mgdl=null", glance.state.lines[0])
        assertNull(glance.state.lastRefreshMs)
        assertNull(glance.state.offlineSinceMs)
    }

    @Test
    fun testAnUnusableAddressMakesNoFetch() {
        val glance = model(url = "http://ns.example.com")
        assertNull(glance.startFetch())
        assertFalse(glance.state.configured)
    }

    @Test
    fun testAGoodFetchShowsItsReadingAtTheTimeItAnswered() {
        val glance = model()
        val ticket = glance.startFetch()!!
        clock = 2_060_000L
        glance.finishFetch(ticket, "list".toByteArray())
        val state = glance.state
        assertTrue(state.configured)
        assertEquals(listOf("mgdl=112", "now=2060000", "error=false", "stale=900000"), state.lines)
        assertFalse(state.fetchError)
        assertEquals(2_060_000L, state.lastRefreshMs)
        assertEquals(2_060_000L, state.drawnAtMs)
        assertNull(state.offlineSinceMs)
    }

    @Test
    fun testReageTurnsTheLastReadingOlderWithoutAFetch() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        clock += 40 * 60_000L
        glance.reage()
        assertEquals("mgdl=112", glance.state.lines[0])
        assertEquals("now=${clock}", glance.state.lines[1])
        assertEquals(clock, glance.state.drawnAtMs)
    }

    @Test
    fun testAFailedFetchKeepsAgingTheLastGoodReadingAsUnreachable() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        clock += 60_000L
        glance.finishFetch(glance.startFetch()!!, null)
        val lines = glance.state.lines
        assertEquals(listOf("mgdl=112", "now=$clock", "error=true", "stale=900000"), lines)
        assertTrue(glance.state.fetchError)
    }

    @Test
    fun testABodyThatIsNotAListIsAFailedFetch() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        glance.finishFetch(glance.startFetch()!!, "<html>".toByteArray())
        assertEquals("mgdl=112", glance.state.lines[0])
        assertEquals("error=true", glance.state.lines[2])
        assertNotNull(glance.state.offlineSinceMs)
    }

    @Test
    fun testAListWithNoTrustworthyReadingForgetsTheOldOne() {
        // As Python and iOS: Nightscout answered, and it has nothing to show.
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        glance.finishFetch(glance.startFetch()!!, "empty".toByteArray())
        assertEquals("mgdl=null", glance.state.lines[0])
        assertEquals("error=false", glance.state.lines[2])
        glance.finishFetch(glance.startFetch()!!, null)
        assertEquals("mgdl=null", glance.state.lines[0])
    }

    @Test
    fun testOfflineSinceIsSetOnTheFirstFailureKeptOnRepeatsAndClearedOnSuccess() {
        val glance = model()
        clock = 3_000_000L
        glance.finishFetch(glance.startFetch()!!, null)
        assertEquals(3_000_000L, glance.state.offlineSinceMs)
        clock = 3_060_000L
        glance.finishFetch(glance.startFetch()!!, null)
        assertEquals(3_000_000L, glance.state.offlineSinceMs)
        assertEquals(3_060_000L, glance.state.lastRefreshMs)
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        assertNull(glance.state.offlineSinceMs)
        assertFalse(glance.state.fetchError)
    }

    @Test
    fun testALateAnswerFromAnOlderFetchIsDropped() {
        val glance = model()
        val older = glance.startFetch()!!
        val newer = glance.startFetch()!!
        glance.finishFetch(newer, "list".toByteArray())
        val shown = glance.state
        glance.finishFetch(older, null)
        assertEquals(shown, glance.state)
        assertFalse(glance.state.fetchError)
    }

    @Test
    fun testChangingTheSiteForgetsTheOldSitesReadingAndDropsItsAnswers() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        val inFlight = glance.startFetch()!!
        glance.updateSettings(Settings(nightscoutUrl = "https://other.example.com"))
        assertEquals("mgdl=null", glance.state.lines[0])
        assertNull(glance.state.lastRefreshMs)
        glance.finishFetch(inFlight, "list".toByteArray())
        assertEquals("mgdl=null", glance.state.lines[0])
    }

    @Test
    fun testNewThresholdsOnTheSameSiteReageTheReading() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        glance.updateSettings(Settings(nightscoutUrl = site, staleMinutes = 10))
        val lines = glance.state.lines
        assertEquals(listOf("mgdl=112", "now=$clock", "error=false", "stale=600000"), lines)
    }

    @Test
    fun testClearingTheAddressGoesBackToTheSetupScreen() {
        val glance = model()
        glance.finishFetch(glance.startFetch()!!, "list".toByteArray())
        glance.updateSettings(Settings())
        assertFalse(glance.state.configured)
        assertNull(glance.startFetch())
        assertEquals("mgdl=null", glance.state.lines[0])
    }

    @Test
    fun testEveryStateComesFromTheRules() {
        val glance = model()
        val before = rules.asked
        glance.reage()
        glance.finishFetch(glance.startFetch()!!, null)
        assertEquals(before + 2, rules.asked)
    }
}
