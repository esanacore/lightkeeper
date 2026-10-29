package com.esanacore.lightkeeper

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.os.Build
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/**
 * The glance, in the Keeper's Logbook order (docs/BRAND.md): the status, then
 * the number with its arrow, then the age in Ink, then the context lines.
 * Every word comes from a [Presentation], which takes it from the vector
 * lines; every status has its word and a shape, and colour is only the
 * second cue.
 *
 * What it never does: show a STALE value as the hero (no large number, no
 * separate arrow, no unit), show a number on NO DATA, or move. There is no
 * animation and no per-second ticking; a change is one redraw.
 *
 * For TalkBack the whole area is one element whose description is the
 * display lines in order.
 */
class GlanceView(context: Context) : LinearLayout(context) {
    private val statusMark = StatusMarkView(context)
    private val hero = HeroRow(context)
    private val wordHero = Logbook.text(context, Logbook.WORD_SP, face = Logbook.sansBlack)
    private val placeholder = Logbook.text(context, Logbook.PLACEHOLDER_SP, face = Logbook.mono)
    private val struck =
        Logbook.text(context, Logbook.BODY_SP, R.color.lk_muted, Logbook.mono).apply {
            paintFlags = paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
        }
    private val age = Logbook.text(context, Logbook.AGE_SP, face = Logbook.monoBold)
    private val contextLines = LinearLayout(context).apply { orientation = VERTICAL }
    private var shown: Presentation? = null

    init {
        id = R.id.lk_status_area
        orientation = VERTICAL
        statusMark.id = R.id.lk_status_mark
        hero.id = R.id.lk_hero
        struck.id = R.id.lk_struck_line
        age.id = R.id.lk_age_line
        placeholder.id = R.id.lk_placeholder
        val gap = Logbook.dp(context, 12)
        for (child in listOf(statusMark, hero, wordHero, placeholder, struck, age, contextLines)) {
            addView(child, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            (child.layoutParams as LayoutParams).bottomMargin = gap
            child.importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        }
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES
        isFocusable = true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) isScreenReaderFocusable = true
    }

    /** Draws [presentation]. The same presentation again changes nothing on screen. */
    fun bind(presentation: Presentation) {
        if (presentation == shown) return
        shown = presentation
        contentDescription = presentation.accessibilityText

        statusMark.bind(presentation, hero.heroTextPx)

        val number = presentation.hero as? Presentation.Hero.Number
        hero.visibility = if (number != null) VISIBLE else GONE
        if (number != null) hero.bind(number)

        val word = presentation.hero as? Presentation.Hero.Word
        wordHero.visibility = if (word != null) VISIBLE else GONE
        wordHero.text = word?.text.orEmpty()

        show(placeholder, presentation.placeholder)
        show(struck, presentation.struckLine)
        show(age, presentation.age)

        contextLines.removeAllViews()
        for (line in presentation.context) {
            val view = Logbook.text(context, Logbook.BODY_SP, face = Logbook.mono)
            view.text = line
            contextLines.addView(view)
        }
        contextLines.visibility = if (presentation.context.isEmpty()) GONE else VISIBLE
    }

    private fun show(view: TextView, text: String?) {
        view.visibility = if (text == null) GONE else VISIBLE
        view.text = text.orEmpty()
    }
}

/**
 * The status word in its shape: a chip, an Ink band with a status rule
 * (URGENT), an Ink band with a hatched margin (STALE), or a dashed frame
 * (NO DATA and anything unknown). The URGENT band is held to the hero's
 * height, so it is never shorter than the number beneath it.
 */
