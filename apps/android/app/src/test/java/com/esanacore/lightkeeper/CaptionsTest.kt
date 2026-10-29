package com.esanacore.lightkeeper

import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The captions are absolute 24-hour local times, so nothing has to tick to stay true. */
class CaptionsTest {
    private val noon = Instant.parse("2026-10-18T12:00:00Z").toEpochMilli()

    @Test
    fun testCaptionsAreAbsoluteLocalTwentyFourHourTimes() {
        assertEquals("checked 12:00", Captions.checked(noon, ZoneOffset.UTC))
        assertEquals("checked 05:00", Captions.checked(noon, ZoneId.of("America/Los_Angeles")))
        assertEquals("checked 21:00", Captions.checked(noon, ZoneId.of("Asia/Tokyo")))
        assertEquals(
            "Nightscout unreachable since 12:00",
            Captions.offlineSince(noon, ZoneOffset.UTC),
        )
        assertEquals(
            "Nightscout unreachable since 17:30",
            Captions.offlineSince(noon, ZoneId.of("Asia/Kolkata")),
        )
    }

    @Test
    fun testTheClockIsZeroPaddedAndNeverShowsSeconds() {
        assertEquals("07:05", utcClock("2026-10-18T07:05:59Z"))
        assertEquals("00:00", utcClock("2026-10-18T00:00:00Z"))
        assertEquals("23:59", utcClock("2026-10-18T23:59:59Z"))
        assertTrue(Regex("[0-2][0-9]:[0-5][0-9]").matches(Captions.clockText(noon)))
    }

    private fun utcClock(moment: String): String =
        Captions.clockText(Instant.parse(moment).toEpochMilli(), ZoneOffset.UTC)

    @Test
    fun testTheFirstCaptionSaysCheckingUntilAFetchAnswers() {
        assertEquals("checking Nightscout...", Captions.status(null, ZoneOffset.UTC))
        assertEquals(Captions.CHECKING, Captions.status(null))
        assertEquals("checked 12:00", Captions.status(noon, ZoneOffset.UTC))
    }
}
