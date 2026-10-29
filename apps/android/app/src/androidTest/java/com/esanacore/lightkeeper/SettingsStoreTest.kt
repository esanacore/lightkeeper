package com.esanacore.lightkeeper

import android.content.Context
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The settings on disk (HAZ-006): an invalid threshold set found there is
 * reset to the defaults and written back, so the screen and the rules always
 * run on the same numbers, and Save writes nothing for an invalid set.
 */
class SettingsStoreTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val prefs = context.getSharedPreferences(SettingsStore.FILE, Context.MODE_PRIVATE)
    private val site = "https://ns.example.com"

    @Before
    @After
    fun clear() {
        prefs.edit().clear().commit()
    }

    private fun writeRaw(values: Map<String, Any>) {
        val editor = prefs.edit()
        for ((key, value) in values) {
            when (value) {
                is String -> editor.putString(key, value)
                is Int -> editor.putInt(key, value)
            }
        }
        editor.commit()
    }

    @Test
    fun testAnInvalidStoredSetIsResetAndWrittenBackToDisk() {
        // Inverted: urgent low above low, as a tampered or corrupted file might hold.
        writeRaw(Settings(site, urgentLow = 90, low = 80, high = 200, staleMinutes = 30).toStored())
        val loaded = SettingsStore(context).load()
        assertEquals(Settings(nightscoutUrl = site), loaded)
        // On disk now: the defaults, with the address kept.
        assertEquals(Settings(nightscoutUrl = site).toStored(), prefs.all.toMap())
        assertEquals(loaded, SettingsStore(context).load())
    }

    @Test
    fun testAZeroStaleLimitOnDiskIsResetAndWrittenBack() {
        writeRaw(Settings(site, staleMinutes = 0).toStored())
        assertEquals(15, SettingsStore(context).load().staleMinutes)
        assertEquals(15, prefs.getInt(Settings.KEY_STALE_MINUTES, -1))
    }

    @Test
    fun testAValidStoredSetIsLoadedAndNotRewritten() {
        val saved = Settings(site, 60, 80, 200, 300, 20)
        writeRaw(saved.toStored())
        assertEquals(saved, SettingsStore(context).load())
        assertEquals(saved.toStored(), prefs.all.toMap())
    }

    @Test
    fun testSaveRefusesAnInvalidSetAndWritesNothing() {
        val store = SettingsStore(context)
        assertFalse(store.save(Settings(site, low = 300)))
        assertFalse(store.save(Settings(site, staleMinutes = 0)))
        assertFalse(store.save(Settings("http://ns.example.com")))
        assertTrue(prefs.all.isEmpty())

        val good = Settings(site, staleMinutes = 20)
        assertTrue(store.save(good))
        assertFalse(store.save(Settings(site, urgentLow = 90, low = 80)))
        assertEquals(good.toStored(), prefs.all.toMap())
        assertEquals(good, store.load())
    }
}
