package com.esanacore.lightkeeper

import java.util.concurrent.Executor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The controller's timing, on a main queue and a fetch thread driven by hand
 * in virtual time: the fetch at once and every 60 seconds, the re-age every
 * 30 seconds with no fetch (HAZ-008), the fetch on resume only after 15
 * seconds, one fetch at a time, the 20-second deadline that shows a hung
 * fetch as "Nightscout unreachable" (HAZ-002), and nothing at all once the
 * screen is hidden or gone. The rules are a recorder; they run through JNI in
 * the instrumented tests.
 */
class GlanceControllerTest {
    private val site = "https://ns.example.com"
    private val reading = Reading(mgdl = 112, timestampMs = WALL_MS, trendCode = 3)

    /** The main thread: tasks run in time order, and in the order posted at the same time. */
    private class Queue : MainQueue {
        var nowMs = 0L
            private set

        private val tasks = mutableListOf<Pair<Long, Runnable>>()

        override fun post(delayMs: Long, task: Runnable) {
            tasks += (nowMs + delayMs) to task
        }

        override fun remove(task: Runnable) {
            tasks.removeAll { it.second === task }
        }

        override fun elapsedMs(): Long = nowMs

        /** How many runs are waiting. */
        val pending: Int
            get() = tasks.size

        /** The times the waiting runs are due, soonest first. */
        val dueTimes: List<Long>
            get() = tasks.map { it.first }.sorted()

        /** Runs everything due up to [toMs], moving the clock to each in turn, then to [toMs]. */
        fun advanceTo(toMs: Long) {
            while (true) {
                val next = tasks.filter { it.first <= toMs }.minByOrNull { it.first } ?: break
                tasks.remove(next)
                nowMs = next.first
                next.second.run()
            }
            nowMs = toMs
        }

        fun runDue() = advanceTo(nowMs)
    }

    /** The fetch thread: runs a handed-over fetch when the test says, or at once. */
    private class FetchThread(var immediate: Boolean) : Executor {
        private val waiting = ArrayDeque<Runnable>()

        override fun execute(command: Runnable) {
            if (immediate) command.run() else waiting.addLast(command)
        }

        val queued: Int
            get() = waiting.size

        /** The oldest handed-over fetch finishes on the fetch thread. */
        fun finishNext() = waiting.removeFirst().run()
    }

    /** A fetch that answers [answer] when its thread runs it, and records a cancel. */
    private class Job(val site: SiteAddress) : FetchJob {
        var answer: ByteArray? = "list".toByteArray()
        var cancelled = false
        var ran = false

        override fun run(): ByteArray? {
            ran = true
            return answer
        }

        override fun cancel() {
            cancelled = true
        }
    }

    /** Writes the reading, the time and the error flag as the "lines". */
    private class Recorder(private val reading: Reading) : Rules {
        var asked = 0

        override fun readBody(body: ByteArray): BodyReading =
            when (String(body)) {
                "list" -> BodyReading(isList = true, reading = reading)
                else -> BodyReading(isList = false, reading = null)
            }

        override fun lines(
            reading: Reading?,
            nowMs: Long,
            thresholds: Thresholds,
            fetchError: Boolean,
        ): List<String> {
            asked += 1
            return listOf("mgdl=${reading?.mgdl}", "now=$nowMs", "error=$fetchError")
        }
    }

    private val queue = Queue()
    private val rules = Recorder(reading)
    private val jobs = mutableListOf<Job>()
    private var saved = Settings(nightscoutUrl = site)
    private var released = false
    private var changes = 0

    private fun controller(immediate: Boolean = true): Pair<GlanceController, FetchThread> {
        val thread = FetchThread(immediate)
        val glance =
            GlanceController(
                settings = { saved },
                newFetch = { site -> Job(site).also { jobs += it } },
                main = queue,
                background = thread,
                rules = rules,
                now = { WALL_MS + queue.nowMs },
                release = { released = true },
            )
        glance.onChange = { changes += 1 }
        return glance to thread
    }

    private val GlanceController.drawnAt: Long
        get() = model.state.drawnAtMs - WALL_MS

