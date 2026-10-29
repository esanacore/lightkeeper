package com.esanacore.lightkeeper

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Paint
import android.os.Build
import android.util.TypedValue
import android.view.ContextThemeWrapper
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The screen itself: the first run shows the setup card and no number, the
 * headline is never under a system bar, STALE never shows a large number,
 * and the panel image is drawn at a whole-number scale.
 */
class GlanceScreenTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private var activity: Activity? = null

    /** Level words that must never appear before a reading exists. */
    private val levelWords = listOf("IN RANGE", "LOW", "HIGH", "URGENT", "STALE", "NO DATA")

    /** A site that never resolves (RFC 2606): configured, whatever the network does. */
    private val nowhere = "https://lightkeeper.invalid"

    @Before
    fun clearSettings() {
        for (file in listOf(SettingsStore.FILE, TokenStore.FILE)) {
            context.getSharedPreferences(file, Context.MODE_PRIVATE).edit().clear().commit()
        }
    }

    @After
    fun closeTheScreen() {
        activity?.let { instrumentation.runOnMainSync { it.finish() } }
        clearSettings()
    }

    private fun launch(): Activity {
        val intent =
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val launched = instrumentation.startActivitySync(intent)
        instrumentation.waitForIdleSync()
        activity = launched
        return launched
    }

    /** Every visible TextView at or under [view]. */
    private fun visibleTexts(view: View): List<TextView> {
        if (view.visibility != View.VISIBLE) return emptyList()
        val found = mutableListOf<TextView>()
        if (view is TextView) found += view
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) found += visibleTexts(view.getChildAt(i))
        }
        return found
    }

    private fun lines(reading: Reading?, ageMs: Long, error: Boolean = false): List<String> =
        NativeRules.lines(reading, Spec.NOW_MS + ageMs, Thresholds(), error)

    /** A glance laid out off screen at a phone's width, in the app's theme. */
    private fun glanceFor(lines: List<String>): GlanceView {
        var glance: GlanceView? = null
        instrumentation.runOnMainSync {
            val view = GlanceView(ContextThemeWrapper(context, R.style.Theme_Lightkeeper))
            view.bind(Presentation.of(lines))
            val width = View.MeasureSpec.makeMeasureSpec(1080, View.MeasureSpec.EXACTLY)
            val height = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
            view.measure(width, height)
            view.layout(0, 0, view.measuredWidth, view.measuredHeight)
            glance = view
        }
        return glance!!
    }

    @Test
    fun testFirstRunShowsTheSetupCardWithNoNumberAndNoLevelWord() {
        val screen = launch()
        val root = screen.findViewById<View>(R.id.lk_root)
        assertEquals(View.VISIBLE, screen.findViewById<View>(R.id.lk_setup_card).visibility)
        assertEquals(View.GONE, screen.findViewById<View>(R.id.lk_status_area).visibility)
        assertEquals(View.GONE, screen.findViewById<View>(R.id.lk_panel).visibility)
        val texts = visibleTexts(root).map { it.text.toString() }
        assertTrue(texts.contains(context.getString(R.string.setup_title)))
        for (text in texts) {
            assertFalse("a digit on the first-run screen: $text", text.any { it.isDigit() })
            for (word in levelWords) {
                val found = Regex("\\b$word\\b").containsMatchIn(text)
                assertFalse("a level word on the first-run screen: $text", found)
            }
        }
    }

    @Test
    fun testTheHeadlineIsNotUnderTheSystemBars() {
        SettingsStore(context).save(Settings(nightscoutUrl = nowhere))
        val screen = launch()
        val mark = screen.findViewById<View>(R.id.lk_status_mark)
        assertEquals(View.VISIBLE, screen.findViewById<View>(R.id.lk_status_area).visibility)
        val insets = screen.window.decorView.rootWindowInsets
        val bars = EdgeToEdge.barInsets(insets)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val system = insets.getInsets(WindowInsets.Type.systemBars())
            assertTrue("the status bar has height", system.top > 0)
        }
        val where = IntArray(2)
        mark.getLocationOnScreen(where)
        val window = IntArray(2)
        screen.window.decorView.getLocationOnScreen(window)
        val top = where[1] - window[1]
        val bottom = top + mark.height
        val lowest = screen.window.decorView.height - bars.bottom
        assertTrue(mark.height > 0)
        assertTrue("headline top $top is under the status bar (${bars.top})", top >= bars.top)
        assertTrue("headline bottom $bottom is under the navigation bar", bottom <= lowest)
        assertTrue(where[0] - window[0] >= bars.left)
    }

    @Test
    fun testStaleShowsNoLargeNumberAndStrikesItsLastLine() {
        val body = "[{\"type\":\"sgv\",\"sgv\":112,\"date\":${Spec.NOW_MS},\"direction\":\"Flat\"}]"
        val reading = NativeRules.readBody(body.toByteArray()).reading
        val stale = lines(reading, ageMs = 40 * 60_000L)
        assertEquals("STALE - DO NOT TRUST", stale[0])
        val glance = glanceFor(stale)
        val headline = visibleTexts(glance.findViewById(R.id.lk_status_mark)).single()
        assertEquals("STALE - DO NOT TRUST", headline.text.toString())
        assertEquals(View.GONE, glance.findViewById<View>(R.id.lk_hero).visibility)
        val struck = glance.findViewById<TextView>(R.id.lk_struck_line)
        assertEquals("last: 112 mg/dL ->", struck.text.toString())
        assertTrue(struck.paintFlags and Paint.STRIKE_THRU_TEXT_FLAG != 0)
        val age = glance.findViewById<TextView>(R.id.lk_age_line)
        for (text in visibleTexts(glance)) {
            if (text === headline) continue
            // The banner is the largest text, and the old value is never above the age.
            val size = text.textSize
            assertTrue("${text.text} is not smaller than the banner", size < headline.textSize)
            if (text.text.any { it.isDigit() }) {
                assertTrue("${text.text} is larger than the age line", size <= age.textSize)
            }
        }
        assertEquals(stale.joinToString(". "), glance.contentDescription)
    }

    @Test
    fun testNoDataShowsNoNumberAndItsBannerIsTheLargestText() {
        val glance = glanceFor(lines(null, ageMs = 0, error = true))
        val headline = visibleTexts(glance.findViewById(R.id.lk_status_mark)).single()
        assertEquals("NO DATA", headline.text.toString())
        val placeholder = glance.findViewById<TextView>(R.id.lk_placeholder)
        assertEquals("--", placeholder.text.toString())
        for (text in visibleTexts(glance)) {
            if (text === headline) continue
            assertFalse(text.text.toString(), text.text.any { it.isDigit() })
            assertTrue(text.text.toString(), text.textSize < headline.textSize)
        }
    }

    @Test
    fun testAFreshNumberIsTheHeroAndTheChipIsAtLeastTwentySpBold() {
        val reading = Reading(mgdl = 112, timestampMs = Spec.NOW_MS, trendCode = 3)
        val glance = glanceFor(lines(reading, ageMs = 3 * 60_000L))
        val chip = visibleTexts(glance.findViewById(R.id.lk_status_mark)).single()
        assertEquals("IN RANGE", chip.text.toString())
        val metrics = context.resources.displayMetrics
        val twentySp = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 20f, metrics)
        assertTrue(chip.textSize >= twentySp - 0.5f)
        assertTrue(chip.typeface.isBold)
        val hero = glance.findViewById<View>(R.id.lk_hero)
        assertEquals(View.VISIBLE, hero.visibility)
        val digits = visibleTexts(hero).first { it.text.toString() == "112" }
        assertTrue(digits.textSize > chip.textSize)
        val age = glance.findViewById<TextView>(R.id.lk_age_line)
        assertEquals("3 min ago", age.text.toString())
    }

    @Test
    fun testTheUrgentBandIsNeverShorterThanTheNumber() {
        val reading = Reading(mgdl = 50, timestampMs = Spec.NOW_MS, trendCode = 6)
        val glance = glanceFor(lines(reading, ageMs = 0))
        val band = glance.findViewById<View>(R.id.lk_status_mark)
        val hero = glance.findViewById<View>(R.id.lk_hero)
        val digits = visibleTexts(hero).first { it.text.toString() == "50" }
        assertTrue(band.height >= digits.textSize.toInt())
        assertEquals(glance.width, band.width)
    }

    @Test
    fun testThePanelIsDrawnAtAWholeNumberScale() {
        SettingsStore(context).save(Settings(nightscoutUrl = nowhere))
        val screen = launch()
        val panel = screen.findViewById<PanelView>(R.id.lk_panel)
        assertNotNull(panel)
        assertEquals(View.VISIBLE, panel.visibility)
        assertTrue("scale ${panel.scale}", panel.scale >= 1)
        // Whole screen pixels per panel pixel, and the whole image on screen.
        assertTrue(MainActivity.PANEL_WIDTH * panel.scale <= panel.width)
        assertTrue(MainActivity.PANEL_HEIGHT * panel.scale <= panel.height)
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO, panel.importantForAccessibility)
    }

    @Test
    fun testAPanelTooNarrowForItsImageShowsNothingRatherThanACrop() {
        val width = MainActivity.PANEL_WIDTH
        val height = MainActivity.PANEL_HEIGHT
        val frame = 2 * (Logbook.dp(context, 2) + Logbook.dp(context, 8))
        val reading = Reading(mgdl = 112, timestampMs = Spec.NOW_MS, trendCode = 3)
        val rows = NativeRules.panel(lines(reading, ageMs = 0), width, height, "12:00")
        assertNotNull(rows)
        var measured = emptyList<Pair<Int, Int>>()
        instrumentation.runOnMainSync {
            val panel = PanelView(ContextThemeWrapper(context, R.style.Theme_Lightkeeper))
            panel.show(rows, width, height)
            val unbounded = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
            measured =
                listOf(width + frame - 1, width + frame, 2 * width + frame).map { across ->
                    val spec = View.MeasureSpec.makeMeasureSpec(across, View.MeasureSpec.EXACTLY)
                    panel.measure(spec, unbounded)
                    panel.scale to panel.measuredHeight
                }
        }
        // One pixel short of the whole image and its margin: no room taken, nothing drawn.
        assertEquals(0 to 0, measured[0])
        assertEquals(1 to height + frame, measured[1])
        assertEquals(2 to 2 * height + frame, measured[2])
    }
}
