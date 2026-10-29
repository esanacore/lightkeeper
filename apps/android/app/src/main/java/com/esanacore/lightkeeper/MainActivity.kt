package com.esanacore.lightkeeper

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * The glance screen: the status area ([GlanceView]), the captions, then the
 * real panel image, then the disclaimer. Before a usable Nightscout address
 * is saved it shows only the setup card: no number, no level word, and no
 * fetch.
 *
 * Everything on it is redrawn from [GlanceModel.state] by [render], once per
 * change. There is no animation, no sound and no notification.
 */
class MainActivity : Activity() {
    private lateinit var controller: GlanceController
    private lateinit var glance: GlanceView
    private lateinit var captions: LinearLayout
    private lateinit var checked: TextView
    private lateinit var offline: TextView
    private lateinit var setupCard: LinearLayout
    private lateinit var setupMessage: TextView
    private lateinit var panel: PanelView
    private var drawnPanel: Pair<List<String>, String>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Kept across a rotation or a theme change, so the last good reading survives it.
        controller = lastNonConfigurationInstance as? GlanceController ?: GlanceController(this)
        val root = buildLayout()
        setContentView(root)
        EdgeToEdge.install(this, root)
        render()
    }

    override fun onRetainNonConfigurationInstance(): Any = controller

    override fun onStart() {
        super.onStart()
        controller.onChange = ::render
        controller.start()
    }

    override fun onResume() {
        super.onResume()
        controller.resume()
    }

    override fun onStop() {
        controller.stop()
        super.onStop()
    }

    override fun onDestroy() {
        if (isChangingConfigurations) controller.onChange = null else controller.close()
        super.onDestroy()
    }

    /** Redraws the screen from the model's state. */
    private fun render() {
        val state = controller.model.state
        if (state.configured) {
            glance.bind(Presentation.of(state.lines))
            checked.text = Captions.status(state.lastRefreshMs)
            val since = state.offlineSinceMs
            offline.visibility = if (since == null) View.GONE else View.VISIBLE
            offline.text = since?.let { Captions.offlineSince(it) }.orEmpty()
            showPanel(state)
        } else {
            val problem = controller.model.settings.urlProblem
            setupMessage.text =
                if (problem == null) {
                    getString(R.string.setup_message)
                } else {
                    getString(R.string.setup_problem, problem)
                }
            drawnPanel = null
            panel.show(null, PANEL_WIDTH, PANEL_HEIGHT)
        }
        glance.visibility = if (state.configured) View.VISIBLE else View.GONE
        captions.visibility = glance.visibility
        setupCard.visibility = if (state.configured) View.GONE else View.VISIBLE
    }

    /** Draws the panel image for the state's lines, stamped with when they were drawn. */
    private fun showPanel(state: GlanceState) {
        val stamp = Captions.clockText(state.drawnAtMs)
        val wanted = state.lines to stamp
        if (wanted == drawnPanel) return
        drawnPanel = wanted
        val rows = NativeRules.panel(state.lines, PANEL_WIDTH, PANEL_HEIGHT, stamp)
        panel.show(rows, PANEL_WIDTH, PANEL_HEIGHT)
    }

    private fun openSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    private fun buildLayout(): ScrollView {
        val column =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                val pad = Logbook.dp(context, 16)
                setPadding(pad, Logbook.dp(context, 8), pad, pad)
            }
        column.addView(header())

        glance = GlanceView(this)
        column.addView(glance, matchWidth(top = 8))

        checked = Logbook.text(this, Logbook.CAPTION_SP, R.color.lk_muted, Logbook.mono)
        checked.id = R.id.lk_checked
        offline = Logbook.text(this, Logbook.CAPTION_SP, face = Logbook.mono)
        offline.id = R.id.lk_offline
        captions =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                addView(checked)
                addView(offline)
            }
        column.addView(captions, matchWidth(top = 4))

        setupCard = setupCard()
        column.addView(setupCard, matchWidth(top = 16))

        panel = PanelView(this)
        column.addView(panel, matchWidth(top = 24))

        val disclaimer = Logbook.text(this, Logbook.CAPTION_SP, R.color.lk_muted)
        disclaimer.setText(R.string.disclaimer)
        column.addView(disclaimer, matchWidth(top = 16))

        return ScrollView(this).apply {
            id = R.id.lk_root
            isFillViewport = true
            clipToPadding = true
            addView(column)
        }
    }

    private fun header(): View {
        val row =
            LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
        // The app's name, smaller than any status word.
        val name = Logbook.text(this, Logbook.APP_NAME_SP, face = Logbook.sansBold)
        name.setText(R.string.app_name)
        row.addView(name, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val settings = Logbook.headerButton(this, getString(R.string.settings))
        settings.id = R.id.lk_open_settings
        settings.setOnClickListener { openSettings() }
        row.addView(settings)
        return row
    }

    /** First launch, or a saved address that cannot be used: an invitation, not an outage. */
    private fun setupCard(): LinearLayout {
        val card =
            LinearLayout(this).apply {
                id = R.id.lk_setup_card
                orientation = LinearLayout.VERTICAL
                background = Logbook.card(context)
                val pad = Logbook.dp(context, 16)
                val shadow = Logbook.dp(context, Logbook.SHADOW_DP)
                setPadding(pad, pad, pad + shadow, pad + shadow)
            }
        val title = Logbook.text(this, Logbook.TITLE_SP, face = Logbook.sansBold)
        title.setText(R.string.setup_title)
        card.addView(title, matchWidth())
        setupMessage = Logbook.text(this, Logbook.BODY_SP)
        card.addView(setupMessage, matchWidth(top = 12))
        val open = Logbook.button(this, getString(R.string.open_settings))
        open.setOnClickListener { openSettings() }
        card.addView(
            open,
            LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                )
                .apply { topMargin = Logbook.dp(this@MainActivity, 12) },
        )
        return card
    }

    private fun matchWidth(top: Int = 0): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
            .apply { topMargin = Logbook.dp(this@MainActivity, top) }

    companion object {
        /** The bedside panel's size, waveshare_2in9 (the reference renderer's default profile). */
        const val PANEL_WIDTH = 296
        const val PANEL_HEIGHT = 128
    }
}
