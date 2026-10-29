package com.esanacore.lightkeeper

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.graphics.drawable.StateListDrawable
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.TextView

/**
 * The Keeper's Logbook pieces the screens share (docs/BRAND.md): the type
 * sizes, the 4 dp grid, and the card and button shapes. Every colour is a
 * resource mirrored from assets/brand/tokens.json (res/values/colors.xml and
 * res/values-night/colors.xml); nothing here makes a colour of its own.
 *
 * Text sizes are in sp, so they follow the person's font size, and keep
 * their order at every size: the STALE and NO DATA banners stay the largest
 * text on their screens, and the status chip never drops below 20 sp bold.
 */
object Logbook {
    /** The fresh number: the hero. */
    const val HERO_SP = 96f

    /** The arrow beside the number, in proportion at every size, so it is never demoted. */
    const val ARROW_SP = 40f

    /** A sensor sentinel ("LOW (<40)") is wider than a number, so it starts smaller. */
    const val WORD_SP = 48f

    /** The unit beside the number. */
    const val UNIT_SP = 15f

    /** The status word in its chip: never smaller than 20 sp bold. */
    const val CHIP_SP = 20f

    /** The URGENT, STALE and NO DATA banners: the largest text on a STALE or NO DATA screen. */
    const val BANNER_SP = 28f

    /** The age line, in Ink: the number's partner, never small print. */
    const val AGE_SP = 20f

    /** STALE's struck `last:` line and the context lines: body size. */
    const val BODY_SP = 16f

    /** The "--" where NO DATA has no number: smaller than its banner. */
    const val PLACEHOLDER_SP = 22f

    /** Captions, footnotes and the disclaimer. */
    const val CAPTION_SP = 13f

    /** Card titles. */
    const val TITLE_SP = 22f

    /** The app's name in the header: smaller than any status word. */
    const val APP_NAME_SP = 17f

    /** The smallest touch target, in dp. */
    const val TOUCH_DP = 48

    /** The hard offset shadow under cards and buttons, in dp. */
    const val SHADOW_DP = 3

    val mono: Typeface = Typeface.MONOSPACE
    val monoBold: Typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
    val sansBold: Typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
    val sansBlack: Typeface = Typeface.create("sans-serif-black", Typeface.NORMAL)

    fun dp(context: Context, value: Int): Int =
        TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP,
                value.toFloat(),
                context.resources.displayMetrics,
            )
            .toInt()

    fun color(context: Context, id: Int): Int = context.getColor(id)

    /** A text line: [sp] in sp, in [colorId], left aligned. */
    fun text(
        context: Context,
        sp: Float,
        colorId: Int = R.color.lk_ink,
        face: Typeface = Typeface.DEFAULT,
    ): TextView =
        TextView(context).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
            setTextColor(color(context, colorId))
            typeface = face
            gravity = Gravity.START
        }

    /** A rectangle with the 2 dp screen radius, [fill], and an optional [stroke] border. */
    fun box(context: Context, fill: Int, stroke: Int? = null, strokeDp: Int = 1): GradientDrawable =
        GradientDrawable().apply {
            setColor(fill)
            cornerRadius = dp(context, 2).toFloat()
            if (stroke != null) setStroke(dp(context, strokeDp), stroke)
        }

    /** [face] over the hard offset shadow (Beam soft, or Line in dark mode). */
    fun withShadow(context: Context, face: Drawable): Drawable {
        val shadow = box(context, color(context, R.color.lk_hard_shadow))
        val offset = dp(context, SHADOW_DP)
        return LayerDrawable(arrayOf(shadow, face)).apply {
            setLayerInset(0, offset, offset, 0, 0)
            setLayerInset(1, 0, 0, offset, offset)
        }
    }

    /** A card: Surface with a 1 dp Line strong edge and the hard shadow. */
    fun card(context: Context): Drawable {
        val surface = color(context, R.color.lk_surface)
        return withShadow(context, box(context, surface, color(context, R.color.lk_line_strong)))
    }

    /**
     * A logbook button: Ink on Surface with a Line strong edge and the hard
     * shadow; a 2 dp Beam ring when focused; an Ink fill with Band text when
     * pressed. At least 48 dp tall.
     */
    fun button(context: Context, label: String): Button =
        Button(context).apply {
            text = label
            isAllCaps = false
            stateListAnimator = null
            typeface = sansBold
            setTextSize(TypedValue.COMPLEX_UNIT_SP, BODY_SP)
            minHeight = dp(context, TOUCH_DP)
            minimumHeight = dp(context, TOUCH_DP)
            minWidth = dp(context, TOUCH_DP)
            minimumWidth = dp(context, TOUCH_DP)
            val shadow = dp(context, SHADOW_DP)
            setPadding(dp(context, 16), 0, dp(context, 16) + shadow, shadow)
            background = buttonBackground(context)
            setTextColor(
                ColorStateList(
                    arrayOf(
                        intArrayOf(android.R.attr.state_pressed),
                        intArrayOf(-android.R.attr.state_enabled),
                        intArrayOf(),
                    ),
                    intArrayOf(
                        color(context, R.color.lk_band_text),
                        color(context, R.color.lk_muted),
                        color(context, R.color.lk_ink),
                    ),
                )
            )
        }

    private fun buttonBackground(context: Context): Drawable {
        val surface = color(context, R.color.lk_surface)
        val edge = color(context, R.color.lk_line_strong)
        return StateListDrawable().apply {
            addState(
                intArrayOf(android.R.attr.state_pressed),
                withShadow(context, box(context, color(context, R.color.lk_ink), edge)),
            )
            addState(
                intArrayOf(android.R.attr.state_focused),
                withShadow(context, box(context, surface, color(context, R.color.lk_beam), 2)),
            )
            addState(intArrayOf(), withShadow(context, box(context, surface, edge)))
        }
    }

    /** A plain text button for the header: Beam text, at least 48 dp square. */
    fun headerButton(context: Context, label: String): Button =
        Button(context, null, 0, android.R.style.Widget_Material_Button_Borderless).apply {
            text = label
            isAllCaps = false
            typeface = sansBold
            setTextSize(TypedValue.COMPLEX_UNIT_SP, BODY_SP)
            setTextColor(
                ColorStateList(
                    arrayOf(intArrayOf(-android.R.attr.state_enabled), intArrayOf()),
                    intArrayOf(
                        color(context, R.color.lk_muted),
                        color(context, R.color.lk_beam_text),
                    ),
                )
            )
            minHeight = dp(context, TOUCH_DP)
            minimumHeight = dp(context, TOUCH_DP)
            minWidth = dp(context, TOUCH_DP)
            minimumWidth = dp(context, TOUCH_DP)
        }

}

/** A [width]-pixel rule in [color] down the start edge: the shape cue on a warning row. */
class WarningRule(color: Int, private val width: Int) : Drawable() {
    private val paint = Paint().apply { this.color = color }

    override fun draw(canvas: Canvas) {
        val area = bounds
        canvas.drawRect(
            area.left.toFloat(),
            area.top.toFloat(),
            (area.left + width).toFloat(),
            area.bottom.toFloat(),
            paint,
        )
    }

    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.OPAQUE
}
