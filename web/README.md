# web/

Browser code for the demo page (`demo.html` at the repository root). The page
is one file with no network loads, so nothing here is served on its own: it is
copied into the page by a generator and tested with Node.

## panel/

- `panel/panel.js` draws a display screen as the real 1-bit pixels of an
  e-paper panel. It is an integer-only port of the Python reference rasterizer
  (`src/lightkeeper/infrastructure/panel_layout.py`, which plans every line,
  band and frame, and `epaper_bitmap.py`, which draws the plan), so the demo
  shows exactly what a panel would.
  - A classic script: no `import`, no `export`, no network, no storage. It
    defines one global, `globalThis.LightkeeperPanel`.
  - `renderPanel(lines, width, height, font, {stamp})` returns the packed rows
    (1 = ink, most significant bit first, each row padded to a whole byte), the
    bytes `spec/panel_vectors.json` hashes. `crc32(bytes)` and `inkCount(bytes)`
    give the two numbers each pixel vector pins.
  - The page helpers live here too, so the Node tests reach them: `parseHash`
    and `chooseState` (a deep link opens only a vector that exists, never an
    invented state), `haGlucose` (the Home Assistant tile's number, by the
    `status_payload` rule: none for STALE, NO DATA or a sensor limit, HAZ-013)
    and `glance` (the phone card mock, where STALE and NO DATA have no hero
    number).
  - Integers only, as in the Python layout: no floats and no rounding. Every
    division goes through `idiv`, which refuses a negative dividend, so no
    rounding rule can differ from Python's `//`.
- `panel/panel.test.mjs` runs every case in `spec/panel_vectors.json` (39
  vectors at six profiles, plus three stamped cases) for its CRC-32 and ink
  count, the CRC-32 check value, what the port refuses, the deep-link parser,
  and the Home Assistant number rule for every vector.

## How it reaches the page

`tools/gen_demo_panel.py` copies `panel/panel.js` byte for byte into
`demo.html`, between `// BEGIN GENERATED PANEL` and `// END GENERATED PANEL`,
followed by the data it draws with: `spec/font5x8.json` (the Keeper 5x8 font),
the spoken sentences from `spec/spoken_vectors.json`, the three lamp icons
from `assets/brand/pixel-icons.json`, the panel profiles, and the page's own
size in bytes for the colophon. The states block above it stays
`tools/gen_display_gallery.py`'s.

After changing `panel.js`, a vector, the font or the page, run (same on every
platform, from the repository root):

```sh
python tools/gen_display_gallery.py   # only if a vector changed
python tools/gen_demo_panel.py
```

Then commit `demo.html` with the change. `python tools/gen_demo_panel.py
--check` exits 1 when the block is out of date.

## Tests

Node 20 or later, no packages. Same on every platform, from the repository
root:

```sh
node --test web/panel/panel.test.mjs
```

`tests/test_demo_panel.py` runs the same command from pytest, and also asks the
port for sizes and lines the pixel vectors do not pin (the narrowest and
shortest panels the layout accepts, the sizes just past them, unknown
headlines, too many lines, characters outside the font) and compares every
answer with the Python reference. Without node those tests are skipped
locally; on CI (`CI=true`) a missing node fails them. The same file keeps the
generated block current, checks the page's colors against
`assets/brand/tokens.json`, and holds the page to one file of 512 KB or less
that loads nothing.

## Rules

- Pixel-honest: the page shows only what `renderPanel` draws, scaled by whole
  numbers with `image-rendering: pixelated`, never imitated in CSS.
- Panel text comes only from the generated states block
  (`spec/display_vectors.json`).
- Nothing moves: no timers, no animation, no simulated e-ink flash. A change is
  one redraw, made by a click, a key or a link.
