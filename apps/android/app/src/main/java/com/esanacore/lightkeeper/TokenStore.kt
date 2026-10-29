package com.esanacore.lightkeeper

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import java.io.IOException
import java.security.GeneralSecurityException
import java.security.KeyStore
import java.security.ProviderException
import java.util.Base64
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * The one secret the app holds: the readable Nightscout token.
 *
 * It is sealed with AES-256-GCM under a key that lives in the Android
 * Keystore and never leaves it, and only the sealed bytes and their nonce sit
 * in this app's private SharedPreferences. Backup is off for the whole app
 * (allowBackup false, and data_extraction_rules.xml excludes everything), and
 * a Keystore key never moves to another device, so a copied preferences file
 * cannot be opened anywhere else. Nothing here logs, and nothing puts the
 * token in a URL: [NightscoutClient] sends it only in the api-secret header.
 *
 * A sealed token is deleted only on proof that it can never open again: its
 * check fails, its bytes are not what this class wrote, or its key is gone
 * or permanently invalidated. A Keystore that is busy or cannot be reached
 * right now is no such proof, so the token stays for the next read. A key
 * proved permanently invalidated is deleted too, so the next write makes a
 * new one rather than failing on the dead key for good. (This key needs no
 * screen lock or fingerprint, so Android has no reason to invalidate it;
 * the case is handled all the same.)
 *
 * The fetch thread reads while the settings screen may write, so every read,
 * write and delete holds one lock, and a read takes the nonce and the sealed
 * bytes from one snapshot: a nonce is never paired with another write's
 * bytes. [findKey] looks the key up in the Keystore and [dropKey] deletes
 * it; TokenStoreTest passes ones that fail.
 */
class TokenStore
internal constructor(
    context: Context,
    private val findKey: () -> SecretKey?,
    private val dropKey: () -> Unit,
) {
    constructor(context: Context) : this(context, { keystoreKey() }, { deleteKeystoreKey() })

    private val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /**
     * The saved token, or null when there is none or it cannot be opened
     * now. A sealed token proved damaged is deleted; any other failure
     * leaves it for the next read.
     */
    fun read(): String? =
        synchronized(LOCK) {
            val saved = prefs.all
            val nonce = saved[KEY_NONCE] as? String ?: return null
            val sealed = saved[KEY_SEALED] as? String ?: return null
            open(nonce, sealed)
        }

    /**
     * Seals and saves [token]; an empty token deletes the saved one. Returns
     * false, saving nothing, when the Keystore refuses.
     */
    fun write(token: String): Boolean =
        synchronized(LOCK) {
            if (token.isEmpty()) {
                clear()
                return true
            }
            val cipher: Cipher
            val sealed: ByteArray
            try {
                cipher =
                    try {
                        sealer(findKey() ?: newKey())
                    } catch (_: KeyPermanentlyInvalidatedException) {
                        // The key can never seal or open again: a new one takes its place.
                        dropKey()
                        sealer(newKey())
                    }
                sealed = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
            } catch (_: GeneralSecurityException) {
                return false
            } catch (_: IOException) {
                return false
            } catch (_: ProviderException) {
                return false
            }
            prefs
                .edit()
                .putString(KEY_NONCE, encode(cipher.iv))
                .putString(KEY_SEALED, encode(sealed))
                .apply()
            true
        }

    /** Deletes the saved token. The key stays for the next one. */
    fun clear() {
        synchronized(LOCK) { prefs.edit().remove(KEY_NONCE).remove(KEY_SEALED).apply() }
    }

    /** Opens a sealed token, deleting it only when it is proved damaged. */
    private fun open(nonceText: String, sealedText: String): String? {
        val nonce: ByteArray
        val sealed: ByteArray
        try {
            nonce = decode(nonceText)
            sealed = decode(sealedText)
        } catch (_: IllegalArgumentException) {
            return damaged()
        }
        if (nonce.size != NONCE_BYTES) return damaged()
        return try {
            // No key under the alias: nothing can ever open these bytes again.
            val key = findKey() ?: return damaged()
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_BITS, nonce))
            String(cipher.doFinal(sealed), Charsets.UTF_8)
        } catch (_: AEADBadTagException) {
            damaged()
        } catch (_: KeyPermanentlyInvalidatedException) {
            dropKey()
            damaged()
        } catch (_: GeneralSecurityException) {
            // Busy, locked or unreachable right now: no proof of damage.
            null
        } catch (_: IOException) {
            null
        } catch (_: ProviderException) {
            null
        }
    }

    private fun damaged(): String? {
        clear()
        return null
    }

    /** A cipher ready to seal under [key]; the Keystore picks a fresh random nonce each time. */
    private fun sealer(key: SecretKey): Cipher =
        Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key) }

    private fun newKey(): SecretKey {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(KEY_BITS)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }

    private fun encode(bytes: ByteArray): String = Base64.getEncoder().encodeToString(bytes)

    private fun decode(text: String): ByteArray = Base64.getDecoder().decode(text)

    companion object {
        const val FILE = "lightkeeper.token"
        private const val KEY_NONCE = "nonce"
        private const val KEY_SEALED = "sealed"
        private const val KEYSTORE = "AndroidKeyStore"
        private const val KEY_ALIAS = "lightkeeper-nightscout-token"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val TAG_BITS = 128
        private const val KEY_BITS = 256

        /** The Keystore's GCM nonce: 12 bytes, chosen by the Keystore on every write. */
        private const val NONCE_BYTES = 12

        /** Shared by every TokenStore in the process: they all use one preferences file. */
        private val LOCK = Any()

        /** The app's key in the Android Keystore, or null when there is none yet. */
        private fun keystoreKey(): SecretKey? = keystore().getKey(KEY_ALIAS, null) as? SecretKey

        /**
         * Deletes the app's key from the Android Keystore. Never throws: a
         * key that cannot be deleted now is tried again the next time it is
         * proved dead.
         */
        private fun deleteKeystoreKey() {
            try {
                keystore().deleteEntry(KEY_ALIAS)
            } catch (_: GeneralSecurityException) {
                // Nothing to do: the next write or read finds the key again.
            } catch (_: IOException) {
                // As above.
            } catch (_: ProviderException) {
                // As above.
            }
        }

        private fun keystore(): KeyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
    }
}
