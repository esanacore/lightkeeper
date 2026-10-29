package com.esanacore.lightkeeper

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.EditText
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Save on the settings screen and the saved token: a token field nobody
 * touched never rewrites or deletes the saved token (it may show empty only
 * because the Keystore could not open it just then), an edited one is sealed
 * anew, and an emptied one deletes it.
 */
class SettingsScreenTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private val tokenPrefs = context.getSharedPreferences(TokenStore.FILE, Context.MODE_PRIVATE)
    private val site = "https://ns.example.com"
    private val token = "lightkeeper-0123456789abcdef"
    private var activity: Activity? = null

    @Before
    fun saveASiteAndAToken() {
        clearAll()
        assertTrue(SettingsStore(context).save(Settings(nightscoutUrl = site)))
        assertTrue(TokenStore(context).write(token))
    }

    @After
    fun closeTheScreen() {
        activity?.let { instrumentation.runOnMainSync { if (!it.isFinishing) it.finish() } }
        clearAll()
    }

    private fun clearAll() {
        for (file in listOf(SettingsStore.FILE, TokenStore.FILE)) {
            context.getSharedPreferences(file, Context.MODE_PRIVATE).edit().clear().commit()
        }
    }

    private fun launch(): Activity {
        val intent =
            Intent(context, SettingsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val launched = instrumentation.startActivitySync(intent)
        instrumentation.waitForIdleSync()
        activity = launched
        return launched
    }

    private fun Activity.tokenField(): EditText = findViewById(R.id.lk_token)

    private fun Activity.pressSave() {
        instrumentation.runOnMainSync { findViewById<View>(R.id.lk_save).performClick() }
        instrumentation.waitForIdleSync()
    }

    @Test
    fun testSaveLeavesAnUntouchedTokenAsItWas() {
        val sealed = tokenPrefs.all.toMap()
        val screen = launch()
        assertEquals(token, screen.tokenField().text.toString())
        instrumentation.runOnMainSync { screen.findViewById<EditText>(R.id.lk_url).append("/") }
        screen.pressSave()
        assertTrue(screen.isFinishing)
        assertEquals("$site/", SettingsStore(context).load().nightscoutUrl)
        // Not rewritten: every write seals with a fresh nonce, so the bytes would differ.
        assertEquals(sealed, tokenPrefs.all.toMap())
        assertEquals(token, TokenStore(context).read())
    }

    @Test
    fun testAnEditedTokenIsSealedOnSave() {
        val screen = launch()
        instrumentation.runOnMainSync { screen.tokenField().setText("  lightkeeper-new  ") }
        screen.pressSave()
        assertTrue(screen.isFinishing)
        assertEquals("lightkeeper-new", TokenStore(context).read())
    }

    @Test
    fun testAnEmptiedTokenFieldDeletesTheSavedToken() {
        val screen = launch()
        instrumentation.runOnMainSync { screen.tokenField().setText("") }
        screen.pressSave()
        assertTrue(screen.isFinishing)
        assertTrue(tokenPrefs.all.isEmpty())
        assertNull(TokenStore(context).read())
    }
}
