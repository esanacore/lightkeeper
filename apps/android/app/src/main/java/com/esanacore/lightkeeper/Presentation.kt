package com.esanacore.lightkeeper

/**
 * How the phone arranges one screen of lines: which shape carries the status
 * word, what the hero is, and which line goes where. A port of the iOS
 * ScreenPresentation (Presentation.swift), kept out of the views so the JVM
 * tests check it against every display vector.
 *
 * Every word on the glance is a vector line, verbatim. The one exception is
 * the fresh number, which the view draws in parts (digits, arrow, unit) cut
 * from the vector's value line, never rebuilt from the reading.
 *
 * The shape is keyed by the headline alone, like the panel's treatment and
 * the status table in assets/brand/tokens.json, so a headline nobody planned
 * for gets the most cautious shape: the NO DATA frame, with no number.
 *
 * Safety rules this enforces (HAZ-001, HAZ-008):
 * - STALE has no hero: no large number, no separate arrow, no unit. Its
 *   `last:` line is shown verbatim, struck through, at body size.
 * - NO DATA and an unknown headline never show a number.
 * - The status word comes first in reading order.
 */
data class Presentation(
    /** The lines as rendered: the panel and the accessibility text come from these. */
    val lines: List<String>,
    /** The status word: the vector headline, verbatim. */
    val word: String,
    val tone: Tone,
    val banner: Banner,
    val hero: Hero,
    /** [PLACEHOLDER] under the NO DATA frame; null on every other screen. */
    val placeholder: String?,
    /** STALE's `last:` line, struck; null on every other screen. */
    val struckLine: String?,
    /** The age line, in Ink; null where the screen has none (NO DATA). */
    val age: String?,
    /** The remaining lines, in order ("Confirm on primary device", "Nightscout unreachable"). */
    val context: List<String>,
) {
    /** The status colour family, named by its colour id in tokens.json. */
    enum class Tone(val token: String) {
        IN_RANGE("in-range"),
        LOW("low"),
        HIGH("high"),
        STALE("stale"),
    }

    /** The shape that carries the status word. */
    enum class Banner {
        /** IN RANGE, LOW and HIGH: the word in Ink on its tint, in a status-colour border. */
        CHIP,

        /** URGENT LOW and URGENT HIGH: a full-width Ink band with a status-colour rule. */
        URGENT,

        /** STALE: an Ink band with a hatched margin, and the `last:` line struck. */
        STALE,

        /** NO DATA and any unknown headline: a dashed frame and no number. */
        NO_DATA,
    }

    /** The largest thing on a fresh screen. */
    sealed interface Hero {
        /** A fresh number, cut from the value line "`digits` `unit` `arrow`". */
        data class Number(val digits: String, val arrow: String, val unit: String) : Hero

        /** A fresh value line that is not a plain number (the sensor sentinels), verbatim. */
        data class Word(val text: String) : Hero

        /** No hero: STALE, NO DATA and any unknown headline. */
        data object None : Hero
    }

    /** What TalkBack reads for the whole status area: the lines, in order. */
    val accessibilityText: String
        get() = lines.joinToString(LINE_SEPARATOR)

    companion object {
        /** What NO DATA shows where a number would be. It has no digit in it. */
        const val PLACEHOLDER = "--"

        /** STALE's headline, as the rules write it. */
        const val STALE_HEADLINE = "STALE - DO NOT TRUST"

        /** The unit in a vector value line. */
        const val UNIT = "mg/dL"

        /** Between lines in [accessibilityText], so each is read as its own phrase. */
        const val LINE_SEPARATOR = ". "

        /** The ASCII arrows the rules write, as in glucose_rules.cpp's trend table. */
        val ARROWS = setOf("^^", "^", "/", "->", "\\", "v", "vv", "?")

        /** The arrangement of [lines] (lines[0] is the headline). */
        fun of(lines: List<String>): Presentation {
            val headline = lines.firstOrNull().orEmpty()
            val (banner, tone) = shape(headline)
            val rest = lines.drop(1)
            var hero: Hero = Hero.None
            var struck: String? = null
            var age: String? = null
            val context: List<String>
            when (banner) {
                Banner.CHIP, Banner.URGENT -> {
                    // Fresh: value, then age, then context (panel_layout's roles).
                    rest.firstOrNull()?.let { hero = hero(it) }
                    age = rest.getOrNull(1)
                    context = rest.drop(2)
                }
                Banner.STALE -> {
                    struck = rest.firstOrNull()
                    age = rest.getOrNull(1)
                    context = rest.drop(2)
                }
                Banner.NO_DATA -> context = rest
            }
            return Presentation(
                lines = lines,
                word = headline,
                tone = tone,
                banner = banner,
                hero = hero,
                placeholder = if (banner == Banner.NO_DATA) PLACEHOLDER else null,
                struckLine = struck,
                age = age,
                context = context,
            )
        }

        /**
         * The shape and colour family for a headline. Mirrors the status
         * table in assets/brand/tokens.json (tests/test_android.py holds the
         * two together); anything else is treated as NO DATA.
         */
        fun shape(headline: String): Pair<Banner, Tone> =
            when (headline) {
                "IN RANGE" -> Banner.CHIP to Tone.IN_RANGE
                "LOW" -> Banner.CHIP to Tone.LOW
                "HIGH" -> Banner.CHIP to Tone.HIGH
                "URGENT LOW" -> Banner.URGENT to Tone.LOW
                "URGENT HIGH" -> Banner.URGENT to Tone.HIGH
                STALE_HEADLINE -> Banner.STALE to Tone.STALE
                else -> Banner.NO_DATA to Tone.STALE
            }

        /**
         * The phone glyph for a vector arrow, for display beside the number
         * only, as the iOS app draws it (Trend.symbol). The view falls back
         * to the ASCII arrow itself when the font has no such glyph.
         */
        fun phoneArrow(arrow: String): String =
            when (arrow) {
                "^^" -> "⇈"
                "^" -> "↑"
                "/" -> "↗"
                "->" -> "→"
                "\\" -> "↘"
                "v" -> "↓"
                "vv" -> "⇊"
                else -> arrow
            }

        /** A number hero when the value line is exactly "<digits> mg/dL <arrow>"; else the line. */
        fun hero(value: String): Hero {
            val parts = value.split(" ")
            val digits = parts.firstOrNull().orEmpty()
            val isNumber =
                parts.size == 3 &&
                    digits.isNotEmpty() &&
                    digits.all { it in '0'..'9' } &&
                    parts[1] == UNIT &&
                    parts[2] in ARROWS
            return if (isNumber) Hero.Number(digits, parts[2], parts[1]) else Hero.Word(value)
        }
    }
}
