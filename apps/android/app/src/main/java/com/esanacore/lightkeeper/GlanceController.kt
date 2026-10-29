package com.esanacore.lightkeeper

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import java.util.concurrent.Executor
import java.util.concurrent.Executors

/**
 * The main thread's queue, and a clock that keeps counting while the phone
 * sleeps: a [Handler] in the app, a queue driven by hand in the JVM tests
 * (GlanceControllerTest).
 */
internal interface MainQueue {
    /** Runs [task] on the main thread after [delayMs]. */
    fun post(delayMs: Long, task: Runnable)

    /** Drops every pending run of [task]. */
    fun remove(task: Runnable)

    /** Milliseconds from a fixed point; never set back, and counts through sleep. */
    fun elapsedMs(): Long
}

/** One fetch as the controller runs it: [run] on the fetch thread, [cancel] from the main one. */
internal interface FetchJob {
    /** Blocking: the raw entries body, or null when the fetch failed. Never throws. */
    fun run(): ByteArray?

    /** Ends the fetch early, from any thread, without waiting for it. */
    fun cancel()
}

/**
 * Runs the [GlanceModel] while the glance is on screen: a fetch when the
 * screen appears and every 60 seconds after, and a re-age from the last good
 * reading every 30 seconds and whenever the screen comes back, with no
 * fetch, so the screen turns STALE on time even when fetches stop or the
 * phone has slept (HAZ-008). Coming back to the front also fetches when the
 * last fetch began 15 seconds ago or more, which covers a dialog or the
 * notification shade, where the screen never stopped; a quick focus change
 * does not start a storm of fetches.
 *
 * Nothing runs while the screen is hidden: no service, no alarm, no
 * notification. Hiding it stops both timers and cancels a fetch still
 * running, whose answer is then dropped.
 *
 * Fetches run one at a time on a background thread, each with a new
 * [NightscoutClient] and the token read fresh from [TokenStore]. A fetch that
 * falls due while another is running starts when that one answers, and any
 * more that fall due meanwhile are the same one fetch. A fetch gets
 * [FETCH_DEADLINE_MS], twice the client's timeout, as the iOS
 * app's resource timeout: past that it is cancelled and shown at once as a
 * failed fetch ("Nightscout unreachable"), even if its thread is still stuck
 * in a call. Answers come back to the main thread, where the model decides
 * whether they still apply. Kept across a rotation, so the last good reading
 * survives it.
 *
 * Built by [create]; the JVM tests pass a hand-driven [MainQueue], fake
 * fetches and recorded rules to the internal constructor.
 */