    @Test
    fun testStartFetchesAtOnceAndReagesThirtySecondsLater() {
        val (glance, _) = controller()
        glance.start()
        assertTrue("no fetch before the queue runs", jobs.isEmpty())
        assertEquals(listOf(0L, GlanceController.REAGE_INTERVAL_MS), queue.dueTimes)
        queue.runDue()
        assertEquals(1, jobs.size)
        assertEquals(site, jobs[0].site.toString())
        assertEquals(listOf("mgdl=112", "now=$WALL_MS", "error=false"), glance.model.state.lines)
        // The next fetch a minute on, the first re-age at 30 seconds.
        assertEquals(listOf(30_000L, 60_000L), queue.dueTimes)
        queue.advanceTo(29_999L)
        assertEquals(0L, glance.drawnAt)
        queue.advanceTo(30_000L)
        assertEquals(30_000L, glance.drawnAt)
        assertEquals(1, jobs.size)
        queue.advanceTo(60_000L)
        assertEquals(2, jobs.size)
    }

    @Test
    fun testEveryReageTickReagesWithNoFetch() {
        val (glance, _) = controller()
        glance.start()
        queue.runDue()
        for (tick in 1..40) {
            val at = tick * GlanceController.REAGE_INTERVAL_MS
            val before = jobs.size
            queue.advanceTo(at)
            assertEquals("re-aged at $at", at, glance.drawnAt)
            // A fetch only on the minute; the half-minute ticks only re-age.
            val fetched = if (at % GlanceController.FETCH_INTERVAL_MS == 0L) 1 else 0
            assertEquals("fetches at $at", before + fetched, jobs.size)
        }
        assertEquals(21, jobs.size)
    }

    @Test
    fun testTheScreenAgesWhileNoFetchAnswers() {
        // Nightscout hangs from the start: the 30-second re-age still runs
        // every time, and every fetch past its deadline is shown as failed.
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        for (tick in 1..20) {
            val at = tick * GlanceController.REAGE_INTERVAL_MS
            queue.advanceTo(at)
            assertEquals(at, glance.drawnAt)
        }
        assertTrue(glance.model.state.fetchError)
        assertEquals(1, thread.queued)
    }

    @Test
    fun testResumeReagesAndFetchesOnlyFifteenSecondsAfterTheLastFetchBegan() {
        val (glance, _) = controller()
        glance.start()
        glance.resume()
        queue.runDue()
        assertEquals("start and resume together make one fetch", 1, jobs.size)

        queue.advanceTo(14_999L)
        glance.resume()
        assertEquals("resume re-ages at once", 14_999L, glance.drawnAt)
        queue.runDue()
        assertEquals(1, jobs.size)

        queue.advanceTo(GlanceController.RESUME_FETCH_AFTER_MS)
        glance.resume()
        queue.runDue()
        assertEquals(2, jobs.size)
        // The next timed fetch is a full interval after the one on resume.
        queue.advanceTo(15_000L + 59_999L)
        assertEquals(2, jobs.size)
        queue.advanceTo(15_000L + 60_000L)
        assertEquals(3, jobs.size)
    }

    @Test
    fun testOnlyOneFetchRunsAtATimeAndTheOneDueMeanwhileFollowsIt() {
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        assertEquals(1, jobs.size)

        // Due again while the first is still running: no second fetch yet.
        queue.advanceTo(15_000L)
        glance.resume()
        queue.runDue()
        assertEquals(1, jobs.size)
        assertEquals(1, thread.queued)

        // The first answers in time; the one that fell due starts right after.
        thread.finishNext()
        queue.runDue()
        assertEquals("mgdl=112", glance.model.state.lines[0])
        assertFalse(glance.model.state.fetchError)
        assertEquals(2, jobs.size)
        assertEquals(1, thread.queued)
        assertFalse(jobs[0].cancelled)
    }

    @Test
    fun testAFetchPastItsDeadlineIsCancelledAndShownAsUnreachable() {
        assertEquals(20_000L, GlanceController.FETCH_DEADLINE_MS)
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        thread.finishNext()
        queue.runDue()
        assertEquals(listOf("mgdl=112", "now=$WALL_MS", "error=false"), glance.model.state.lines)

        // The next fetch hangs: until its deadline the screen shows no error.
        queue.advanceTo(60_000L)
        val hung = jobs[1]
        queue.advanceTo(60_000L + 19_999L)
        assertFalse(glance.model.state.fetchError)
        assertFalse(hung.cancelled)

        queue.advanceTo(60_000L + 20_000L)
        assertTrue(hung.cancelled)
        val failed = glance.model.state
        assertTrue(failed.fetchError)
        assertEquals(listOf("mgdl=112", "now=${WALL_MS + 80_000L}", "error=true"), failed.lines)
        assertEquals(WALL_MS + 80_000L, failed.offlineSinceMs)
        assertEquals(WALL_MS + 80_000L, failed.lastRefreshMs)

        // Its answer, when the thread finally comes back, is dropped.
        thread.finishNext()
        queue.runDue()
        assertEquals(failed, glance.model.state)
    }

