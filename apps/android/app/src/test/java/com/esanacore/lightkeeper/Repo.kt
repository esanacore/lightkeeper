package com.esanacore.lightkeeper

import java.io.File

/**
 * The repository checkout the JVM tests read from: tokens.json, the spec
 * vectors and this app's resources. build.gradle.kts passes its path.
 */
object Repo {
    val root: File by lazy {
        val path =
            System.getProperty("lightkeeper.repoRoot")
                ?: error("lightkeeper.repoRoot is not set; run the tests through Gradle")
        File(path)
    }

    fun file(relative: String): File = File(root, relative)

    fun text(relative: String): String = file(relative).readText(Charsets.UTF_8)

    /** The display vectors' cases, parsed. */
    @Suppress("UNCHECKED_CAST")
    val displayCases: List<Map<String, Any?>> by lazy {
        val spec = MiniJson.parse(text("spec/display_vectors.json")) as Map<String, Any?>
        spec["cases"] as List<Map<String, Any?>>
    }

    /** Every case's expected lines, by name. */
    @Suppress("UNCHECKED_CAST")
    val displayLines: Map<String, List<String>> by lazy {
        displayCases.associate { it["name"] as String to it["lines"] as List<String> }
    }
}

/**
 * A strict little JSON reader for the tests: objects become maps (in order),
 * arrays lists, numbers Long or Double. org.json is only a stub on the JVM,
 * and the app ships no JSON library of its own.
 */
object MiniJson {
    fun parse(text: String): Any? {
        val reader = Reader(text)
        val value = reader.value()
        reader.skipSpace()
        require(reader.atEnd()) { "trailing text at ${reader.pos}" }
        return value
    }

    private class Reader(val text: String) {
        var pos = 0

        fun atEnd() = pos >= text.length

        fun skipSpace() {
            while (!atEnd() && text[pos] in " \t\r\n") pos++
        }

        fun value(): Any? {
            skipSpace()
            require(!atEnd()) { "unexpected end" }
            return when (text[pos]) {
                '{' -> obj()
                '[' -> array()
                '"' -> string()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> number()
            }
        }

        private fun literal(word: String, result: Any?): Any? {
            require(text.startsWith(word, pos)) { "bad literal at $pos" }
            pos += word.length
            return result
        }

        private fun obj(): Map<String, Any?> {
            pos++
            val out = LinkedHashMap<String, Any?>()
            skipSpace()
            if (text[pos] == '}') {
                pos++
                return out
            }
            while (true) {
                skipSpace()
                val key = string()
                skipSpace()
                require(text[pos] == ':') { "expected : at $pos" }
                pos++
                out[key] = value()
                skipSpace()
                when (text[pos++]) {
                    ',' -> continue
                    '}' -> return out
                    else -> error("expected , or } at ${pos - 1}")
                }
            }
        }

        private fun array(): List<Any?> {
            pos++
            val out = ArrayList<Any?>()
            skipSpace()
            if (text[pos] == ']') {
                pos++
                return out
            }
            while (true) {
                out.add(value())
                skipSpace()
                when (text[pos++]) {
                    ',' -> continue
                    ']' -> return out
                    else -> error("expected , or ] at ${pos - 1}")
                }
            }
        }

        private fun string(): String {
            require(text[pos] == '"') { "expected a string at $pos" }
            pos++
            val out = StringBuilder()
            while (true) {
                val c = text[pos++]
                when (c) {
                    '"' -> return out.toString()
                    '\\' -> {
                        when (val e = text[pos++]) {
                            '"', '\\', '/' -> out.append(e)
                            'b' -> out.append('\b')
                            'f' -> out.append('\u000C')
                            'n' -> out.append('\n')
                            'r' -> out.append('\r')
                            't' -> out.append('\t')
                            'u' -> {
                                out.append(text.substring(pos, pos + 4).toInt(16).toChar())
                                pos += 4
                            }
                            else -> error("bad escape at ${pos - 1}")
                        }
                    }
                    else -> out.append(c)
                }
            }
        }

        private fun number(): Any {
            val start = pos
            while (!atEnd() && text[pos] in "+-0123456789.eE") pos++
            val token = text.substring(start, pos)
            require(token.isNotEmpty()) { "unexpected character at $start" }
            return token.toLongOrNull() ?: token.toDouble()
        }
    }
}
