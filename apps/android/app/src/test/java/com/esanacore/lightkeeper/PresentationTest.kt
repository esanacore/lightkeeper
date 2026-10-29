package com.esanacore.lightkeeper

import com.esanacore.lightkeeper.Presentation.Banner
import com.esanacore.lightkeeper.Presentation.Hero
import com.esanacore.lightkeeper.Presentation.Tone
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The glance anatomy, held to every display vector: each line appears once,
 * verbatim, in its place; STALE never has a hero; NO DATA never has a number.
 */
class PresentationTest {
    @Test
    fun testEveryVectorLineAppearsOnceVerbatimInItsPlace() {
        for ((name, lines) in Repo.displayLines) {
            val p = Presentation.of(lines)
            assertEquals(name, lines, p.lines)
            assertEquals(name, lines[0], p.word)
            val shown = mutableListOf(p.word)
            when (val hero = p.hero) {
                is Hero.Number -> shown += "${hero.digits} ${hero.unit} ${hero.arrow}"
                is Hero.Word -> shown += hero.text
                Hero.None -> Unit
            }
            p.struckLine?.let { shown += it }
            p.age?.let { shown += it }
            shown += p.context
            assertEquals(name, lines, shown)
        }
    }

    @Test
    fun testStaleNeverHasAHeroAndItsLastLineIsStruck() {
        val stale = Repo.displayLines.filterValues { it[0] == "STALE - DO NOT TRUST" }
        assertTrue("the vectors have STALE screens", stale.isNotEmpty())
        for ((name, lines) in stale) {
            val p = Presentation.of(lines)
            assertEquals(name, Banner.STALE, p.banner)
            assertEquals(name, Hero.None, p.hero)
            assertEquals(name, lines[1], p.struckLine)
            assertTrue(name, p.struckLine!!.startsWith("last: "))
            assertEquals(name, lines[2], p.age)
            assertNull(name, p.placeholder)
        }
    }

    @Test
    fun testNoDataNeverShowsANumber() {
        val noData = Repo.displayLines.filterValues { it[0] == "NO DATA" }
        assertTrue("the vectors have NO DATA screens", noData.isNotEmpty())
        for ((name, lines) in noData) {
            val p = Presentation.of(lines)
            assertEquals(name, Banner.NO_DATA, p.banner)
            assertEquals(name, Hero.None, p.hero)
            assertEquals(name, "--", p.placeholder)
            assertNull(name, p.age)
            val shown = listOf(p.word, p.placeholder!!) + p.context
            assertFalse(name, shown.any { line -> line.any { it.isDigit() } })
        }
    }

    @Test
    fun testFreshScreensHaveTheNumberAsTheHero() {
        val levels = setOf("IN RANGE", "LOW", "HIGH", "URGENT LOW", "URGENT HIGH")
        val fresh = Repo.displayLines.filterValues { it[0] in levels }
        assertTrue(fresh.isNotEmpty())
        for ((name, lines) in fresh) {
            val p = Presentation.of(lines)
            assertTrue(name, p.hero != Hero.None)
            assertEquals(name, lines[2], p.age)
            assertNull(name, p.struckLine)
            assertNull(name, p.placeholder)
        }
        val number = Presentation.of(Repo.displayLines.getValue("in_range_flat")).hero
        assertEquals(Hero.Number("112", "->", "mg/dL"), number)
        val sentinel = Presentation.of(Repo.displayLines.getValue("sensor_low_sentinel")).hero
        assertEquals(Hero.Word("LOW (<40)"), sentinel)
    }

    @Test
    fun testTheShapeFollowsTheHeadlineAndAnUnknownOneGetsTheMostCautious() {
        assertEquals(Banner.CHIP to Tone.IN_RANGE, Presentation.shape("IN RANGE"))
        assertEquals(Banner.CHIP to Tone.LOW, Presentation.shape("LOW"))
        assertEquals(Banner.CHIP to Tone.HIGH, Presentation.shape("HIGH"))
        assertEquals(Banner.URGENT to Tone.LOW, Presentation.shape("URGENT LOW"))
        assertEquals(Banner.URGENT to Tone.HIGH, Presentation.shape("URGENT HIGH"))
        assertEquals(Banner.STALE to Tone.STALE, Presentation.shape("STALE - DO NOT TRUST"))
        assertEquals(Banner.NO_DATA to Tone.STALE, Presentation.shape("NO DATA"))
        for (unknown in listOf("", "STALE", "in range", "LOW (<40)", "WHAT")) {
            assertEquals(unknown, Banner.NO_DATA to Tone.STALE, Presentation.shape(unknown))
        }
        // An unknown headline never shows its lines as a number.
        val odd = Presentation.of(listOf("SOMETHING NEW", "112 mg/dL ->", "3 min ago"))
        assertEquals(Hero.None, odd.hero)
        assertEquals("--", odd.placeholder)
        assertEquals(listOf("112 mg/dL ->", "3 min ago"), odd.context)
        assertEquals(Banner.NO_DATA, Presentation.of(emptyList()).banner)
    }

    @Test
    fun testTheToneTokensAreTheBrandColorIds() {
        assertEquals(listOf("in-range", "low", "high", "stale"), Tone.entries.map { it.token })
    }

    @Test
    fun testOnlyAnExactValueLineBecomesANumber() {
        assertEquals(Hero.Number("70", "\\", "mg/dL"), Presentation.hero("70 mg/dL \\"))
        assertEquals(Hero.Number("250", "^^", "mg/dL"), Presentation.hero("250 mg/dL ^^"))
        val notNumbers =
            listOf(
                "HIGH (>400)",
                "112 mg/dL",
                "112 mg/dl ->",
                "x12 mg/dL ->",
                " mg/dL ->",
                "112 mg/dL -> x",
                "112 mg/dL =>",
            )
        for (line in notNumbers) {
            assertEquals(line, Hero.Word(line), Presentation.hero(line))
        }
    }

    @Test
    fun testEveryArrowHasAPhoneGlyphAndUnknownStaysItself() {
        val glyphs = Presentation.ARROWS.associateWith(Presentation::phoneArrow)
        assertEquals("⇈", glyphs["^^"])
        assertEquals("↑", glyphs["^"])
        assertEquals("↗", glyphs["/"])
        assertEquals("→", glyphs["->"])
        assertEquals("↘", glyphs["\\"])
        assertEquals("↓", glyphs["v"])
        assertEquals("⇊", glyphs["vv"])
        assertEquals("?", glyphs["?"])
        assertEquals(8, glyphs.values.toSet().size)
    }

    @Test
    fun testTheAccessibilityTextIsTheLinesInOrder() {
        val lines = Repo.displayLines.getValue("stale_at_16_minutes")
        assertEquals(lines.joinToString(". "), Presentation.of(lines).accessibilityText)
        assertEquals(
            "IN RANGE. 112 mg/dL ->. 3 min ago",
            Presentation.of(Repo.displayLines.getValue("in_range_flat")).accessibilityText,
        )
    }
}
