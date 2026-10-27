# Bill of Materials

Generated from `hardware/bom/bom.csv` by `tools/gen_bom.py`; edit the CSV, not this file. Prices are US list prices and move; each row says when its stock was last checked. Buying advice and alternatives are in `docs/HARDWARE.md`; the enclosure is in `hardware/enclosure/` and the assembly steps are in `docs/ASSEMBLY.md`.

Nothing here is a medical device. These are secondary displays; the primary CGM app and its alarms stay on the phone. See `docs/SAFETY.md`.

## Bedside display (Raspberry Pi Zero 2 WH + 2.9" e-paper)

The first display a household can rely on. Runs the Python code as it is, in the hardened systemd service, inside the printed enclosure from `hardware/enclosure/` (two parts, no supports, four M2.5 screws).

| Item | Exact name | Qty | Unit price | Stock | Source |
| --- | --- | --- | --- | --- | --- |
| Computer | Raspberry Pi Zero 2 WH (pre-soldered header) | 1 | $19.60 to $20.75 | sold out at CanaKit / PiShop.us / Adafruit on 2026-10-25 | [CanaKit](https://www.canakit.com/raspberry-pi-zero-2-w.html) |
| Display | Waveshare 2.9inch Touch e-Paper HAT (SKU 19967) | 1 | $24.99 | Add to Cart on 2026-10-25 | [Waveshare](https://www.waveshare.com/2.9inch-touch-e-paper-hat.htm) |
| Power supply | 5 V 2.5 A micro-USB supply (official Raspberry Pi or kit) | 1 | $8.00 to $12.00 | not checked | [Any](https://www.raspberrypi.com/products/micro-usb-power-supply/) |
| Power cable | Right-angle (90 degree) micro-USB cable, plug body under 7 mm thick | 1 | $6.00 to $9.00 | not checked | [Any](https://www.amazon.com/s?k=right+angle+micro+usb+cable+90+degree) |
| Storage | 32 GB microSD A1 (SanDisk or Samsung) | 1 | $8.00 | not checked | [Any](https://www.amazon.com/s?k=32GB+microSD+A1+SanDisk) |
| Enclosure front bezel | Printed: hardware/enclosure/bedside.scad part=bezel | 1 | $0.70 to $1.20 | printed | 3D printer |
| Enclosure back cover | Printed: hardware/enclosure/bedside.scad part=back | 1 | $0.20 to $0.40 | printed | 3D printer |
| Case screws | M2.5 x 8 mm pan head self-tapping | 4 | $0.05 to $0.10 | not checked | [Any](https://www.amazon.com/s?k=M2.5+self+tapping+screw+assortment) |

**Subtotal:** $67.69 to $76.74

Notes:

- **Computer:** The H matters: the HAT needs the header. CanaKit Starter Kit with pre-soldered header (PI-Z2WH-STR32-C4-BLK) was $89.95 and in stock.
- **Display:** 296x128 black/white; the plain HAT (D) is discontinued; touch can go unused. Avoid (B) red and (G) four-colour versions.
- **Power supply:** Included in most kits.
- **Power cable:** A straight plug does not fit below the Pi inside the case; the cable runs along the floor and out the back notch. Use it with a 5 V 2.5 A supply that takes a USB-A cable, or a supply with a captive right-angle lead.
- **Enclosure front bezel:** PETG or PLA. 47 g solid volume (37.9 cm3, most of it the plinth); about 30 to 35 g at 20% infill. Prints face down, no supports. Holds the glass; the HAT has no mounting holes.
- **Enclosure back cover:** PETG or PLA. 11 g solid volume (8.6 cm3). Prints outer face down, posts up, no supports.
- **Case screws:** Back cover to bezel.

## Pocket display (Xteink X4 Pro)

The ESP32-C3 pocket reader the firmware targets (ADR-0006). No parts beyond the reader.

| Item | Exact name | Qty | Unit price | Stock | Source |
| --- | --- | --- | --- | --- | --- |
| Reader | Xteink X4 Pro (4.3 inch e-ink; front light; touch) | 1 | $99.00 to $129.00 | pre-order (Mist Gray) shipping from 2026-10-28 | [Xteink](https://www.xteink.com/products/xteink-x4-pro-pocket-ereader) |

**Subtotal:** $99.00 to $129.00

Notes:

- **Reader:** $99 sale; list $109 to $129. Buy only from the Xteink Official Store. The X4 Classic ($79) has no front light.

## Firmware bench board (Waveshare ESP32-S3-ePaper-1.54)

Develop and test firmware here, not on the device the person with diabetes carries.

| Item | Exact name | Qty | Unit price | Stock | Source |
| --- | --- | --- | --- | --- | --- |
| Board | Waveshare ESP32-S3-ePaper-1.54 (with battery) | 1 | $15.99 to $22.99 | Add to Cart on 2026-10-25 | [Waveshare](https://www.waveshare.com/esp32-s3-epaper-1.54.htm) |
| Battery | 3.7 V LiPo 500 to 1000 mAh with MX1.25 2-pin connector | 1 | $8.00 to $12.00 | not checked | [Any](https://www.amazon.com/s?k=3.7V+LiPo+1000mAh+MX1.25) |
| Cable | USB-C data cable | 1 | $6.00 | not checked | Any |

**Subtotal:** $29.99 to $40.99

Notes:

- **Board:** 200x200 black/white; the plain -1.54 listing includes a battery; -1.54-EN has none; avoid the 1.54G four-colour version.
- **Battery:** Check the connector; JST-PH will not fit.
- **Cable:** Many charge-only cables will not flash.

## Optional extras (after the first displays work)

Not needed for a first build.

| Item | Exact name | Qty | Unit price | Stock | Source |
| --- | --- | --- | --- | --- | --- |
| Second bedside display | Second 2.9inch e-Paper HAT plus Pi Zero 2 WH | 1 | $45.00 | see bedside rows | as above |
| Across-the-room display | Waveshare 7.5inch e-Paper HAT 800x480 black/white | 1 | $65.00 | not checked | [Waveshare](https://www.amazon.com/s?k=Waveshare+7.5inch+e-Paper+HAT+800x480) |
| Haptics | 3 V coin vibration motor or USB bed-shaker puck | 1 | $5.00 to $25.00 | not checked | [Any](https://www.amazon.com/s?k=bed+shaker+vibration+alarm+USB) |
| Second pocket unit | Xteink X3 | 1 | $69.00 | not checked | [Xteink](https://www.xteink.com) |

**Subtotal:** $184.00 to $204.00

Notes:

- **Second bedside display:** A display where the builder is (kitchen; desk).
- **Across-the-room display:** Same Pi and code; needs a frame or stand.
- **Haptics:** Community research: partners hated sound and liked haptics.
- **Second pocket unit:** Same firmware.
