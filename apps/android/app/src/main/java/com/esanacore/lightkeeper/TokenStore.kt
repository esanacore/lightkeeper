package com.esanacore.lightkeeper

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.IOException
import java.security.GeneralSecurityException
import java.security.KeyStore
import java.security.ProviderException
import java.util.Base64
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
 * A sealed token that no longer opens (the key was removed, the file was
 * damaged) is deleted and read as no token, never as a guess.
 */
class TokenStore(context: Context) {
    private val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /**
     * The saved token, or null when there is none or it cannot be opened. A
     * sealed token that fails its check is deleted; a Keystore that cannot
     * be reached right now leaves it for the next read.
     */
    fun read(): String? {
        val nonce = prefs.getString(KEY_NONCE, null) ?: return null
        val sealed = prefs.getString(KEY_SEALED, null) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                existingKey() ?: throw GeneralSecurityException("no key"),
                GCMParameterSpec(TAG_BITS, decode(nonce)),
            )
            String(cipher.doFinal(decode(sealed)), Charsets.UTF_8)
        } catch (_: GeneralSecurityException) {
            clear()
            null
        } catch (_: IllegalArgumentException) {
            clear()
            null
        } catch (_: IOException) {
            null
        } catch (_: ProviderException) {
            null
        }
    }

    /**
     * Seals and saves [token]; an empty token deletes the saved one. Returns
     * false, saving nothing, when the Keystore refuses.
     */
    fun write(token: String): Boolean {
        if (token.isEmpty()) {
            clear()
            return true
        }
        val sealed: ByteArray
        val nonce: ByteArray
        try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            // The Keystore picks a fresh random nonce for every encryption.
            cipher.init(Cipher.ENCRYPT_MODE, existingKey() ?: newKey())
            sealed = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
            nonce = cipher.iv
        } catch (_: GeneralSecurityException) {
            return false
        } catch (_: IOException) {
            return false
        } catch (_: ProviderException) {
            return false
        }
        prefs
            .edit()
            .putString(KEY_NONCE, encode(nonce))
            .putString(KEY_SEALED, encode(sealed))
            .apply()
        return true
    }

    /** Deletes the saved token. The key stays for the next one. */
    fun clear() {
        prefs.edit().remove(KEY_NONCE).remove(KEY_SEALED).apply()
    }

    private fun existingKey(): SecretKey? {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        return keyStore.getKey(KEY_ALIAS, null) as? SecretKey
    }

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
    }
}