    @Test
    fun testAFetchDueBehindAHungOneStartsWhenTheHungOneReturns() {
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        // The first fetch hangs past its deadline and the next minute's tick.
        queue.advanceTo(60_000L)
        assertTrue(jobs[0].cancelled)
        assertTrue(glance.model.state.fetchError)
        assertEquals(1, jobs.size)
        // The stuck thread comes back: the fetch that fell due runs now, and answers.
        thread.finishNext()
        queue.runDue()
        assertEquals(2, jobs.size)
        thread.finishNext()
        queue.runDue()
        assertFalse(glance.model.state.fetchError)
        assertEquals("mgdl=112", glance.model.state.lines[0])
    }

    @Test
    fun testStopCancelsTheFetchLeavesNothingScheduledAndDropsTheLateAnswer() {
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        val shown = glance.model.state
        glance.stop()
        assertTrue(jobs[0].cancelled)
        assertEquals("nothing is scheduled while hidden", 0, queue.pending)

        // The cancelled fetch's thread returns with an answer: it is dropped.
        thread.finishNext()
        queue.runDue()
        assertEquals(shown, glance.model.state)
        assertEquals(0, queue.pending)

        // Ten minutes hidden: no fetch, no re-age, nothing redrawn.
        val changesBefore = changes
        queue.advanceTo(10 * 60_000L)
        assertEquals(changesBefore, changes)
        assertEquals(0L, glance.drawnAt)
        assertEquals(1, jobs.size)

        // A resume with no start (never in the app) re-ages, and still never fetches.
        glance.resume()
        queue.runDue()
        assertEquals(10 * 60_000L, glance.drawnAt)
        assertEquals(1, jobs.size)
        assertEquals(0, queue.pending)
    }

    @Test
    fun testComingBackAfterAStopStartsAgainAtOnce() {
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        glance.stop()
        thread.finishNext()
        queue.runDue()
        queue.advanceTo(5 * 60_000L)
        glance.start()
        queue.runDue()
        assertEquals(2, jobs.size)
        assertEquals(5 * 60_000L, glance.drawnAt)
        thread.finishNext()
        queue.runDue()
        assertEquals("mgdl=112", glance.model.state.lines[0])
        assertEquals(WALL_MS + 5 * 60_000L, glance.model.state.lastRefreshMs)
    }

    @Test
    fun testStartPicksUpTheSavedSettings() {
        val (glance, _) = controller()
        glance.start()
        queue.runDue()
        assertEquals("mgdl=112", glance.model.state.lines[0])
        glance.stop()
        // Settings saved a new site: the old site's reading is forgotten.
        saved = Settings(nightscoutUrl = "https://other.example.com")
        glance.start()
        assertEquals("mgdl=null", glance.model.state.lines[0])
        queue.runDue()
        assertEquals("https://other.example.com", jobs.last().site.toString())
    }

    @Test
    fun testFirstRunMakesNoFetchAtAnyTime() {
        saved = Settings()
        val (glance, _) = controller()
        glance.start()
        glance.resume()
        queue.advanceTo(10 * 60_000L)
        assertTrue(jobs.isEmpty())
        assertFalse(glance.model.state.configured)
        assertEquals("mgdl=null", glance.model.state.lines[0])
    }

    @Test
    fun testCloseReleasesTheFetchThreadAndNothingRunsAfterIt() {
        val (glance, thread) = controller(immediate = false)
        glance.start()
        queue.runDue()
        val shown = glance.model.state
        glance.close()
        assertTrue(released)
        assertTrue(jobs[0].cancelled)
        assertNull(glance.onChange)
        assertEquals(0, queue.pending)

        thread.finishNext()
        glance.start()
        glance.resume()
        queue.advanceTo(10 * 60_000L)
        assertEquals(shown, glance.model.state)
        assertEquals(1, jobs.size)
        assertEquals(0, queue.pending)
    }

    @Test
    fun testEveryChangeIsReported() {
        val (glance, _) = controller()
        glance.start()
        assertEquals("start redraws at once", 1, changes)
        queue.runDue()
        assertEquals("the answer redraws", 2, changes)
        queue.advanceTo(30_000L)
        assertEquals("the re-age redraws", 3, changes)
        glance.resume()
        assertEquals("resume redraws", 4, changes)
    }

    private companion object {
        /** The wall clock when the virtual clock reads zero. */
        const val WALL_MS = 1_792_324_800_000L
    }
}
