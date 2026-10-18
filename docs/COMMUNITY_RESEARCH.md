# Community Research: Glucose Displays and Alerts

What people with type 1 diabetes, their partners, and parents say about the display and alert tools that exist today, and what that means for Lightkeeper. Gathered October 2026 from forums, app store reviews, Home Assistant threads, GitHub issues, and press. Reddit and Facebook groups were not reachable from the research session, so those voices are missing; see the gaps at the end.

Quotes are short and attributed to where they were found. Nothing here is medical advice.

## What people like and dislike

**Dexcom Follow** (App Store rating 1.6 of 5 at the time): alerts repeat "Every. Five. Minutes." even when snoozed; the app stopped showing how long since the last update, which hides glitches; notifications silently stopped for some users. [App Store reviews](https://apps.apple.com/us/app/dexcom-follow/id6746294350)

**SugarPixel** (commercial bedside clock): praised for being "VERY LOUD," for its vibration puck, ascending alerts, and random tones that fight habituation. Criticized as "somewhat finicky to set up," for Wi-Fi dropouts, a clumsy firmware update process, and for wanting the user's Dexcom password. [Integrated Diabetes review](https://integrateddiabetes.com/sugarpixel-blood-glucose-pixel-clock-review/), [Breakthrough T1D forum](https://forum.breakthrought1d.org/t/new-cgm-display-device/74980)

**Sugardash**: liked because no app is needed, it has day and night modes, brightness control, up to six users, and a status bar showing time to the next reading. [Diabetech](https://www.diabetech.info/p/sugardash-touchscreen-cgm-display)

**Glowcose**: a color-only nightlight marketed as "passive awareness," explicitly not an alarm replacement. That framing is worth copying. [Type1Strong](https://www.type1strong.org/blog-post/top-3-glucose-companion-devices)

**LoopFollow**: a broad alarm set with per-alarm quiet windows, "Snooze All Until," and a watch complication with delta. The reference for what a follower app should offer. [Loop and Learn](https://www.loopandlearn.org/loop-follow/)

**Home Assistant**: people route lows to a smart speaker because a partner "cannot hear the iOS low notification," while others warn against relying on a speaker in an emergency. The SugarTV card fades to greyscale after three missed intervals and labels it "Do not trust this." [HA thread](https://community.home-assistant.io/t/frontend-panel-for-diabetics-using-a-dexcom-cgm/209984), [SugarTV card](https://github.com/wiltodelta/homeassistant-sugartv-card)

**Apple Watch**: complications update at most every 15 minutes, so watch faces are always a little behind. [GlucoseGlance](https://github.com/dgsmith/GlucoseGlance)

## Nights

Compression lows wake people several times a night; partners and pets trigger them; one description: readings go "smooth and level to crash and burn in a single tick." [FUDiabetes](https://forum.fudiabetes.org/t/false-compression-lows/12624)

A caregiver survey of 205 parents: about 70% rate their sleep as fairly or very bad, about 40% are made nervous by repeated alarms, about 30% worry they set night limits wrong, and still about 75% refuse to disable alarms. [Diabetes on the Net](https://diabetesonthenet.com/diabetes-care-children-young-people/alarm-fatigue-and-sleep-deprivation/)

Wished-for night features: random or ascending tones against habituation, haptic-only options, quiet hours, scheduled low brightness or a true dark mode, per-alert snooze that works, and a visible "age" indicator that changes color as data gets old.

## Stale data

The 2019 Dexcom Follow outage left parents with blank screens and no alert; "I woke up in a panic at 6am." [Fortune](https://www.fortune.com/2019/12/02/dexcom-outage-blackout-diabetes-patients-blood-sugar-monitor)

DIY projects converge on the same answer Lightkeeper chose: WaveshareMon strikes through the number at 7 to 11 minutes and replaces it with `---` after 12, leaving only the age in red; Nightscout's own defaults warn at 15 minutes and go urgent at 30. [WaveshareMon](https://github.com/psonnera/WaveshareMon), [cgm-remote-monitor](https://github.com/nightscout/cgm-remote-monitor)

LoopFollow's remote-bolus docs add a corollary that matters for ADR-0008: display lag can make a dose look failed, so "always assume a previous remote carbs/bolus was delivered." [LoopFollowDocs](https://loopfollowdocs.org/remote/remote-control-loop/)

## Features people keep asking for

Delta and arrow on every face; mg/dL and mmol/L; IOB and COB on screen (greyed when zero); predictions; several followers with their own quiet settings; real battery numbers; "time until next reading"; localization; configurable colors for old or missing data.

## Omnipod 5 with Trio and Loop, and the G7

Omnipod 5 support shipped in Trio 1.0.0 and Loop 3.14.7 on September 15, 2026, with a connect-on-demand method to limit 203 faults. The first pod needs internet for a certificate step; pods pair with one device only; reconnects under five seconds are normal. [Loop and Learn](https://www.loopandlearn.org/version-updates/), [omnipod-five](https://nightscout.github.io/omnipod-five/), [LoopDocs FAQ](https://loopkit.github.io/loopdocs/faqs/omnipod-faqs/)

G7 reports: harder time staying connected alongside a pod; "Wait 3 hours" messages; 15-day sensors failing around day 12 for some; three Bluetooth slots (pump, phone, watch) that contend with each other. [FUDiabetes](https://forum.fudiabetes.org/t/dexcom-g7/15925), [xDrip discussion](https://github.com/NightscoutFoundation/xDrip/discussions/4115)

## Prior art: open source e-ink and ESP32 displays

| Project | Hardware | What to learn from it |
| --- | --- | --- |
| [nightscout-clock](https://github.com/ktomy/nightscout-clock) | Ulanzi TC001 LED clock | Rich alarm windows and a dark-rooms mode. Looking for a new maintainer. Issue #72: its config page leaked credentials to anyone on the LAN. |
| [M5_NightscoutMon](https://github.com/mlukasek/M5_NightscoutMon) | M5Stack Core | Grey/white/red age box; token in a config file on an SD card; dormant since 2020. |
| [WaveshareMon](https://github.com/psonnera/WaveshareMon) | Waveshare ESP32-S3 1.54" e-paper | Closest prior art: deep sleep, redraw only on change, encrypted config, secrets never read back, TLS on by default. New in 2026. |
| [M5_Paper_Nightscout_Xdrip](https://github.com/baaaa1023/M5_Paper_Nightscout_Xdrip) | M5Paper | About three days of battery; abandoned in 2021. |

None of these carry a safety disclaimer beyond license boilerplate.

## Remote bolus expectations

Trio's remote control is off by default, uses a shared secret, expires commands after 10 minutes, requires Face ID in LoopFollow, and keeps its own guardrails separate from the sender's. Friction reported: push keys must match the Trio build's developer account, leftover profiles from other apps can silently block it, and results "can be delayed or lost at the Apple push stage." Community norms: never send a remote dose without authorization, the Trio user keeps final control, and make sure they know when a dose was sent remotely. [TrioDocs](https://triodocs.org/configuration/settings/features/remote-control/), [LoopFollowDocs](https://loopfollowdocs.org/remote/remote-control-trio/)

## How projects phrase "not a medical device"

Nightscout: "not officially approved or regulated for diabetes therapy," and "Do not rely only on Nightscout as the only way you have of knowing your blood glucose values." LoopFollow: "a DIY open source project that may or may not function as you expect." The Omnipod 5 effort: "not approved by the FDA," "not affiliated with or endorsed by Insulet," "Use at your own risk." Commercial nightlights call themselves "passive awareness." [nightscout.github.io](https://nightscout.github.io/), [LoopFollow](https://github.com/loopandlearn/LoopFollow)

## Implications for Lightkeeper

In priority order. Each one that becomes work gets a requirement ID and a TODO entry.

1. **Data age is the primary element, not a footnote.** Consider a graded response like WaveshareMon's: visibly mark the number as aging before the 15-minute STALE cutoff, so a 12-minute-old reading never looks as fresh as a 2-minute-old one.
2. **Tell apart "no new reading," "Nightscout unreachable," and "phone stopped uploading."** Users could not tell which link failed in the outage stories. Lightkeeper already distinguishes the first two; the third needs Nightscout's device status.
3. **Say "secondary awareness," never "alarm."** Adopt Nightscout's wording: do not rely only on Lightkeeper. Primary alarms stay on the phone.
4. **Night mode is a first-class profile:** scheduled dimming, haptic-only or silent options, per-display quiet hours, and if sound is ever added, ascending or varied tones.
5. **Secrets handling as a stated differentiator:** read-only token only, never a vendor password, write-only secret fields on any device config page, TLS on by default. nightscout-clock #72 is the cautionary tale.
6. **Connectivity resilience with a visible "offline since":** every DIY tracker is dominated by Wi-Fi issues. Backoff, last-success timestamp, and an honest indicator.
7. **E-ink refresh strategy and published battery numbers.** Redraw on change plus a periodic age tick; measure and publish real battery life.
8. **Delta, arrow, IOB and COB, loop status, and mmol/L from early on.** Grey out IOB and COB at zero; show "next reading in."
9. **Companion app bolus requests mirror LoopFollow's safety model** and add "assume it was delivered" on a timeout, plus a visible record of remote commands on the bedside display too.
10. **Compression-low hint:** flag a sudden single-interval drop as a hint, clearly not a diagnosis.
11. **Design for one to three followers**, each with their own quiet settings.
12. **Plan for succession:** small projects in this space die quietly. Keep docs current, ship a web flasher, and consider interoperating with WaveshareMon's config schema rather than inventing another.

## Gaps

Reddit (r/dexcom, r/Nightscout, r/Omnipod, r/Trio) and the Looped and Loop and Learn Facebook groups were not reachable. Direct quotes on the G7 geofence, post-release Omnipod 5 pairing anecdotes, and Apple Watch staleness are missing and worth collecting from a browser session.
