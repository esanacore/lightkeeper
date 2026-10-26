# Hardware

What to buy to run and develop Lightkeeper's displays, in the order to buy it. This page condenses `docs/HARDWARE.md` in the repository, which also carries search links. Prices are October 2026 US list prices and move; search by exact product name rather than trusting a pinned listing. Buy from Waveshare, established Raspberry Pi resellers (Vilros, PiShop, CanaKit), and the "Xteink Official Store" only.

Nothing here is a medical device. These are secondary displays; the primary CGM app and its alarms stay on the phone. See [[Safety]].

## Tier 1: first displays (about $195 to $250)

Checked 2026-10-25: the bare Pi Zero 2 WH was sold out at the main US resellers (CanaKit's $89.95 Starter Kit with a soldered header was in stock), Waveshare's plain 2.9 inch HAT is discontinued in favour of the Touch HAT, and the Xteink X4 Pro was on pre-order.

### Bedside e-ink display: Raspberry Pi Zero 2 WH plus a 2.9 inch e-paper HAT

This runs the Python code as it is, so the whole test suite already covers it. The bitmap the panel will show is already drawn and tested (`epaper_bitmap.py`); only the SPI driver waits for the parts. It is the first display a household can rely on.

| Part | Exact name to search | Approx. price |
| --- | --- | --- |
| Computer | Raspberry Pi Zero 2 WH. The H means the 40-pin header is pre-soldered, which the HAT needs. | about $20 bare (often sold out), $89.95 as CanaKit's Starter Kit with header |
| Display | Waveshare 2.9inch Touch e-Paper HAT, 296x128, black/white (the plain HAT (D) is discontinued; touch can go unused). Avoid the (B) red and (G) four-colour versions; they refresh in about 15 seconds and flash. | $24.99 |
| Power | 5 V 2.5 A micro-USB supply (official Raspberry Pi supply or the kit's) | $8 to $12 |
| Storage | 32 GB microSD, A1 class (SanDisk or Samsung) | $8 |
| Case | Optional: a Pi Zero case with a HAT cutout, or a 3D-printed one later | $5 to $10 |

For an across-the-room display, the Waveshare 7.5inch e-Paper HAT, 800x480, black/white (about $65) runs on the same Pi with the same code; it needs a frame or stand. Buy the kit version of the Pi unless you already own a micro-USB supply, a mini-HDMI adapter, and a card reader.

### Pocket display: Xteink X4 Pro

The ESP32-C3 pocket e-ink reader the firmware targets (ADR-0006): a 4.3 inch e-ink reader with front light and touchscreen, about $99, from the Xteink official store or the "Xteink Official Store" on Amazon. Choose the Pro; its front light suits night-time checks. The X4 Classic ($79) is the same device without the light.

Before flashing anything: back up the SD card, read the CrossPoint flashing and recovery guides, and confirm the firmware file matches the model. Do not use an X4 Classic image on a Pro. See [[Firmware]].

### Firmware bench board: Waveshare ESP32-S3-ePaper-1.54

Develop and test firmware here, not on the device the person with diabetes carries. It is the same ESP32 family as the Xteink and the exact board WaveshareMon uses, so there is working prior art.

| Part | Exact name | Approx. price |
| --- | --- | --- |
| Board | Waveshare ESP32-S3-ePaper-1.54 (200x200 black/white, Wi-Fi, BLE, RTC, battery charging). The plain "-1.54" listing includes a battery; avoid the "1.54G" four-colour version. | $15.99 to $22.99 |
| Battery | 3.7 V LiPo, 500 to 1000 mAh, with an MX1.25 2-pin connector. JST-PH will not fit. | $8 to $12 |
| Cable | USB-C data cable. Many charge-only cables will not flash. | $6 |

## Tier 2: after the first displays work

| Part | Why | Approx. price |
| --- | --- | --- |
| Second 2.9 inch e-Paper HAT plus Pi Zero 2 WH | A display where the builder is (kitchen, desk) | $45 |
| Vibration motor or haptic puck (3 V coin motor, or a USB bed-shaker alarm puck) | Partners in the research disliked sound and liked haptics | $5 to $25 |
| Waveshare 7.5 inch HAT | Across-the-room bedside or kitchen board | $65 |
| Xteink X3 | A smaller second pocket unit, same firmware | $69 |

## What not to buy

- Any 3-color or 7-color e-paper (Spectra, ACeP, the (B) and (C) models): 15 to 30 second refreshes with heavy flashing.
- M5Stack Core, M5Paper, and the Ulanzi pixel clock: the projects built around them are dormant, and the LCD ones have 45-minute battery life. See the prior-art table in [[Community Research]].
- Smart speakers as the low alert: fine as an extra, but the community warns against relying on one in an emergency.
- A Raspberry Pi 5 for a display: more power and heat than the job needs. A Zero 2 W is plenty.
- Generic "mini e-book readers" with unknown chips: no way to load firmware.

Not needed: a Mac (Trio builds in the browser, the iOS app on GitHub's macOS runners, the firmware with PlatformIO on Windows) or hardware for Nightscout, which belongs on a VPS or managed host so the phone can reach it from anywhere ([[Nightscout and Trio Setup]]).

## Wiring and setup notes

- The 2.9 inch and 7.5 inch HATs plug straight onto the Pi's 40-pin header; there is no wiring. Enable SPI with `sudo raspi-config`, Interface Options, SPI, then reboot.
- On the Pi, Lightkeeper runs as a systemd service with `--watch --interval 60 --svg /run/lightkeeper/screen.svg` and the token in a root-only `/etc/lightkeeper.env`. Until the e-paper adapter (FR-007) lands, the SVG plus any image viewer works for testing; its "written" stamp shows whether the service is alive. The service file is in `docs/SETUP.md`.
- The ESP32-S3 bench board flashes over USB-C; hold BOOT while powering on to enter download mode.
- Once a device is in service, record it with dates in `docs/OTS_SOFTWARE.md`, so hardware is tracked like software.

## Before a display is relied on

Run it beside the primary CGM app for one full sensor session and log every mismatch, freeze, or missed STALE. That is the exit evidence for Phase 4 in [[Roadmap]], and the person with diabetes decides whether the display has earned trust.
