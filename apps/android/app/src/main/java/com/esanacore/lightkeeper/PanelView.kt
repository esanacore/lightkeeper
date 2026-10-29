package com.esanacore.lightkeeper

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Rect
import android.view.View

/**
 * The real 1-bit panel image from the firmware's rasterizer, the same pixels
 * the bedside e-ink shows, scaled up by a whole number with nearest-neighbour
 * sampling (filtering off), so every panel pixel is an exact square of
 * screen pixels and nothing is smoothed or imitated. Paper and Ink by day;
 * Night paper and Night ink in dark mode, so the panel is never the brightest
 * thing at the bedside. Inside a 2 dp Line strong bezel with notched corners.
 *
 * Hidden from TalkBack: the status area above reads the same lines.
 */
@SuppressLint("ViewConstructor") // Built in code only, never inflated.
class PanelView(context: Context) : View(context) {
    private var image: Bitmap? = null
    private var panelWidth = 0
    private var panelHeight = 0
    private val bezel = Logbook.dp(context, 2)
    private val pad = Logbook.dp(context, 8)
    private val pixels =
        Paint().apply {
            isFilterBitmap = false
            isAntiAlias = false
            isDither = false
        }
    private val paper = Paint().apply { color = context.getColor(R.color.lk_panel_paper) }
    private val edge =
        Paint().apply {
            color = context.getColor(R.color.lk_line_strong)
            style = Paint.Style.STROKE
            strokeWidth = bezel.toFloat()
        }
    private val outline = Path()
    private val target = Rect()

    init {
        id = R.id.lk_panel
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
    }

    /** The whole-number scale the image is drawn at, or 0 when nothing is shown. */
    var scale: Int = 0
        private set

    /**
     * Shows packed [rows] (1 = ink, leftmost pixel in the most significant
     * bit) of a [width] x [height] image. Null rows, from a refused render,
     * show nothing at all, never the previous image.
     */
    fun show(rows: ByteArray?, width: Int, height: Int) {
        val stride = (width + 7) / 8
        if (rows == null || width < 1 || height < 1 || rows.size < stride * height) {
            image = null
            visibility = GONE
            return
        }
        val ink = context.getColor(R.color.lk_panel_ink)
        val ground = context.getColor(R.color.lk_panel_paper)
        val colors = IntArray(width * height)
        for (y in 0 until height) {
            for (x in 0 until width) {
                val bit = (rows[y * stride + x / 8].toInt() shr (7 - x % 8)) and 1
                colors[y * width + x] = if (bit == 1) ink else ground
            }
        }
        image = Bitmap.createBitmap(colors, width, height, Bitmap.Config.ARGB_8888)
        panelWidth = width
        panelHeight = height
        visibility = VISIBLE
        requestLayout()
        invalidate()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val width = MeasureSpec.getSize(widthMeasureSpec)
        val inner = width - 2 * (bezel + pad)
        scale = if (image == null || panelWidth == 0) 0 else maxOf(1, inner / panelWidth)
        val height = if (scale == 0) 0 else panelHeight * scale + 2 * (bezel + pad)
        setMeasuredDimension(width, height)
    }

    override fun onDraw(canvas: Canvas) {
        val bitmap = image ?: return
        notched(outline, width.toFloat(), height.toFloat(), bezel.toFloat())
        canvas.drawPath(outline, paper)
        canvas.drawPath(outline, edge)
        val drawnWidth = panelWidth * scale
        val left = (width - drawnWidth) / 2
        val top = bezel + pad
        target.set(left, top, left + drawnWidth, top + panelHeight * scale)
        canvas.drawBitmap(bitmap, null, target, pixels)
    }

    /** The bezel: a rectangle with each corner notched by one [step]. */
    private fun notched(path: Path, w: Float, h: Float, step: Float) {
        val inset = step / 2
        path.reset()
        path.moveTo(inset + step, inset)
        path.lineTo(w - inset - step, inset)
        path.lineTo(w - inset - step, inset + step)
        path.lineTo(w - inset, inset + step)
        path.lineTo(w - inset, h - inset - step)
        path.lineTo(w - inset - step, h - inset - step)
        path.lineTo(w - inset - step, h - inset)
        path.lineTo(inset + step, h - inset)
        path.lineTo(inset + step, h - inset - step)
        path.lineTo(inset, h - inset - step)
        path.lineTo(inset, inset + step)
        path.lineTo(inset + step, inset + step)
        path.close()
    }
}
