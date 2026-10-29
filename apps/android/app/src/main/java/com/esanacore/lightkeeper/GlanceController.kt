package com.esanacore.lightkeeper

import android.content.Context
import android.os.Handler
import android.os.Looper
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * Runs the [GlanceModel] while the glance is on screen: a fetch when the
 * screen appears and every 60 seconds after, and a re-age from the last good
 * reading every 30 seconds and whenever the screen comes back, with no
 * fetch, so the screen turns STALE on time even when fetches stop or the
 * phone has slept (HAZ-008). Nothing runs while the screen is hidden: no
 * service, no alarm, no notification.
 *
 * Fetches run one at a time on a background thread, each with a new
 * [NightscoutClient] and the token read fresh from [TokenStore]; answers
 * come back to the main thread, where the model decides whether they still
 * apply. Kept across a rotation, so the last good reading survives it.
 */
class GlanceController(context: Context) {
    private val appContext = context.applicationContext
    private val settingsStore = SettingsStore(appContext)
    private val tokenStore = TokenStore(appContext)
    private val handler = Handler(Looper.getMainLooper())
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private var closed = false

    val model = GlanceModel(settingsStore.load(), NativeRules, System::currentTimeMillis)

    /** Called on the main thread after every change to [GlanceModel.state]. */
    var onChange: (() -> Unit)? = null

    private val fetchTick =
        object : Runnable {
            override fun run() {
                fetch()
                handler.postDelayed(this, FETCH_INTERVAL_MS)
            }
        }

    private val reageTick =
        object : Runnable {
            override fun run() {
                model.reage()
                changed()
                handler.postDelayed(this, REAGE_INTERVAL_MS)
            }
        }

    /**
     * The screen became visible (launch, or back from the background or from
     * Settings): pick up saved settings, re-age at once, fetch, and start
     * both timers.
     */
    fun start() {
        if (closed) return
        stopTimers()
        // Re-ages the last reading against the saved settings, or forgets it
        // when the address changed.
        model.updateSettings(settingsStore.load())
        changed()
        handler.post(fetchTick)
        handler.postDelayed(reageTick, REAGE_INTERVAL_MS)
    }

    /** The screen came to the front: re-age at once, with no fetch. */
    fun resume() {
        if (closed) return
        model.reage()
        changed()
    }

    /** The screen is hidden: stop both timers. */
    fun stop() {
        stopTimers()
    }

    /** The glance is gone for good: stop, and drop any fetch still running. */
    fun close() {
        closed = true
        stopTimers()
        onChange = null
        executor.shutdownNow()
    }

    private fun stopTimers() {
        handler.removeCallbacks(fetchTick)
        handler.removeCallbacks(reageTick)
    }

    private fun fetch() {
        val ticket = model.startFetch()
        if (ticket == null) {
            changed()
            return
        }
        val site = ticket.settings.site
        executor.execute {
            // Any failure degrades to a failed fetch, never a crash: the model
            // then re-ages the last good reading with "Nightscout unreachable".
            val body =
                try {
                    site?.let { NightscoutClient(it, tokenStore.read()).fetchEntries() }
                } catch (_: Exception) {
                    null
                }
            handler.post {
                if (!closed) {
                    model.finishFetch(ticket, body)
                    changed()
                }
            }
        }
    }

    private fun changed() {
        onChange?.invoke()
    }

    companion object {
        const val FETCH_INTERVAL_MS = 60_000L
        const val REAGE_INTERVAL_MS = 30_000L
    }
}
