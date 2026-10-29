package com.esanacore.lightkeeper

import android.content.Context
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** The token is sealed with a Keystore key: never on disk in the clear, and never guessed at. */
class TokenStoreTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val prefs = context.getSharedPreferences(TokenStore.FILE, Context.MODE_PRIVATE)
    private val token = "lightkeeper-0123456789abcdef"

    @Before
    @After
    fun clear() {
        prefs.edit().clear().commit()
    }

    @Test
    fun testTheTokenRoundTripsAndIsNeverStoredInTheClear() {
        val store = TokenStore(context)
        assertTrue(store.write(token))
        assertEquals(token, store.read())
        assertEquals(token, TokenStore(context).read())
        val stored = prefs.all.values.joinToString(" ")
        assertFalse("the token is on disk in the clear", stored.contains(token))
        assertFalse(stored.contains("0123456789abcdef"))
    }

    @Test
    fun testEveryWriteUsesAFreshNonce() {
        val store = TokenStore(context)
        store.write(token)
        val first = prefs.all.toMap()
        store.write(token)
        assertFalse(first == prefs.all.toMap())
        assertEquals(token, store.read())
    }

    @Test
    fun testAnEmptyTokenDeletesTheSavedOne() {
        val store = TokenStore(context)
        store.write(token)
        assertTrue(store.write(""))
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
    }

    @Test
    fun testADamagedTokenReadsAsNoneAndIsDeleted() {
        val store = TokenStore(context)
        store.write(token)
        val sealed = prefs.getString("sealed", null)!!
        val flipped = (if (sealed[0] == 'A') "B" else "A") + sealed.substring(1)
        prefs.edit().putString("sealed", flipped).commit()
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
        prefs.edit().putString("nonce", "not base64 !").putString("sealed", "x").commit()
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
    }
}
