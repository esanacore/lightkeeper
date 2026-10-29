package com.esanacore.lightkeeper

import android.content.Context
import android.security.keystore.KeyPermanentlyInvalidatedException
import androidx.test.platform.app.InstrumentationRegistry
import java.io.IOException
import java.security.KeyStoreException
import java.security.ProviderException
import java.security.UnrecoverableKeyException
import java.util.Base64
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import javax.crypto.SecretKey
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The token is sealed with a Keystore key: never on disk in the clear, and
 * never guessed at. It is deleted only on proof of damage (a failed check,
 * bytes this class never wrote, a missing or dead key), never because the
 * Keystore could not be reached for a moment, and never by a read that runs
 * alongside a write.
 */
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

    @Test
    fun testANonceOfTheWrongSizeIsDeleted() {
        val store = TokenStore(context)
        store.write(token)
        val thirteen = Base64.getEncoder().encodeToString(ByteArray(13))
        prefs.edit().putString("nonce", thirteen).commit()
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
    }

    @Test
    fun testAKeystoreThatCannotBeReachedNowKeepsTheToken() {
        // Busy or locked is no proof of damage: the sealed token stays, untouched.
        assertTrue(TokenStore(context).write(token))
        val saved = prefs.all.toMap()
        var dropped = false
        val failures =
            listOf<() -> SecretKey?>(
                { throw KeyStoreException("busy") },
                { throw UnrecoverableKeyException("locked") },
                { throw ProviderException("keystore daemon gone") },
                { throw IOException("keystore unreachable") },
            )
        for (failure in failures) {
            val store = TokenStore(context, findKey = failure, dropKey = { dropped = true })
            assertNull(store.read())
            assertEquals(saved, prefs.all.toMap())
        }
        assertFalse(dropped)
        assertEquals(token, TokenStore(context).read())
    }

    @Test
    fun testAMissingKeyDeletesTheToken() {
        assertTrue(TokenStore(context).write(token))
        var dropped = false
        val store = TokenStore(context, findKey = { null }, dropKey = { dropped = true })
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
        assertFalse(dropped)
    }

    @Test
    fun testAPermanentlyInvalidatedKeyDeletesTheTokenAndTheKey() {
        assertTrue(TokenStore(context).write(token))
        var dropped = 0
        val store =
            TokenStore(
                context,
                findKey = { throw KeyPermanentlyInvalidatedException() },
                dropKey = { dropped += 1 },
            )
        assertNull(store.read())
        assertTrue(prefs.all.isEmpty())
        assertEquals(1, dropped)
    }

    @Test
    fun testAWriteOverAnInvalidatedKeyMakesANewKeyAndSaves() {
        var dropped = 0
        val store =
            TokenStore(
                context,
                findKey = { throw KeyPermanentlyInvalidatedException() },
                dropKey = { dropped += 1 },
            )
        assertTrue(store.write(token))
        assertEquals(1, dropped)
        // Sealed under the new key, which the app's own store finds and opens.
        assertEquals(token, TokenStore(context).read())
    }

    @Test
    fun testAWriteTheKeystoreRefusesSavesNothing() {
        val store =
            TokenStore(context, findKey = { throw KeyStoreException("busy") }, dropKey = {})
        assertFalse(store.write(token))
        assertTrue(prefs.all.isEmpty())
    }

    @Test
    fun testReadsDuringWritesNeverDeleteAJustSavedToken() {
        // The fetch thread reads while the settings screen writes: a read must
        // never pair one write's nonce with another's bytes and delete the token.
        val first = TokenStore(context)
        assertTrue(first.write("$token-start"))
        val written = (0 until 40).map { "$token-$it" }
        val seen = mutableListOf<String?>()
        val writing = AtomicBoolean(true)
        val reader = Thread {
            val store = TokenStore(context)
            while (writing.get()) seen += store.read()
        }
        reader.start()
        val writer = TokenStore(context)
        for (each in written) assertTrue(writer.write(each))
        writing.set(false)
        reader.join(TimeUnit.SECONDS.toMillis(30))
        assertFalse(reader.isAlive)
        assertTrue("the reader never ran alongside the writes", seen.isNotEmpty())
        val allowed = written.toSet() + "$token-start"
        for (read in seen) assertTrue("read $read", read in allowed)
        assertEquals(written.last(), TokenStore(context).read())
    }
}
