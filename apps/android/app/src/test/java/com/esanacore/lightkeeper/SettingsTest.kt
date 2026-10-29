package com.esanacore.lightkeeper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The threshold rules are the other ports' (status.py, Status.swift), and the
 * settings screen's ranges, steps and caution are the iOS app's (SettingsTests.swift).
 */
class SettingsTest {
    private val site = "https://ns.example.com"

    @Test
    fun testTheDefaultsAreTheDocumentedOnesAndValid() {
        val defaults = Settings()
        assertEquals(listOf(55, 70, 180, 250, 15), defaults.values())
        assertTrue(defaults.isValid)
        assertNull(defaults.validationMessage)
        assertEquals(Thresholds(55, 70, 180, 250, 15L * 60_000), defaults.thresholds)
        assertEquals(Thresholds(), defaults.thresholds)
    }

    @Test
    fun testThresholdsMustIncreaseInsideTheSensorRange() {
        val invalid =
            listOf(
                Settings(urgentLow = 70, low = 70),
                Settings(low = 180, high = 180),
                Settings(high = 250, urgentHigh = 250),
                Settings(low = 200, high = 180),
                Settings(urgentLow = 39),
                Settings(urgentHigh = 401),
            )
        for (settings in invalid) {
            assertFalse(settings.toString(), settings.isValid)
            assertEquals(
                "Thresholds must increase: urgent low < low < high < urgent high.",
                settings.validationMessage,
            )
            // Never judged against an impossible set: the rules get the defaults.
            assertEquals(Thresholds(), settings.thresholds)
        }
        assertTrue(Settings(urgentLow = 40, urgentHigh = 400).isValid)
    }

    @Test
    fun testTheStaleLimitMustBePositive() {
        assertEquals(
            "Stale limit must be at least one minute.",
            Settings(staleMinutes = 0).validationMessage,
        )
        assertEquals(Settings.STALE_NOT_POSITIVE, Settings(staleMinutes = -5).validationMessage)
        assertEquals(60L * 60_000, Settings(staleMinutes = 60).thresholds.staleAfterMs)
    }

    @Test
    fun testTheCautionShowsAboveFifteenMinutesWordForWord() {
        assertNull(Settings(staleMinutes = 15).staleCaution)
        assertNull(Settings(staleMinutes = 6).staleCaution)
        assertEquals(
            "Above 15 minutes, an old reading keeps looking current for longer before this " +
                "display says STALE. The primary CGM app's signal-loss alert is the one to " +
                "rely on.",
            Settings(staleMinutes = 16).staleCaution,
        )
        assertEquals(Settings.STALE_CAUTION, Settings(staleMinutes = 60).staleCaution)
    }

    @Test
    fun testTheStepsAndTheCapAreTheIosRules() {
        assertEquals(5, Settings.THRESHOLD_STEP)
        assertEquals(1, Settings.STALE_STEP)
        assertEquals(40..100, Settings.URGENT_LOW_RANGE)
        assertEquals(45..150, Settings.LOW_RANGE)
        assertEquals(100..350, Settings.HIGH_RANGE)
        assertEquals(105..400, Settings.URGENT_HIGH_RANGE)
        assertEquals(6..60, Settings.STALE_RANGE)
        assertEquals(15, Settings.STALE_CAUTION_ABOVE)
    }

    @Test
    fun testEveryStepperBoundAndDefaultSitsOnTheFiveStepGrid() {
        val defaults = Settings()
        val ranges =
            listOf(
                Settings.URGENT_LOW_RANGE to defaults.urgentLow,
                Settings.LOW_RANGE to defaults.low,
                Settings.HIGH_RANGE to defaults.high,
                Settings.URGENT_HIGH_RANGE to defaults.urgentHigh,
            )
        for ((range, default) in ranges) {
            assertEquals(0, range.first % Settings.THRESHOLD_STEP)
            assertEquals(0, range.last % Settings.THRESHOLD_STEP)
            assertEquals(0, default % Settings.THRESHOLD_STEP)
            assertTrue(default in range)
        }
        assertTrue(defaults.staleMinutes in Settings.STALE_RANGE)
    }

