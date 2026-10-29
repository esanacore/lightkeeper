package com.esanacore.lightkeeper

import android.app.Activity
import android.graphics.Rect
import android.os.Build
import android.view.View
import android.view.WindowInsets

/**
 * Draws the window behind transparent system bars (as Android 15 and later
 * require) and pads the content by the bars, the display cutout and the
 * keyboard, so the status headline is never under a system bar. The content
 * is clipped to that padding, so nothing scrolls under a bar either.
 */
object EdgeToEdge {
    fun install(activity: Activity, root: View) {
        val window = activity.window
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Android 15 and later draw every app edge to edge already.
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.VANILLA_ICE_CREAM) {
                @Suppress("DEPRECATION")
                window.setDecorFitsSystemWindows(false)
            }
        } else {
            val decor = window.decorView
            @Suppress("DEPRECATION")
            decor.systemUiVisibility =
                decor.systemUiVisibility or
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                    View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                    View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        }
        val base = Rect(root.paddingLeft, root.paddingTop, root.paddingRight, root.paddingBottom)
        root.setOnApplyWindowInsetsListener { view, insets ->
            val bars = barInsets(insets)
            view.setPadding(
                base.left + bars.left,
                base.top + bars.top,
                base.right + bars.right,
                base.bottom + bars.bottom,
            )
            insets
        }
        root.requestApplyInsets()
    }

    /** What the system bars, the display cutout and the keyboard cover on each side. */
    fun barInsets(insets: WindowInsets): Rect =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val types =
                WindowInsets.Type.systemBars() or
                    WindowInsets.Type.displayCutout() or
                    WindowInsets.Type.ime()
            val covered = insets.getInsets(types)
            Rect(covered.left, covered.top, covered.right, covered.bottom)
        } else {
            @Suppress("DEPRECATION")
            Rect(
                insets.systemWindowInsetLeft,
                insets.systemWindowInsetTop,
                insets.systemWindowInsetRight,
                insets.systemWindowInsetBottom,
            )
        }
}
