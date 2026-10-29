package com.esanacore.lightkeeper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The last good reading ages into STALE on the clock alone, through the real
 * native rules, with no fetch: what keeps the screen honest when Nightscout
 * stops answering or the phone sleeps through its fetches (HAZ-001, HAZ-008).
 */
class ReageTest {
    private var clock = Spec.NOW_MS
    private val settings = Settings(nightscoutUrl = "https://ns.example.com")

    private fun body(mgdl: Int, ageMs: Long): ByteArray =
        "[{\"type\":\"sgv\",\"sgv\":$mgdl,\"date\":${clock - ageMs},\"direction\":\"Flat\"}]"
            .toByteArray()

    @Test
    fun testFortyMinuteReageShowsStaleWithoutAFetch() {
        val model = GlanceModel(settings, NativeRules) { clock }
        model.finishFetch(model.startFetch()!!, body(112, ageMs = 0))
        assertEquals(listOf("IN RANGE", "112 mg/dL ->", "just now"), model.state.lines)

        // Forty minutes pass and no fetch is made at all.
        clock += 40 * 60_000L
        model.reage()

        assertEquals(
            listOf(
                "STALE - DO NOT TRUST",
                "last: 112 mg/dL ->",
                "40 min ago",
                "Confirm on primary device",
            ),
            model.state.lines,
        )
        val glance = Presentation.of(model.state.lines)
        assertEquals(Presentation.Banner.STALE, glance.banner)
        assertEquals(Presentation.Hero.None, glance.hero)
    }

    @Test
    fun testTheScreenTurnsStaleAtTheFirstMinutePastTheLimit() {
        val model = GlanceModel(settings, NativeRules) { clock }
        model.finishFetch(model.startFetch()!!, body(95, ageMs = 0))
        clock += 15 * 60_000L
        model.reage()
        assertEquals("IN RANGE", model.state.lines[0])
        clock += 1
        model.reage()
        assertEquals("STALE - DO NOT TRUST", model.state.lines[0])
    }

    @Test
    fun testAFailedFetchAgesTheLastReadingAndSaysUnreachable() {
        val model = GlanceModel(settings, NativeRules) { clock }
        model.finishFetch(model.startFetch()!!, body(112, ageMs = 0))
        clock += 20 * 60_000L
        model.finishFetch(model.startFetch()!!, null)
        assertEquals(
            listOf(
                "STALE - DO NOT TRUST",
                "last: 112 mg/dL ->",
                "20 min ago",
                "Nightscout unreachable",
            ),
            model.state.lines,
        )
        assertTrue(model.state.fetchError)
        assertEquals(clock, model.state.offlineSinceMs)
    }
}