    @Test
    fun testAStepStaysInsideItsRange() {
        assertEquals(60, Settings.step(55, 5, Settings.URGENT_LOW_RANGE))
        assertEquals(100, Settings.step(100, 5, Settings.URGENT_LOW_RANGE))
        assertEquals(40, Settings.step(40, -5, Settings.URGENT_LOW_RANGE))
        assertEquals(60, Settings.step(60, 1, Settings.STALE_RANGE))
        assertEquals(6, Settings.step(6, -1, Settings.STALE_RANGE))
        // A value from disk outside the range comes back inside on the first press.
        assertEquals(100, Settings.step(120, 5, Settings.URGENT_LOW_RANGE))
    }

    @Test
    fun testAnEmptyStoreLoadsTheDefaults() {
        val restored = Settings.restore(emptyMap<String, Any>())
        assertEquals(Settings(), restored.settings)
        assertFalse(restored.wasReset)
    }

    @Test
    fun testAValidStoredSetIsKept() {
        val saved = Settings(site, 60, 80, 200, 300, 20)
        val restored = Settings.restore(saved.toStored())
        assertEquals(saved, restored.settings)
        assertFalse(restored.wasReset)
    }

    @Test
    fun testInvalidStoredSetIsResetAndWrittenBack() {
        val stored = Settings(site, urgentLow = 90, low = 80).toStored()
        val restored = Settings.restore(stored)
        assertTrue(restored.wasReset)
        assertEquals(Settings(nightscoutUrl = site), restored.settings)
    }

    @Test
    fun testAZeroStaleLimitOnDiskIsReset() {
        val restored = Settings.restore(Settings(staleMinutes = 0).toStored())
        assertTrue(restored.wasReset)
        assertEquals(15, restored.settings.staleMinutes)
    }

    @Test
    fun testAMistypedStoredValueTakesItsDefault() {
        val stored =
            mapOf(Settings.KEY_URL to 7, Settings.KEY_LOW to "70", Settings.KEY_HIGH to 190)
        val restored = Settings.restore(stored)
        assertEquals(Settings(high = 190), restored.settings)
        assertFalse(restored.wasReset)
    }

    @Test
    fun testAnUnusableStoredAddressIsKeptForSettingsToExplain() {
        val restored = Settings.restore(Settings("http://ns.example.com").toStored())
        assertEquals("http://ns.example.com", restored.settings.nightscoutUrl)
        assertFalse(restored.settings.isConfigured)
        assertEquals(SiteAddress.HTTPS_ONLY, restored.settings.urlProblem)
        assertNull(restored.settings.site)
    }

    @Test
    fun testAnEmptyAddressIsNotConfiguredAndNotAnError() {
        val settings = Settings()
        assertNull(settings.urlProblem)
        assertFalse(settings.isConfigured)
        assertTrue(settings.canSave)
        assertNull(settings.site)
    }

    @Test
    fun testSaveIsRefusedForAnInvalidSetOrAnUnusableAddress() {
        assertTrue(Settings(site).canSave)
        assertTrue(Settings(site).isConfigured)
        assertEquals("https://ns.example.com", Settings(site).site.toString())
        assertFalse(Settings(site, low = 300).canSave)
        assertFalse(Settings("https://ns.example.com/api/v1/entries").canSave)
        assertFalse(Settings("http://ns.example.com").canSave)
        assertFalse(Settings(site, staleMinutes = 0).canSave)
    }

    @Test
    fun testResetRestoresTheDefaultsAndKeepsTheAddress() {
        val reset = Settings(site, 60, 80, 200, 300, 30).resettingThresholds()
        assertEquals(Settings(nightscoutUrl = site), reset)
    }

    @Test
    fun testTheStoredKeysAreTheIosOnes() {
        assertEquals(
            setOf("nightscoutURL", "urgentLow", "low", "high", "urgentHigh", "staleMinutes"),
            Settings().toStored().keys,
        )
    }

    private fun Settings.values() = listOf(urgentLow, low, high, urgentHigh, staleMinutes)
}
