# Community Research

Before building more displays, we read what people with type 1 diabetes, their partners, and parents say about the display and alert tools that already exist. The findings were gathered in October 2026 from forums, app store reviews, Home Assistant threads, GitHub issues, and press, and are recorded with quotes in `docs/COMMUNITY_RESEARCH.md` in the repository. Reddit and the Facebook groups were not reachable, so those voices are missing. Nothing here is medical advice.

## What people like and dislike

**Dexcom Follow** (App Store rating 1.6 of 5 at the time): alerts repeat every five minutes even when snoozed; the app stopped showing how long since the last update, which hides glitches; notifications silently stopped for some users. [App Store reviews](https://apps.apple.com/us/app/dexcom-follow/id6746294350)

**SugarPixel**, a commercial bedside clock: praised for being very loud, for its vibration puck, and for ascending and random tones that fight habituation. Criticized for finicky setup, Wi-Fi dropouts, and wanting the user's Dexcom password. [Integrated Diabetes review](https://integrateddiabetes.com/sugarpixel-blood-glucose-pixel-clock-review/), [Breakthrough T1D forum](https://forum.breakthrought1d.org/t/new-cgm-display-device/74980)

**Glowcose**: a color-only nightlight marketed as "passive awareness," explicitly not an alarm replacement. That framing is worth copying. [Type1Strong](https://www.type1strong.org/blog-post/top-3-glucose-companion-devices)

**LoopFollow**: a broad alarm set with per-alarm quiet windows, "Snooze All Until," and a watch complication with delta. The reference for what a follower app should offer. [Loop and Learn](https://www.loopandlearn.org/loop-follow/)

**Home Assistant**: people route lows to a smart speaker because a partner cannot hear the iOS low notification, while others warn against relying on a speaker in an emergency. The SugarTV card fades to greyscale after three missed intervals and labels it "Do not trust this." [HA thread](https://community.home-assistant.io/t/frontend-panel-for-diabetics-using-a-dexcom-cgm/209984), [SugarTV card](https://github.com/wiltodelta/homeassistant-sugartv-card)

## Nights and stale data

Compression lows wake people several times a night. [FUDiabetes](https://forum.fudiabetes.org/t/false-compression-lows/12624) A survey of 205 parents found about 70% rate their sleep as fairly or very bad, about 40% are made nervous by repeated alarms, and still about 75% refuse to disable alarms. [Diabetes on the Net](https://diabetesonthenet.com/diabetes-care-children-young-people/alarm-fatigue-and-sleep-deprivation/) Wished-for night features: random or ascending tones, haptic-only options, quiet hours, a true dark mode, per-alert snooze that works, and a visible age indicator.

The 2019 Dexcom Follow outage left parents with blank screens and no alert. [Fortune](https://www.fortune.com/2019/12/02/dexcom-outage-blackout-diabetes-patients-blood-sugar-monitor) DIY projects converge on the answer Lightkeeper chose: WaveshareMon strikes through the number at 7 to 11 minutes and replaces it with dashes after 12; Nightscout's own defaults warn at 15 minutes and go urgent at 30. [WaveshareMon](https://github.com/psonnera/WaveshareMon), [cgm-remote-monitor](https://github.com/nightscout/cgm-remote-monitor) LoopFollow's remote-bolus docs add a corollary for the companion app: display lag can make a dose look failed, so always assume a previous remote bolus was delivered. [LoopFollowDocs](https://loopfollowdocs.org/remote/remote-control-loop/)

## Omnipod 5 with Trio, and the G7

Omnipod 5 support shipped in Trio 1.0.0 and Loop 3.14.7 on September 15, 2026, with a connect-on-demand method to limit 203 faults. The first pod needs internet for a certificate step; pods pair with one device only. [Loop and Learn](https://www.loopandlearn.org/version-updates/), [omnipod-five](https://nightscout.github.io/omnipod-five/) G7 reports: a harder time staying connected alongside a pod, "Wait 3 hours" messages, and three Bluetooth slots that contend with each other. [FUDiabetes](https://forum.fudiabetes.org/t/dexcom-g7/15925), [xDrip discussion](https://github.com/NightscoutFoundation/xDrip/discussions/4115)

## Prior art: open source e-ink and ESP32 displays

| Project | Hardware | What to learn from it |
| --- | --- | --- |
| [nightscout-clock](https://github.com/ktomy/nightscout-clock) | Ulanzi TC001 LED clock | Rich alarm windows and a dark-rooms mode. Looking for a maintainer. Issue #72: its config page leaked credentials to anyone on the LAN. |
| [M5_NightscoutMon](https://github.com/mlukasek/M5_NightscoutMon) | M5Stack Core | Grey/white/red age box; token in a config file on an SD card; dormant since 2020. |
| [WaveshareMon](https://github.com/psonnera/WaveshareMon) | Waveshare ESP32-S3 1.54 inch e-paper | Closest prior art: deep sleep, redraw only on change, encrypted config, secrets never read back, TLS on by default. New in 2026. |
| [M5_Paper_Nightscout_Xdrip](https://github.com/baaaa1023/M5_Paper_Nightscout_Xdrip) | M5Paper | About three days of battery; abandoned in 2021. |

None of these carry a safety disclaimer beyond license boilerplate. Nightscout's own wording is the model: "Do not rely only on Nightscout as the only way you have of knowing your blood glucose values." [nightscout.github.io](https://nightscout.github.io/)

## The twelve implications for Lightkeeper

In priority order. Each one that becomes work gets a requirement ID and a TODO entry.

1. **Data age is the primary element, not a footnote.** Consider a graded response like WaveshareMon's, so a 12-minute-old reading never looks as fresh as a 2-minute-old one.
2. **Tell apart "no new reading," "Nightscout unreachable," and "phone stopped uploading."** Lightkeeper distinguishes the first two; the third needs Nightscout's device status.
3. **Say "secondary awareness," never "alarm."** Primary alarms stay on the phone.
4. **Night mode is a first-class profile:** scheduled dimming, haptic-only or silent options, per-display quiet hours.
5. **Secrets handling as a stated differentiator:** read-only token only, never a vendor password, write-only secret fields on any device config page, TLS on by default.
6. **Connectivity resilience with a visible "offline since."**
7. **E-ink refresh strategy and published battery numbers.**
8. **Delta, arrow, IOB and COB, loop status, and mmol/L from early on.**
9. **Companion app bolus requests mirror LoopFollow's safety model**, with "assume it was delivered" on a timeout.
10. **Compression-low hint:** flag a sudden single-interval drop as a hint, clearly not a diagnosis.
11. **Design for one to three followers**, each with their own quiet settings.
12. **Plan for succession:** keep docs current, ship a web flasher, consider interoperating with WaveshareMon's config schema.

Where these have landed: 1, 2, 4, and 10 are open items in `TODO.md`; 8 is reserved as FR-013 and FR-014, and 6 as FR-015; 3 shapes the voice in [[Brand]]; 5 shapes [[Security and Privacy]] and [[Firmware]]; 9 shapes HAZ-010 and [[Companion App]]. [[Roadmap]] shows where they sit in the phases.
