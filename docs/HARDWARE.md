# Hardware Buyer's Guide

What to buy to run and develop Lightkeeper's displays, in the order to buy it, with Amazon search links and first-party alternatives. Prices are October 2026 US list prices and move; Amazon listings and ASINs change often, so links below search by exact product name rather than pinning a listing that may vanish. Always check the seller: Waveshare, Raspberry Pi resellers (Vilros, PiShop, CanaKit), and the "Xteink Official Store" are the ones to buy from.

Nothing here is a medical device. These are secondary displays; the primary CGM app and its alarms stay on the phone. See `docs/SAFETY.md`.

## Tier 1: first displays (about $180, prices as of 2026-10)

### 1. Bedside e-ink display: Raspberry Pi Zero 2 W + 2.9" e-paper HAT

Runs the Python code as it is, so the whole Python suite already covers it. This is the first display a household can rely on.

| Part | Exact name to search | Approx. price | Where |
| --- | --- | --- | --- |
| Computer | **Raspberry Pi Zero 2 WH** (the H means the 40-pin header is pre-soldered; you need that for the HAT) | $18 to $22 bare, $35 to $50 as a kit | [Amazon search](https://www.amazon.com/s?k=Raspberry+Pi+Zero+2+WH), [Vilros kit](https://vilros.com/products/vilros-raspberry-pi-zero-2-w-max-kit-copy), [Pimoroni Essentials Kit](https://shop.pimoroni.com/products/raspberry-pi-zero-2-w-essentials-kit) |
| Display | **Waveshare 2.9inch e-Paper HAT, 296x128, black/white** (model "2.9inch e-Paper Module" or "HAT"; avoid the (B)/(C) red or yellow versions, they refresh in 15 seconds and flash) | $22 to $28 | [Amazon search](https://www.amazon.com/s?k=Waveshare+2.9inch+e-Paper+HAT+296x128), [Waveshare wiki](https://www.waveshare.com/wiki/2.9inch_e-Paper_HAT_(D)_Manual) |
| Power | 5 V 2.5 A micro-USB supply (official Raspberry Pi supply or the one in the kit) | $8 to $12 | in most kits |
| Storage | 32 GB microSD, A1 class (SanDisk or Samsung) | $8 | [Amazon search](https://www.amazon.com/s?k=32GB+microSD+A1+SanDisk) |
| Case | Optional: a Pi Zero case with a HAT cutout, or a 3D-printed one later | $5 to $10 | [Amazon search](https://www.amazon.com/s?k=Raspberry+Pi+Zero+2+W+case+HAT) |

Alternative if you want it readable across the room: **Waveshare 7.5inch e-Paper HAT, 800x480, black/white** (about $65, [Amazon search](https://www.amazon.com/s?k=Waveshare+7.5inch+e-Paper+HAT+800x480)) on the same Pi Zero 2 WH. Same code, bigger panel, needs a frame or stand.

Buy the kit version of the Pi unless you already own a micro-USB supply, a mini-HDMI adapter, and a card reader.

### 2. Pocket display: Xteink X4 Pro

The ESP32-C3 pocket e-ink reader the firmware targets (ADR-0006). Choose the Pro: its front light suits night-time checks.

| Part | Exact name | Approx. price | Where |
| --- | --- | --- | --- |
| Reader | **Xteink X4 Pro** (4.3" e-ink, front light, touchscreen). The X4 Classic ($79) is the same without the light. | $99 | [Xteink official store](https://www.xteink.com/products/xteink-x4-pro-pocket-ereader), [Amazon search](https://www.amazon.com/s?k=Xteink+X4+Pro) (buy only from "Xteink Official Store") |

Before flashing anything: back up the SD card, read the CrossPoint flashing guide and the firmware recovery page, and confirm the firmware file matches the model. Do not use an X4 Classic image on a Pro. [CrossPoint](https://www.readme.club/firmware/crosspoint), [PocketInk flash guide](https://pocketink.io/blog/xteink-x4-buy-setup-flash-guide)

### 3. Firmware bench board: Waveshare ESP32-S3-ePaper-1.54

Develop and test firmware here, not on the device the person with diabetes carries. Same ESP32 family as the Xteink, and the exact board WaveshareMon uses, so there is working prior art for Wi-Fi, TLS, deep sleep, and e-paper refresh.

| Part | Exact name | Approx. price | Where |
| --- | --- | --- | --- |
| Board | **Waveshare ESP32-S3-ePaper-1.54** (200x200 black/white, Wi-Fi, BLE, RTC, battery charging; not the "1.54G" color version) | $20 to $25 | [Waveshare store](https://www.waveshare.com/esp32-s3-epaper-1.54.htm), [Amazon search](https://www.amazon.com/s?k=Waveshare+ESP32-S3+1.54inch+e-Paper) |
| Battery | 3.7 V LiPo, 500 to 1000 mAh, with **MX1.25 2-pin** connector (check the connector; JST-PH will not fit) | $8 to $12 | [Amazon search](https://www.amazon.com/s?k=3.7V+LiPo+1000mAh+MX1.25) |
| Cable | USB-C data cable (many charge-only cables won't flash) | $6 | any |

[Waveshare wiki](https://docs.waveshare.com/ESP32-S3-ePaper-1.54), [WaveshareMon](https://github.com/psonnera/WaveshareMon)

## Tier 2: after the first displays work

| Part | Why | Approx. price | Where |
| --- | --- | --- | --- |
| Second **2.9" e-Paper HAT** + Pi Zero 2 WH | A display where Eric is (kitchen, desk) | $45 | as above |
| **Vibration motor or haptic puck** (3 V coin vibration motor, or a USB "bed shaker" alarm puck) | Partners in the research hated sound and liked haptics | $5 to $25 | [Amazon search](https://www.amazon.com/s?k=bed+shaker+vibration+alarm+USB) |
| **Waveshare 7.5" HAT** | Across-the-room bedside or kitchen board | $65 | as above |
| **Xteink X3** | A smaller second pocket unit, same firmware | $69 | Xteink store |

## Not recommended

- Any 3-color or 7-color e-paper (Spectra, ACeP, (B)/(C) models): 15 to 30 second refreshes with heavy flashing.
- M5Stack Core or M5Paper and the Ulanzi pixel clock: the projects built around them are dormant and the LCD ones have 45-minute battery life.
- Smart speakers as the low alert: fine as an extra, but the community warns against relying on one in an emergency.
- A Raspberry Pi 5 for a display: more power and heat than the job needs; a Zero 2 W is plenty.
- Generic "mini e-book readers" with unknown chips: no way to load firmware.

## Things you already have or don't need

- Home Assistant: runs on whatever hosts it now.
- Nightscout: a cloud VPS or managed host, not hardware in the apartment, since the phone must reach it from anywhere.
- A Mac: not needed. Trio builds in the browser; firmware builds with PlatformIO on Windows.

## Wiring and setup notes

- The 2.9" and 7.5" HATs plug straight onto the Pi's 40-pin header; no wiring. Enable SPI in `raspi-config`.
- On the Pi, Lightkeeper runs as a systemd service with `--watch` and the e-paper adapter (FR-007, in progress); until then `--svg` plus any image viewer works for testing.
- The ESP32-S3 board flashes over USB-C; hold BOOT while powering on to enter download mode.
- Keep a written list of what you bought, with dates, in `docs/OTS_SOFTWARE.md`'s system-level table once a device is in service, so hardware is tracked like software.

## Running total

Tier 1, buying the Pi as a kit: about $50 (bedside) + $99 (Xteink X4 Pro) + $35 (bench board and battery) = about $185.
