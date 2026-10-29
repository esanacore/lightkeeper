package com.esanacore.lightkeeper

import android.content.Context

/**
 * [Settings] in this app's private SharedPreferences. The token is never
 * stored here; [TokenStore] keeps it encrypted.
 */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /** The saved settings. An invalid threshold set is reset and written back (HAZ-006). */
    fun load(): Settings {
        val restored = Settings.restore(prefs.all)
        if (restored.wasReset) write(restored.settings)
        return restored.settings
    }

    /** Persists [settings]. Returns false, writing nothing, when [Settings.canSave] is false. */
    fun save(settings: Settings): Boolean {
        if (!settings.canSave) return false
        write(settings)
        return true
    }

    private fun write(settings: Settings) {
        val editor = prefs.edit()
        for ((key, value) in settings.toStored()) {
            when (value) {
                is String -> editor.putString(key, value)
                is Int -> editor.putInt(key, value)
            }
        }
        editor.apply()
    }

    companion object {
        const val FILE = "lightkeeper.settings"
    }
}