class StatusMarkView(context: Context) : FrameLayout(context) {
    /** Draws the status word of [presentation]; [heroPx] is the number's full text size. */
    fun bind(presentation: Presentation, heroPx: Float) {
        removeAllViews()
        val tone = presentation.tone
        val statusColor = Logbook.color(context, statusColorId(tone))
        when (presentation.banner) {
            Presentation.Banner.CHIP -> {
                val tint = Logbook.color(context, chipColorId(tone))
                val chip =
                    Logbook.text(context, Logbook.CHIP_SP, face = Logbook.sansBold).apply {
                        text = presentation.word
                        background = Logbook.box(context, tint, statusColor, 2)
                        setPadding(dp(12), dp(4), dp(12), dp(4))
                    }
                addView(chip, LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT))
            }
            Presentation.Banner.URGENT -> {
                val band = band(presentation.word)
                val rule = GradientDrawable().apply { setColor(statusColor) }
                band.background =
                    LayerDrawable(arrayOf(band.background, rule)).apply {
                        setLayerGravity(1, Gravity.START or Gravity.FILL_VERTICAL)
                        setLayerWidth(1, dp(4))
                    }
                band.minHeight = heroPx.toInt()
                band.gravity = Gravity.CENTER_VERTICAL or Gravity.START
                addView(band, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            }
            Presentation.Banner.STALE -> {
                // The hatch sits in the margin beside the band, never under the word.
                val row = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
                row.addView(
                    HatchView(context, statusColor),
                    LinearLayout.LayoutParams(dp(8), LinearLayout.LayoutParams.MATCH_PARENT).apply {
                        marginEnd = dp(4)
                    },
                )
                row.addView(
                    band(presentation.word),
                    LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f),
                )
                addView(row, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            }
            Presentation.Banner.NO_DATA -> {
                val frame =
                    Logbook.text(context, Logbook.BANNER_SP, face = Logbook.sansBold).apply {
                        text = presentation.word
                        background =
                            GradientDrawable().apply {
                                setColor(Logbook.color(context, R.color.lk_surface))
                                cornerRadius = dp(2).toFloat()
                                setStroke(
                                    dp(2),
                                    Logbook.color(context, R.color.lk_line_strong),
                                    dp(4).toFloat(),
                                    dp(4).toFloat(),
                                )
                            }
                        setPadding(dp(12), dp(12), dp(12), dp(12))
                    }
                addView(frame, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            }
        }
    }

    /** A full-width Ink band with the word in Band text. */
    private fun band(word: String): TextView =
        Logbook.text(context, Logbook.BANNER_SP, R.color.lk_band_text, Logbook.sansBold).apply {
            text = word
            background = Logbook.box(context, Logbook.color(context, R.color.lk_ink))
            setPadding(dp(16), dp(12), dp(12), dp(12))
        }

    private fun dp(value: Int): Int = Logbook.dp(context, value)

    companion object {
        /** The status colour resource for a tone: chip borders, band rules, the stale hatch. */
        fun statusColorId(tone: Presentation.Tone): Int =
            when (tone) {
                Presentation.Tone.IN_RANGE -> R.color.lk_in_range
                Presentation.Tone.LOW -> R.color.lk_low
                Presentation.Tone.HIGH -> R.color.lk_high
                Presentation.Tone.STALE -> R.color.lk_stale
            }

        /** The tint behind the status word in a chip. */
        fun chipColorId(tone: Presentation.Tone): Int =
            when (tone) {
                Presentation.Tone.IN_RANGE -> R.color.lk_chip_in_range
                Presentation.Tone.LOW -> R.color.lk_chip_low
                Presentation.Tone.HIGH -> R.color.lk_chip_high
                Presentation.Tone.STALE -> R.color.lk_chip_stale
            }
    }
}

/** hatch-45: one 1 dp diagonal every 4 dp. Texture for STALE's margin only. */
@SuppressLint("ViewConstructor") // Built in code with its colour, never inflated.
class HatchView(context: Context, color: Int) : View(context) {
    private val paint =
        Paint().apply {
            this.color = color
            strokeWidth = Logbook.dp(context, 1).toFloat()
            style = Paint.Style.STROKE
        }
    private val pitch = Logbook.dp(context, 4).toFloat()

    override fun onDraw(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        canvas.save()
        canvas.clipRect(0f, 0f, w, h)
        var x = -h
        while (x < w) {
            canvas.drawLine(x, h, x + h, 0f, paint)
            x += pitch
        }
        canvas.restore()
    }
}

/**
 * The fresh number: digits, then the arrow over the unit. Only the number
 * (and its arrow, in proportion) shrinks to fit a narrow screen or a large
 * font size, never below half; the status and the age never shrink.
 */
class HeroRow(context: Context) : LinearLayout(context) {
    private val digits =
        Logbook.text(context, Logbook.HERO_SP, face = Logbook.sansBlack).apply {
            fontFeatureSettings = "tnum"
            maxLines = 1
            includeFontPadding = false
        }
    private val arrow = Logbook.text(context, Logbook.ARROW_SP, face = Logbook.sansBold)
    private val unit = Logbook.text(context, Logbook.UNIT_SP, R.color.lk_muted)

    /** The number's full text size in pixels, before any shrinking. */
    val heroTextPx: Float = digits.textSize
    private val arrowTextPx: Float = arrow.textSize

    init {
        orientation = HORIZONTAL
        gravity = Gravity.BOTTOM
        addView(digits, LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT))
        val column = LinearLayout(context).apply { orientation = VERTICAL }
        column.addView(arrow)
        column.addView(unit)
        addView(
            column,
            LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT).apply {
                marginStart = Logbook.dp(context, 8)
                bottomMargin = Logbook.dp(context, 12)
            },
        )
    }

    /** Shows [number]: its digits, its arrow as a phone glyph, and its unit, all from the line. */
    fun bind(number: Presentation.Hero.Number) {
        digits.text = number.digits
        val glyph = Presentation.phoneArrow(number.arrow)
        // Never a missing-glyph box: the vector's own ASCII arrow is the fallback.
        arrow.text = if (arrow.paint.hasGlyph(glyph)) glyph else number.arrow
        unit.text = number.unit
        requestLayout()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val available = MeasureSpec.getSize(widthMeasureSpec) - paddingLeft - paddingRight
        var scale = 1f
        if (MeasureSpec.getMode(widthMeasureSpec) != MeasureSpec.UNSPECIFIED && available > 0) {
            val column = maxOf(widthAt(arrow, arrowTextPx), widthAt(unit, unit.textSize))
            val needed = widthAt(digits, heroTextPx) + Logbook.dp(context, 8) + column
            if (needed > available) scale = maxOf(MIN_SCALE, available / needed)
        }
        setPx(digits, heroTextPx * scale)
        setPx(arrow, arrowTextPx * scale)
        super.onMeasure(widthMeasureSpec, heightMeasureSpec)
    }

    /** [view]'s text width at [px], measured with a copy so the view's own paint is untouched. */
    private fun widthAt(view: TextView, px: Float): Float =
        Paint(view.paint).apply { textSize = px }.measureText(view.text.toString())

    private fun setPx(view: TextView, px: Float) {
        if (view.textSize != px) view.setTextSize(TypedValue.COMPLEX_UNIT_PX, px)
    }

    private companion object {
        const val MIN_SCALE = 0.5f
    }
}
