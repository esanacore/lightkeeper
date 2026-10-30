# Brand

How Lightkeeper looks and sounds, so every screen, slide, and page reads as one project. The full guide is `docs/BRAND.md` in the repository, and the assets live in `assets/brand/`. The same tokens are published as a design system for decks and app mockups.

![Lightkeeper mark](https://raw.githubusercontent.com/esanacore/lightkeeper/main/assets/brand/png/lightkeeper-mark.png)

## The idea

A lighthouse watches all night and never steers the ship. That is the project in one sentence, and the mark reduces it to geometry: one point of light and the sweep it casts, three concentric arcs inside a 60 degree sector (lens, beam, reach), held by a stem that stands in for the tower. No windows, no waves, no picture of a building. The beam always sweeps to the right, toward the next reading.

## Mark rules

- Keep clear space of at least the lamp's diameter around the mark.
- The sweep keeps its three steps and its 60 degree angle.
- Never recolor the lamp anything but Beam amber or the mono color.
- Never add a face, a wave, a building, or a second beam.
- On e-ink, use the mono mark in ink only.
- At 16 px, use the mono mark without the outer arc.

## Color

Two neutral families and one accent. Status colors are separate from the accent and always travel with a word, so no state relies on hue alone.

| Token | Light theme | Dark theme | Role |
| --- | --- | --- | --- |
| Night | `#0E1116` | `#0E1116` | Dark background, app icon |
| Ink | `#15171C` | `#E6E5DF` (text) | Text on light, tower on light |
| Paper | `#E6E5DF` | `#DDDCD5` | E-ink panel color |
| Fog | `#ECEBE5` | `#0E1116` | Page background |
| Surface | `#F6F5F0` | `#161A21` | Cards and panels |
| Line | `#CFCDC4` | `#262B33` | Borders |
| Muted | `#5B6068` | `#9AA0A9` | Secondary text |
| Beam | `#B8730A` | `#E0A526` | Accent: eyebrows, links, the lamp |
| Beam soft | `#F1DDB4` | `#3A2E13` | Accent backgrounds |
| In range | `#2E6B4A` | `#6CC597` | Status |
| Low, urgent low | `#B3261E` | `#FF6B5E` | Status |
| High, urgent high | `#B86A00` | `#F5A341` | Status |
| Stale, no data | `#6B6F76` | `#9AA0A9` | Status |

Beam deep (`#B8730A`) is the accent on light backgrounds because the bright amber fails contrast on paper tones. Red and orange are kept apart in lightness so low and high never rely on hue alone, and every status is also printed as text. The SVG panel renderer used for the gallery and `--svg` draws in the brand's Paper (`#E6E5DF`) and Ink (`#15171C`), with Muted (`#5B6068`) only for the written stamp and a darker line color (`#7D7B74`, a proposed token in `docs/BRAND.md`) only for the panel's edge; each status keeps its 1-bit panel shape, because a black and white e-paper panel has no color at all.

`docs/BRAND.md` also carries a Keeper's Logbook section (new tokens such as Line strong, contrast measured for every color, the 1-bit shape grammar, and pixel icons), with the same tokens in `assets/brand/tokens.json`. Those additions wait for Eric's approval; this page will mirror them once they are approved.

## Type

- Display: Bricolage Grotesque, weights 600 to 800, tight tracking on large sizes.
- Body: IBM Plex Sans, 400 to 600.
- Data and panels: IBM Plex Mono. Everything an e-ink panel shows is monospace, and every digit column uses tabular numerals.

Scale: 12, 14, 16, 20, 28, 40, 64 px on screens; 24, 28, 32, 44, 72, 120 px on slides.

## Voice

Plain, calm, and specific. Short sentences. Say what the screen shows and how old it is. Never "alarm"; say "notice" or "nudge". Never medical advice. Every public surface carries one line:

> Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.

The "never alarm" rule is not a style preference. It came from [[Community Research]], where commercial nightlights that call themselves "passive awareness" were the devices people trusted most honestly, and where Nightscout's own wording ("do not rely only on Nightscout") set the standard. It also mirrors the safety boundary: primary alarms stay on the phone. See [[Safety]].

## Photography and imagery

No stock photos of people or of medical devices we did not photograph. When imagery is needed, use our own photos of real displays on the bench or bedside, rendered panel images from the gallery in [[Display States]], and the mark. Hardware photos go in `assets/photos/` with the device and date in the file name.

## Asset list

| File | Use |
| --- | --- |
| `assets/brand/lightkeeper-mark.svg` | On light backgrounds (ink tower, amber lamp) |
| `assets/brand/lightkeeper-mark-dark.svg` | On dark backgrounds (paper tower, amber lamp) |
| `assets/brand/lightkeeper-mark-mono.svg` | Single color, inherits `currentColor`; for favicons, watch faces, e-ink |
| `assets/brand/lightkeeper-wordmark.svg` | Horizontal lockup, mark plus the name in Bricolage Grotesque |
| `assets/brand/app-icon.svg` | 1024 px iOS app icon source (night background, rounded by iOS) |
| `assets/brand/social-preview.svg` | 1280 by 640 GitHub social preview (upload in repository Settings) |
| `assets/brand/palette.svg` | The color table above as an image |
| `assets/brand/png/` | Rendered PNGs of all of the above |

![Social preview](https://raw.githubusercontent.com/esanacore/lightkeeper/main/assets/brand/png/social-preview.png)

The iOS app in [[Companion App]] uses the app icon source, and the Android app's launcher icon is built from `assets/brand/png/app-icon.png`, with the mono mark as its monochrome layer. The Xteink firmware in [[Firmware]] will use the mono mark in ink on its e-paper panel.
