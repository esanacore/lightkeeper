package com.esanacore.lightkeeper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * res/values/colors.xml and res/values-night/colors.xml mirror
 * assets/brand/tokens.json: one lk_ color per token, light and dark, plus
 * three pairs taken from two tokens. tests/test_android.py checks the same
 * thing in the repository's Full suite. If this fails, change tokens.json
 * first, then mirror it here; never the other way round.
 */
class ColorDriftTest {
    /** Colors drawn from two tokens: (light token, dark token). */
    private val pairs =
        mapOf(
            "lk_panel_paper" to ("paper" to "night-paper"),
            "lk_panel_ink" to ("ink" to "night-ink"),
            "lk_hard_shadow" to ("beam-soft" to "line"),
        )

    @Suppress("UNCHECKED_CAST")
    private val tokens: Map<String, Map<String, Any?>> by lazy {
        val all = MiniJson.parse(Repo.text("assets/brand/tokens.json")) as Map<String, Any?>
        all["color"] as Map<String, Map<String, Any?>>
    }

    private fun colors(folder: String): Map<String, String> {
        val xml = Repo.text("apps/android/app/src/main/res/$folder/colors.xml")
        val found = Regex("""<color name="(\w+)">([^<]*)</color>""").findAll(xml)
        return found.associate { it.groupValues[1] to it.groupValues[2] }
    }

    /** Every lk_ color a theme must define, with its tokens.json value. */
    private fun expected(theme: String): Map<String, String> {
        val mirrored =
            tokens.entries.associate { (id, token) ->
                "lk_" + id.replace('-', '_') to token[theme] as String
            }
        val drawn =
            pairs.mapValues { (_, ids) ->
                val id = if (theme == "light") ids.first else ids.second
                tokens.getValue(id)[theme] as String
            }
        return mirrored + drawn
    }

    @Test
    fun testEveryLightColorEqualsTokensJson() {
        assertEquals(expected("light"), colors("values"))
    }

    @Test
    fun testEveryDarkColorEqualsTokensJson() {
        assertEquals(expected("dark"), colors("values-night"))
    }

    @Test
    fun testThePanelUsesNightPaperInDarkMode() {
        assertEquals(tokens["night-paper"]!!["dark"], colors("values-night")["lk_panel_paper"])
        assertEquals(tokens["night-ink"]!!["dark"], colors("values-night")["lk_panel_ink"])
        assertEquals(tokens["paper"]!!["light"], colors("values")["lk_panel_paper"])
    }

    @Test
    fun testEveryValueIsAnOpaqueHexColor() {
        for (folder in listOf("values", "values-night")) {
            for ((name, value) in colors(folder)) {
                assertTrue("$folder/$name: $value", Regex("#[0-9A-F]{6}").matches(value))
            }
        }
    }
}
