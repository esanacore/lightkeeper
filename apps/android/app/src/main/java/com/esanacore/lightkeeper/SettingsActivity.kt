package com.esanacore.lightkeeper

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * The settings screen: the Nightscout address and readable token, and the
 * display thresholds. The address is checked as it is typed, with the reason
 * shown, by the same [SiteAddress] check every fetch goes through, so an
 * address the app cannot use can never be saved. Edits land in a draft, and
 * Save is refused while the draft is not a valid set (HAZ-006): leaving the
 * screen any other way applies nothing.
 */
class SettingsActivity : Activity() {
    /**
     * The draft and the typed token, kept in memory across a rotation and
     * never in a Bundle. [tokenEdited] is false until the token field is
     * changed: an untouched field never rewrites or deletes the saved token,
     * even when it shows empty because the Keystore could not open it just now.
     */
    private class Draft(
        var settings: Settings,
        var token: String,
        var tokenEdited: Boolean = false,
    )

    private lateinit var store: SettingsStore
    private lateinit var tokens: TokenStore
    private lateinit var draft: Draft
    private lateinit var url: EditText
    private lateinit var token: EditText
    private lateinit var urlProblem: TextView
    private lateinit var caution: TextView
    private lateinit var invalid: TextView
    private lateinit var saveError: TextView
    private lateinit var save: Button
    private val steppers = mutableListOf<Stepper>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SettingsStore(this)
        tokens = TokenStore(this)
        draft =
            lastNonConfigurationInstance as? Draft
                ?: Draft(store.load(), tokens.read().orEmpty())
        val root = buildLayout()
        setContentView(root)
        EdgeToEdge.install(this, root)
        refresh()
    }

    override fun onRetainNonConfigurationInstance(): Any = draft

    /** Shows the draft: the problems, the stepper values and bounds, and whether Save works. */
    private fun refresh() {
        val settings = draft.settings
        show(urlProblem, settings.urlProblem, R.string.address_problem_spoken)
        show(caution, settings.staleCaution, R.string.caution_spoken)
        show(invalid, settings.validationMessage, R.string.invalid_spoken)
        steppers.forEach { it.refresh(settings) }
        save.isEnabled = settings.canSave
    }

    private fun show(view: TextView, text: String?, spoken: Int) {
        view.visibility = if (text == null) View.GONE else View.VISIBLE
        view.text = text.orEmpty()
        view.contentDescription = text?.let { getString(spoken, it) }
    }

    private fun saveAndClose() {
        val settings = draft.settings
        if (!settings.canSave) return
        // The token first: if the Keystore refuses it, nothing is saved.
        if (draft.tokenEdited && !tokens.write(draft.token)) {
            saveError.visibility = View.VISIBLE
            return
        }
        store.save(settings)
        finish()
    }

    private fun buildLayout(): ScrollView {
        val column =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                val pad = Logbook.dp(context, 16)
                setPadding(pad, Logbook.dp(context, 8), pad, pad)
            }
        column.addView(header())
        saveError = warning().apply { setText(R.string.token_not_saved) }
        saveError.visibility = View.GONE
        column.addView(saveError, matchWidth(top = 8))

        column.addView(sectionTitle(R.string.section_nightscout), matchWidth(top = 16))
        url =
            EditText(this).apply {
                id = R.id.lk_url
                setHint(R.string.url_hint)
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
                isSingleLine = true
                setText(draft.settings.nightscoutUrl)
                contentDescription = getString(R.string.url_label)
                addTextChangedListener(
                    afterChange { typed ->
                        // A pasted address often carries a space or a newline at an end.
                        draft.settings = draft.settings.copy(nightscoutUrl = typed.trim())
                        refresh()
                    }
                )
            }
        column.addView(url, matchWidth(top = 4))
        urlProblem = warning()
        column.addView(urlProblem, matchWidth(top = 4))

        token =
            EditText(this).apply {
                id = R.id.lk_token
                setHint(R.string.token_hint)
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                // A password field switches to monospace; keep the hint in the body face.
                typeface = Typeface.DEFAULT
                isSingleLine = true
                // The token never goes to an autofill service or into saved view state.
                importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
                isSaveEnabled = false
                setText(draft.token)
                addTextChangedListener(
                    afterChange { typed ->
                        draft.token = typed.trim()
                        draft.tokenEdited = true
                    }
                )
            }
        column.addView(token, matchWidth(top = 8))
        column.addView(footnote(R.string.token_footnote), matchWidth(top = 4))

        column.addView(sectionTitle(R.string.section_thresholds), matchWidth(top = 24))
        val step = Settings.THRESHOLD_STEP
        steppers +=
            listOf(
                Stepper(
                    R.string.urgent_low_label,
                    R.string.urgent_low_name,
                    Settings.URGENT_LOW_RANGE,
                    step,
                    { it.urgentLow },
                    { s, v -> s.copy(urgentLow = v) },
                ),
                Stepper(
                    R.string.low_label,
                    R.string.low_name,
                    Settings.LOW_RANGE,
                    step,
                    { it.low },
                    { s, v -> s.copy(low = v) },
                ),
                Stepper(
                    R.string.high_label,
                    R.string.high_name,
                    Settings.HIGH_RANGE,
                    step,
                    { it.high },
                    { s, v -> s.copy(high = v) },
                ),
                Stepper(
                    R.string.urgent_high_label,
                    R.string.urgent_high_name,
                    Settings.URGENT_HIGH_RANGE,
                    step,
                    { it.urgentHigh },
                    { s, v -> s.copy(urgentHigh = v) },
                ),
                Stepper(
                    R.string.stale_label,
                    R.string.stale_name,
                    Settings.STALE_RANGE,
                    Settings.STALE_STEP,
                    { it.staleMinutes },
                    { s, v -> s.copy(staleMinutes = v) },
                ),
            )
        steppers.forEach { column.addView(it.row, matchWidth(top = 8)) }
        caution = warning().apply { id = R.id.lk_stale_caution }
        column.addView(caution, matchWidth(top = 8))
        invalid = warning().apply { id = R.id.lk_invalid_thresholds }
        column.addView(invalid, matchWidth(top = 8))
        val reset = Logbook.button(this, getString(R.string.reset_defaults))
        reset.setOnClickListener {
            draft.settings = draft.settings.resettingThresholds()
            refresh()
        }
        column.addView(
            reset,
            LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                )
                .apply { topMargin = Logbook.dp(this@SettingsActivity, 12) },
        )
        column.addView(footnote(R.string.thresholds_footnote), matchWidth(top = 8))

        return ScrollView(this).apply {
            id = R.id.lk_settings_root
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
        val cancel = Logbook.headerButton(this, getString(R.string.cancel))
        cancel.setOnClickListener { finish() }
        row.addView(cancel)
        val title = Logbook.text(this, Logbook.APP_NAME_SP, face = Logbook.sansBold)
        title.setText(R.string.settings)
        title.gravity = Gravity.CENTER
        row.addView(title, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        save = Logbook.headerButton(this, getString(R.string.save))
        save.id = R.id.lk_save
        save.setOnClickListener { saveAndClose() }
        row.addView(save)
        return row
    }

    private fun sectionTitle(text: Int): TextView =
        Logbook.text(this, Logbook.BODY_SP, face = Logbook.sansBold).apply {
            setText(text)
            isAllCaps = false
        }

    private fun footnote(text: Int): TextView =
        Logbook.text(this, Logbook.CAPTION_SP, R.color.lk_muted).apply { setText(text) }

    /** A warning row: Ink words beside a 4 dp Ink rule, never colour alone. */
    private fun warning(): TextView =
        Logbook.text(this, Logbook.CAPTION_SP).apply {
            val rule = Logbook.dp(context, 4)
            background = WarningRule(Logbook.color(context, R.color.lk_ink), rule)
            setPadding(rule * 3, Logbook.dp(context, 4), 0, Logbook.dp(context, 4))
            visibility = View.GONE
        }

    private fun matchWidth(top: Int = 0): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
            .apply { topMargin = Logbook.dp(this@SettingsActivity, top) }

    /** One threshold row: its value in words, and a minus and a plus of at least 48 dp. */
    private inner class Stepper(
        private val label: Int,
        name: Int,
        private val range: IntRange,
        private val step: Int,
        private val read: (Settings) -> Int,
        private val write: (Settings, Int) -> Settings,
    ) {
        private val activity = this@SettingsActivity
        private val value = Logbook.text(activity, Logbook.BODY_SP, face = Logbook.mono)
        private val minus = Logbook.button(activity, "−")
        private val plus = Logbook.button(activity, "+")
        val row =
            LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }

        init {
            val spoken = getString(name)
            value.accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            minus.contentDescription = getString(R.string.decrease, spoken)
            plus.contentDescription = getString(R.string.increase, spoken)
            minus.setOnClickListener { move(-step) }
            plus.setOnClickListener { move(step) }
            val wrap = LinearLayout.LayoutParams.WRAP_CONTENT
            row.addView(value, LinearLayout.LayoutParams(0, wrap, 1f))
            row.addView(minus)
            val gap = LinearLayout.LayoutParams(wrap, wrap)
            gap.marginStart = Logbook.dp(activity, 8)
            row.addView(plus, gap)
        }

        /** Shows the value in [settings]; a button at its bound does nothing, so it is off. */
        fun refresh(settings: Settings) {
            val current = read(settings)
            value.text = getString(label, current)
            minus.isEnabled = current > range.first
            plus.isEnabled = current < range.last
        }

        private fun move(delta: Int) {
            val moved = Settings.step(read(draft.settings), delta, range)
            draft.settings = write(draft.settings, moved)
            activity.refresh()
        }
    }

    private companion object {
        fun afterChange(onChange: (String) -> Unit): TextWatcher =
            object : TextWatcher {
                override fun beforeTextChanged(
                    s: CharSequence?,
                    start: Int,
                    count: Int,
                    after: Int,
                ) = Unit

                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) =
                    Unit

                override fun afterTextChanged(s: Editable?) {
                    onChange(s?.toString().orEmpty())
                }
            }
    }
}