class GlanceController
internal constructor(
    private val settings: () -> Settings,
    private val newFetch: (SiteAddress) -> FetchJob,
    private val main: MainQueue,
    private val background: Executor,
    rules: Rules,
    now: () -> Long,
    private val release: () -> Unit,
) {
    /** A fetch handed to the fetch thread. Its answer is applied while [applies] holds. */
    private inner class Attempt(val ticket: GlanceModel.Ticket, val job: FetchJob) {
        var applies = true
        val deadline = Runnable { expire(this@Attempt) }
    }

    private var closed = false
    private var visible = false

    /** The fetch on the fetch thread, from the moment it is handed over until it answers. */
    private var running: Attempt? = null

    /** A fetch fell due while another was running: it starts when that one answers. */
    private var fetchWanted = false

    /** When the last fetch began, on [MainQueue.elapsedMs]; null before the first. */
    private var lastFetchStartMs: Long? = null

    val model = GlanceModel(settings(), rules, now)

    /** Called on the main thread after every change to [GlanceModel.state]. */
    var onChange: (() -> Unit)? = null

    private val fetchTick =
        object : Runnable {
            override fun run() {
                fetch()
                main.post(FETCH_INTERVAL_MS, this)
            }
        }

    private val reageTick =
        object : Runnable {
            override fun run() {
                model.reage()
                changed()
                main.post(REAGE_INTERVAL_MS, this)
            }
        }

    /**
     * The screen became visible (launch, or back from the background or from
     * Settings): pick up saved settings, re-age at once, fetch, and start
     * both timers.
     */
    fun start() {
        if (closed) return
        visible = true
        stopTimers()
        // Re-ages the last reading against the saved settings, or forgets it
        // when the address changed.
        model.updateSettings(settings())
        changed()
        main.post(0, fetchTick)
        main.post(REAGE_INTERVAL_MS, reageTick)
    }

    /**
     * The screen came to the front: re-age at once, which needs no fetch,
     * and fetch as well when the last fetch began [RESUME_FETCH_AFTER_MS] or
     * more ago. Nothing is fetched while the screen is not started.
     */
    fun resume() {
        if (closed) return
        model.reage()
        changed()
        val last = lastFetchStartMs
        if (visible && (last == null || main.elapsedMs() - last >= RESUME_FETCH_AFTER_MS)) {
            // This fetch now, and the next a full interval after it.
            main.remove(fetchTick)
            main.post(0, fetchTick)
        }
    }

    /** The screen is hidden: stop both timers, and cancel a fetch still running. */
    fun stop() {
        visible = false
        stopTimers()
        abandon()
    }

    /** The glance is gone for good: stop, and let the fetch thread go. */
    fun close() {
        closed = true
        stop()
        onChange = null
        release()
    }

    private fun stopTimers() {
        main.remove(fetchTick)
        main.remove(reageTick)
    }

    /** Cancels the running fetch and drops its answer, whenever it comes. */
    private fun abandon() {
        fetchWanted = false
        val attempt = running ?: return
        attempt.applies = false
        main.remove(attempt.deadline)
        attempt.job.cancel()
    }

    private fun fetch() {
        if (closed || !visible) return
        if (running != null) {
            // One fetch at a time: this one starts when the running one answers.
            fetchWanted = true
            return
        }
        val ticket = model.startFetch()
        if (ticket == null) {
            changed()
            return
        }
        // A configured site always parses; were it not to, that is a failed fetch.
        val site = ticket.settings.site
        if (site == null) {
            model.finishFetch(ticket, null)
            changed()
            return
        }
        val attempt = Attempt(ticket, newFetch(site))
        running = attempt
        lastFetchStartMs = main.elapsedMs()
        main.post(FETCH_DEADLINE_MS, attempt.deadline)
        background.execute {
            val body = attempt.job.run()
            main.post(0) { answered(attempt, body) }
        }
    }

    /** A fetch's thread is done: apply its answer if it is still wanted. */
    private fun answered(attempt: Attempt, body: ByteArray?) {
        if (running === attempt) running = null
        main.remove(attempt.deadline)
        if (attempt.applies && !closed) {
            attempt.applies = false
            model.finishFetch(attempt.ticket, body)
            changed()
        }
        if (fetchWanted) {
            fetchWanted = false
            fetch()
        }
    }

    /** A fetch ran past its deadline: cancel it and show it as failed now. */
    private fun expire(attempt: Attempt) {
        if (!attempt.applies || closed) return
        attempt.applies = false
        attempt.job.cancel()
        model.finishFetch(attempt.ticket, null)
        changed()
    }

    private fun changed() {
        onChange?.invoke()
    }

    companion object {
        const val FETCH_INTERVAL_MS = 60_000L
        const val REAGE_INTERVAL_MS = 30_000L

        /** The longest one fetch may take: twice the client's timeout, as on iOS. */
        const val FETCH_DEADLINE_MS = 2L * NightscoutClient.TIMEOUT_MS

        /** Coming back to the front fetches when the last fetch began this long ago or more. */
        const val RESUME_FETCH_AFTER_MS = 15_000L

        /** The app's controller: saved settings, the Keystore token, and the native rules. */
        fun create(context: Context): GlanceController {
            val app = context.applicationContext
            val settingsStore = SettingsStore(app)
            val tokenStore = TokenStore(app)
            val fetchThread = Executors.newSingleThreadExecutor()
            return GlanceController(
                settings = settingsStore::load,
                newFetch = { site -> ClientFetch(site, tokenStore) },
                main = HandlerQueue(Handler(Looper.getMainLooper())),
                background = fetchThread,
                rules = NativeRules,
                now = System::currentTimeMillis,
                release = { fetchThread.shutdownNow() },
            )
        }
    }
}

/**
 * The main thread's [Handler]. Its delays run on the uptime clock, which
 * stops while the phone is asleep, so a timer can come due late after a
 * sleep: the re-age when the screen comes back covers that. [elapsedMs] is
 * the clock that does count through sleep, so the resume rule measures real
 * time.
 */
private class HandlerQueue(private val handler: Handler) : MainQueue {
    override fun post(delayMs: Long, task: Runnable) {
        handler.postDelayed(task, delayMs)
    }

    override fun remove(task: Runnable) {
        handler.removeCallbacks(task)
    }

    override fun elapsedMs(): Long = SystemClock.elapsedRealtime()
}

/**
 * The app's fetch: a fresh [NightscoutClient], with the token read from
 * [TokenStore] on the fetch thread and never kept.
 */
private class ClientFetch(private val site: SiteAddress, private val tokens: TokenStore) :
    FetchJob {
    @Volatile private var client: NightscoutClient? = null
    @Volatile private var cancelled = false

    override fun run(): ByteArray? =
        try {
            val fresh = NightscoutClient(site, tokens.read())
            // Published before the flag is read, so a cancel either sees this
            // client or is seen here.
            client = fresh
            if (cancelled) null else fresh.fetchEntries()
        } catch (_: Exception) {
            // Any failure degrades to a failed fetch, never a crash: the model
            // then re-ages the last good reading with "Nightscout unreachable".
            null
        } finally {
            client = null
        }

    override fun cancel() {
        cancelled = true
        client?.cancel()
    }
}
