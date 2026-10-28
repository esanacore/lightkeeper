/*
 * Lightkeeper panel pixels for the browser, and for Node in the tests.
 *
 * An integer-only port of the Python reference rasterizer
 * (src/lightkeeper/infrastructure/panel_layout.py, which plans every line,
 * band and frame, and epaper_bitmap.py, which draws the plan). The demo page
 * draws a screen with it, so the page shows exactly the 1-bit pixels a panel
 * would. spec/panel_vectors.json pins every vector at every panel profile by
 * the CRC-32 of its packed rows and its ink count; web/panel/panel.test.mjs
 * checks every case, and tests/test_demo_panel.py checks more sizes against
 * the Python reference.
 *
 * A classic script with no import or export: tools/gen_demo_panel.py copies it
 * byte for byte into demo.html, which stays one file. It defines
 * globalThis.LightkeeperPanel and nothing else.
 *
 * Integers only, as in the Python plan: no floats, no rounding, and every
 * division goes through idiv, which refuses a negative dividend, so no
 * rounding rule can differ from Python's //. Nothing here moves or blinks:
 * one call draws one still image.
 *
 * The page helpers at the end (the deep-link parser, the Home Assistant
 * number rule and the glance model for the phone mock) live here too, so the
 * Node tests can reach them.
 */
(function (root) {
  "use strict";

  // Keeper 5x8: the layout is defined for this cell size.
  const GLYPH_WIDTH = 5;
  const GLYPH_HEIGHT = 8;
  const CAP_ROWS = GLYPH_HEIGHT - 1; // rows above the baseline; the last is for descenders

  const PLAIN = "plain";
  const RULE = "rule";
  const INVERSE = "inverse";
  const STALE = "stale";
  const DASHED = "dashed";

  // Keyed by the exact headline text; anything else gets UNKNOWN_TREATMENT.
  const TREATMENTS = Object.freeze({
    "IN RANGE": PLAIN,
    LOW: RULE,
    HIGH: RULE,
    "URGENT LOW": INVERSE,
    "URGENT HIGH": INVERSE,
    "STALE - DO NOT TRUST": STALE,
    "NO DATA": DASHED,
  });
  const UNKNOWN_TREATMENT = DASHED;
  const FRESH = [PLAIN, RULE, INVERSE];

  // Line roles, in glance order.
  const HEADLINE = "headline";
  const VALUE = "value";
  const LAST = "last";
  const AGE = "age";
  const CONTEXT = "context";
  const STAMP = "stamp";

  const BAND_PAD = 2;
  const RULE_THICKNESS = 2;
  const HATCH_WIDTH = 4;
  const HATCH_PITCH = 4;
  const DASH_WIDTH = 2;
  const DASH_ON = 4;
  const DASH_OFF = 4;
  const MIN_GAP = 2;
  const READABLE_SCALE = 2;
  const RESERVED_BODY_LINES = 3;
  const STAMP_MIN_SCALE = 2;
  const STAMP_SAMPLE = "00:00";
  const REFERENCE_HEADLINE = "IN RANGE";
  const WIDEST_LINE = "Confirm on primary device";
  const MAX_SIDE = 4096;

  // The same names spec/panel_vectors.json uses, so the tests can compare them.
  const CONSTANTS = Object.freeze({
    band_pad: BAND_PAD,
    rule_thickness: RULE_THICKNESS,
    hatch_width: HATCH_WIDTH,
    hatch_pitch: HATCH_PITCH,
    dash_width: DASH_WIDTH,
    dash_on: DASH_ON,
    dash_off: DASH_OFF,
    min_gap: MIN_GAP,
    readable_scale: READABLE_SCALE,
    reserved_body_lines: RESERVED_BODY_LINES,
    stamp_min_scale: STAMP_MIN_SCALE,
    reference_headline: REFERENCE_HEADLINE,
    widest_line: WIDEST_LINE,
    max_side: MAX_SIDE,
  });

  const STAMP_TEXT = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;

  function own(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  // Python's // for the only case the layout uses: a dividend that is not
  // negative and a positive divisor. The subtraction leaves an exact multiple,
  // so the division is exact too.
  function idiv(a, b) {
    if (!(Number.isInteger(a) && Number.isInteger(b) && a >= 0 && b > 0)) {
      throw new RangeError(`idiv(${a}, ${b}): the layout divides only whole numbers, never negative`);
    }
    return (a - (a % b)) / b;
  }

  function sum(values) {
    return values.reduce((total, value) => total + value, 0);
  }

  // A string's characters as Python iterates them: by code point.
  function chars(text) {
    return Array.from(text);
  }

  function treatment(headline) {
    return own(TREATMENTS, headline) ? TREATMENTS[headline] : UNKNOWN_TREATMENT;
  }

  function glyphGap(scale) {
    return Math.max(1, idiv(scale, 2));
  }

  function textWidth(text, scale) {
    const count = chars(text).length;
    if (count === 0) {
      return 0;
    }
    return count * GLYPH_WIDTH * scale + (count - 1) * glyphGap(scale);
  }

  // Largest whole-number scale, up to maxScale, at which every line fits.
  function fitScale(lines, usableWidth, maxScale) {
    for (let scale = maxScale; scale > 1; scale -= 1) {
      if (lines.every((line) => textWidth(line, scale) <= usableWidth)) {
        return scale;
      }
    }
    return 1;
  }

  function margin(height) {
    return Math.max(4, idiv(height * 6 + 50, 100));
  }

  function headlineCap(height) {
    return Math.max(4, idiv(height, 32));
  }

  function bodyCap(bandScale) {
    return Math.min(bandScale, Math.max(3, idiv(bandScale, 2)));
  }

  function stampScale(width, height) {
    const contentWidth = width - 2 * margin(height);
    return fitScale([STAMP_SAMPLE], contentWidth, Math.max(STAMP_MIN_SCALE, idiv(height, 240)));
  }

  function bodyReserve(strip) {
    return RESERVED_BODY_LINES * GLYPH_HEIGHT + (RESERVED_BODY_LINES + 1) * MIN_GAP + strip;
  }

  function minContentWidth() {
    // The first of the longest headlines, as Python's max(TREATMENTS, key=len).
    const headline = Object.keys(TREATMENTS).reduce((best, word) =>
      chars(word).length > chars(best).length ? word : best,
    );
    return Math.max(textWidth(WIDEST_LINE, 1), 2 * BAND_PAD + textWidth(headline, 1));
  }

  function minContentHeight(width, height) {
    const strip = GLYPH_HEIGHT * stampScale(width, height) + MIN_GAP;
    return 2 * BAND_PAD + GLYPH_HEIGHT + bodyReserve(strip);
  }

  // Refuse a panel the layout cannot draw every screen on, as panel_layout.check_size does.
  function checkSize(width, height) {
    const whole = Number.isInteger(width) && Number.isInteger(height);
    if (!(whole && width >= 1 && width <= MAX_SIDE && height >= 1 && height <= MAX_SIDE)) {
      throw new RangeError(`panel ${width}x${height} must be 1 to ${MAX_SIDE} pixels on a side`);
    }
    const edge = margin(height);
    const needWidth = minContentWidth();
    if (width - 2 * edge < needWidth) {
      throw new RangeError(
        `panel ${width}x${height} is too narrow: at ${height} px tall the margins take ` +
          `${2 * edge} px, and '${WIDEST_LINE}' needs ${needWidth} px between them, ` +
          `${2 * edge + needWidth} px in all`,
      );
    }
    const needHeight = minContentHeight(width, height);
    if (height - 2 * edge < needHeight) {
      throw new RangeError(
        `panel ${width}x${height} is too short: the margins take ${2 * edge} px, and the ` +
          `headline band and a four-line screen with its stamp need ${needHeight} px between them`,
      );
    }
  }

  function checkStamp(stamp) {
    if (typeof stamp !== "string" || !STAMP_TEXT.test(stamp)) {
      throw new RangeError(`stamp must be a 24-hour HH:MM, got ${JSON.stringify(stamp)}`);
    }
  }

  function rolesFor(kind, count) {
    let first = [];
    if (FRESH.includes(kind)) {
      first = [VALUE, AGE];
    } else if (kind === STALE) {
      first = [LAST, AGE];
    }
    const roles = [];
    for (let i = 0; i < count; i += 1) {
      roles.push(i < first.length ? first[i] : CONTEXT);
    }
    return roles;
  }

  function box(x, y, w, h) {
    return { x, y, w, h };
  }

  function place(text, role, x, y, scale) {
    return { text, role, x, y, scale, tall: scale, width: textWidth(text, scale), height: GLYPH_HEIGHT * scale };
  }

  function placeRight(text, right, y, scale) {
    return place(text, STAMP, right - textWidth(text, scale), y, scale);
  }

  // A rule through the middle of the line's capitals: 1 px at scale 2 or less, else 2.
  function strikeBox(line) {
    const thickness = line.scale <= 2 ? 1 : 2;
    const middle = line.y + idiv(CAP_ROWS * line.scale, 2) - idiv(thickness, 2);
    return box(line.x, middle, line.width, thickness);
  }

  // The texture ring for STALE or DASHED, centred in the margin.
  function frameFor(kind, edge, width, height) {
    if (kind !== STALE && kind !== DASHED) {
      return null;
    }
    const thickness = kind === STALE ? HATCH_WIDTH : DASH_WIDTH;
    const inset = idiv(edge - thickness, 2);
    return { kind, box: box(inset, inset, width - 2 * inset, height - 2 * inset), thickness };
  }

  // Lay out lines on a width x height panel: the same plan as panel_layout.plan_panel.
  function planPanel(lines, width, height, stamp) {
    checkSize(width, height);
    if (!Array.isArray(lines) || lines.length === 0) {
      throw new RangeError("nothing to draw: lines is empty");
    }
    if (!lines.every((line) => typeof line === "string")) {
      throw new TypeError("every line must be a string");
    }
    const stamped = stamp !== undefined && stamp !== null;
    if (stamped) {
      checkStamp(stamp);
    }

    const edge = margin(height);
    const content = box(edge, edge, width - 2 * edge, height - 2 * edge);
    const kind = treatment(lines[0]);
    const stampSize = stampScale(width, height);
    const strip = stamped ? GLYPH_HEIGHT * stampSize + MIN_GAP : 0;

    // The band: one height per panel, sized from IN RANGE.
    const inner = content.w - 2 * BAND_PAD;
    const reserve = bodyReserve(strip);
    const tallest = idiv(Math.max(0, content.h - 2 * BAND_PAD - reserve), GLYPH_HEIGHT);
    const bandCap = Math.max(1, Math.min(headlineCap(height), tallest));
    const bandScale = fitScale([REFERENCE_HEADLINE], inner, bandCap);
    const band = box(content.x, content.y, content.w, 2 * BAND_PAD + GLYPH_HEIGHT * bandScale);
    const headScale = fitScale([lines[0]], inner, bandScale);
    const headline = {
      text: lines[0],
      role: HEADLINE,
      x: band.x + BAND_PAD,
      y: band.y + BAND_PAD,
      scale: headScale,
      tall: bandScale,
      width: textWidth(lines[0], headScale),
      height: GLYPH_HEIGHT * bandScale,
    };

    const body = lines.slice(1);
    const roles = rolesFor(kind, body.length);
    const withRole = (role) => body.filter((_, i) => roles[i] === role);
    const valueLines = withRole(VALUE);
    const ageLines = withRole(AGE);
    const smallLines = withRole(LAST).concat(withRole(CONTEXT));

    // Widest that fits: the hero up to the headline, the age up to the hero,
    // the rest up to the age (and, on STALE, up to the headline as well).
    const cap = bodyCap(bandScale);
    const value = fitScale(valueLines, content.w, headScale);
    const age = fitScale(ageLines, content.w, valueLines.length ? Math.min(cap, value) : cap);
    let smallCap = ageLines.length ? Math.min(cap, age) : cap;
    if (kind === STALE) {
      smallCap = Math.min(smallCap, headScale);
    }
    const sizes = { value, age, small: fitScale(smallLines, content.w, smallCap) };
    const sizeOf = (role) => (role === VALUE ? sizes.value : role === AGE ? sizes.age : sizes.small);

    // The stamp sits at the right of the age row when it fits there beside
    // the age and a one-character gap; otherwise it gets the bottom strip.
    const stampChars = stamped ? stamp : "";
    const onAgeRow =
      stampChars !== "" &&
      ageLines.length > 0 &&
      textWidth(ageLines[0], age) + GLYPH_WIDTH * age + textWidth(stampChars, stampSize) <= content.w;
    const top = band.y + band.h;
    const bottom = content.y + content.h - (stampChars !== "" && !onAgeRow ? strip : 0);

    // Each line's row height in glyph cells: the age row is as tall as its stamp.
    const rowScales = () =>
      roles.map((role) => (role === AGE && onAgeRow ? Math.max(sizeOf(role), stampSize) : sizeOf(role)));

    // Shrink in glance order until the lines and their gaps fit the height:
    // context to a readable 2, the hero down to the age, then context to 1,
    // then the age.
    const gaps = body.length + 1;
    while (GLYPH_HEIGHT * sum(rowScales()) + gaps * MIN_GAP > bottom - top) {
      if (smallLines.length && sizes.small > READABLE_SCALE) {
        sizes.small -= 1;
      } else if (valueLines.length && sizes.value > (ageLines.length ? sizes.age : 1)) {
        sizes.value -= 1;
      } else if (smallLines.length && sizes.small > 1) {
        sizes.small -= 1;
      } else if (ageLines.length && sizes.age > 1) {
        sizes.age -= 1;
      } else {
        break; // still too tall: the lines past the content box are clipped
      }
    }

    const rows = rowScales();
    const gap = idiv(Math.max(0, bottom - top - GLYPH_HEIGHT * sum(rows)), gaps);
    const placed = [];
    let stampLine = null;
    let y = top + gap;
    body.forEach((text, i) => {
      const role = roles[i];
      const row = rows[i];
      const scale = sizeOf(role);
      // Text sharing a row shares its baseline.
      placed.push(place(text, role, content.x, y + CAP_ROWS * (row - scale), scale));
      if (role === AGE && onAgeRow) {
        const stampY = y + CAP_ROWS * (row - stampSize);
        stampLine = placeRight(stampChars, content.x + content.w, stampY, stampSize);
      }
      y += GLYPH_HEIGHT * row + gap;
    });
    if (stampChars !== "" && !onAgeRow) {
      const stampY = content.y + content.h - GLYPH_HEIGHT * stampSize;
      stampLine = placeRight(stampChars, content.x + content.w, stampY, stampSize);
    }

    return {
      width,
      height,
      margin: edge,
      treatment: kind,
      content,
      band,
      bandScale,
      headline,
      lines: placed,
      stamp: stampLine,
      inkBand: kind === INVERSE || kind === STALE ? band : null,
      rule:
        kind === RULE
          ? box(content.x, band.y + band.h - RULE_THICKNESS, content.w, RULE_THICKNESS)
          : null,
      // Under a STALE headline the first line is always the 'last:' line.
      strike: kind === STALE && placed.length ? strikeBox(placed[0]) : null,
      frame: frameFor(kind, edge, width, height),
    };
  }

  // --- drawing ---------------------------------------------------------------

  const checkedFonts = new WeakSet();

  function checkFont(font) {
    if (checkedFonts.has(font)) {
      return;
    }
    if (!font || font.glyph_width !== GLYPH_WIDTH || font.glyph_height !== GLYPH_HEIGHT) {
      throw new TypeError("the panel layout is defined for Keeper 5x8 (spec/font5x8.json)");
    }
    const glyphs = font.glyphs;
    if (!glyphs || !own(glyphs, font.fallback)) {
      throw new TypeError("the font has no fallback glyph");
    }
    for (const char of Object.keys(glyphs)) {
      const rows = glyphs[char];
      const wellFormed =
        Array.isArray(rows) &&
        rows.length === GLYPH_HEIGHT &&
        rows.every((row) => typeof row === "string" && /^[#.]{5}$/.test(row));
      if (!wellFormed) {
        throw new TypeError(`glyph ${JSON.stringify(char)} is not eight rows of five cells`);
      }
    }
    checkedFonts.add(font);
  }

  function glyph(font, char) {
    return own(font.glyphs, char) ? font.glyphs[char] : font.glyphs[font.fallback];
  }

  // Ink a rectangle (or clear it to paper), clipped to the panel.
  function fill(bitmap, x, y, w, h, ink) {
    const left = Math.max(0, x);
    const right = Math.min(bitmap.width, x + w);
    if (left >= right) {
      return;
    }
    const value = ink ? 1 : 0;
    const last = Math.min(bitmap.height, y + h);
    for (let row = Math.max(0, y); row < last; row += 1) {
      const start = row * bitmap.width;
      bitmap.ink.fill(value, start + left, start + right);
    }
  }

  // Draw text with its top-left corner at (x, y). `tall` stretches the glyphs
  // vertically, so a narrowed headline keeps the band's height.
  function drawText(bitmap, font, text, x, y, scale, tall, ink) {
    const sy = Math.max(scale, tall);
    let left = x;
    for (const char of text) {
      const rows = glyph(font, char);
      for (let row = 0; row < rows.length; row += 1) {
        for (let col = 0; col < rows[row].length; col += 1) {
          if (rows[row][col] === "#") {
            fill(bitmap, left + col * scale, y + row * sy, scale, sy, ink);
          }
        }
      }
      left += GLYPH_WIDTH * scale + glyphGap(scale);
    }
  }

  function drawLine(bitmap, font, line, ink) {
    drawText(bitmap, font, line.text, line.x, line.y, line.scale, line.tall, ink);
  }

  // A ring `thickness` wide just inside the box: hatched for STALE, else dashed.
  function drawFrame(bitmap, frame) {
    const { kind, box: ring, thickness } = frame;
    const period = DASH_ON + DASH_OFF;
    for (let y = ring.y; y < ring.y + ring.h; y += 1) {
      const across = y < ring.y + thickness || y >= ring.y + ring.h - thickness;
      const columns = [];
      if (across) {
        for (let x = ring.x; x < ring.x + ring.w; x += 1) {
          columns.push(x);
        }
      } else {
        for (let x = ring.x; x < ring.x + thickness; x += 1) {
          columns.push(x);
        }
        for (let x = ring.x + ring.w - thickness; x < ring.x + ring.w; x += 1) {
          columns.push(x);
        }
      }
      for (const x of columns) {
        let on;
        if (kind === DASHED) {
          const along = across ? x - ring.x : y - ring.y;
          on = along % period < DASH_ON;
        } else {
          on = (x + y) % HATCH_PITCH === 0;
        }
        if (on) {
          bitmap.ink[y * bitmap.width + x] = 1;
        }
      }
    }
  }

  // Band, headline, rule, strike, lines, stamp, then the frame. Only the
  // headline on an ink band clears pixels; everything after it adds ink.
  function drawPlan(plan, font) {
    checkFont(font);
    const bitmap = { width: plan.width, height: plan.height, ink: new Uint8Array(plan.width * plan.height) };
    if (plan.inkBand !== null) {
      const band = plan.inkBand;
      fill(bitmap, band.x, band.y, band.w, band.h, true);
    }
    drawLine(bitmap, font, plan.headline, plan.inkBand === null);
    for (const mark of [plan.rule, plan.strike]) {
      if (mark !== null) {
        fill(bitmap, mark.x, mark.y, mark.w, mark.h, true);
      }
    }
    for (const line of plan.lines) {
      drawLine(bitmap, font, line, true);
    }
    if (plan.stamp !== null) {
      drawLine(bitmap, font, plan.stamp, true);
    }
    if (plan.frame !== null) {
      drawFrame(bitmap, plan.frame);
    }
    return bitmap;
  }

  // Rows top to bottom, 1 = ink, eight pixels a byte, most significant bit
  // first, each row padded with paper (0 bits) to a whole byte.
  function packRows(bitmap) {
    const stride = idiv(bitmap.width + 7, 8);
    const packed = new Uint8Array(stride * bitmap.height);
    for (let y = 0; y < bitmap.height; y += 1) {
      for (let x = 0; x < bitmap.width; x += 1) {
        if (bitmap.ink[y * bitmap.width + x]) {
          packed[y * stride + (x >> 3)] |= 0x80 >> (x & 7);
        }
      }
    }
    return packed;
  }

  // The packed rows of `lines` drawn on a width x height panel with the
  // Keeper 5x8 font (spec/font5x8.json). options.stamp is an optional HH:MM.
  function renderPanel(lines, width, height, font, options) {
    const stamp = options ? options.stamp : undefined;
    return packRows(drawPlan(planPanel(lines, width, height, stamp), font));
  }

  function rowBytes(width) {
    return idiv(width + 7, 8);
  }

  // True where pixel (x, y) of the packed rows is ink.
  function isInk(packed, width, x, y) {
    return (packed[y * rowBytes(width) + (x >> 3)] & (0x80 >> (x & 7))) !== 0;
  }

  function inkCount(packed) {
    let count = 0;
    for (const byte of packed) {
      for (let bits = byte; bits; bits &= bits - 1) {
        count += 1;
      }
    }
    return count;
  }

  // CRC-32/ISO-HDLC, as zlib.crc32 computes it.
  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
      crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  // --- page helpers (demo.html) ---------------------------------------------

  const STATE_NAME = /^[a-z0-9_]{1,64}$/;

  // The vector name a location hash asks for, or null for anything else.
  function parseHash(hash) {
    if (typeof hash !== "string") {
      return null;
    }
    let name = hash.charAt(0) === "#" ? hash.slice(1) : hash;
    try {
      name = decodeURIComponent(name);
    } catch (error) {
      return null; // a malformed escape names no state
    }
    return STATE_NAME.test(name) ? name : null;
  }

  // The state a deep link opens: an existing vector, or the fallback. A link
  // can only select a state that exists; it never makes one up.
  function chooseState(hash, states, fallback) {
    const name = parseHash(hash);
    return name !== null && own(states, name) ? name : fallback;
  }

  const FRESH_LEVELS = ["URGENT LOW", "LOW", "IN RANGE", "HIGH", "URGENT HIGH"];
  const MEASURED = /^([0-9]{1,3}) mg\/dL(?: |$)/;

  // The glucose number a Home Assistant tile shows, by the status_payload rule
  // (HAZ-013): a number only for a fresh, measured reading. STALE, NO DATA, a
  // sensor sentinel, or anything this cannot place gives null, which Home
  // Assistant shows as "unknown".
  function haGlucose(level, lines) {
    if (!FRESH_LEVELS.includes(level) || !Array.isArray(lines)) {
      return null;
    }
    if (!FRESH.includes(treatment(lines[0])) || typeof lines[1] !== "string") {
      return null;
    }
    const match = MEASURED.exec(lines[1]);
    if (match === null) {
      return null; // sentinels are words: LOW (<40), HIGH (>400)
    }
    const mgdl = Number(match[1]);
    return mgdl >= 40 && mgdl <= 400 ? mgdl : null;
  }

  const VALUE_PARTS = /^([0-9]+) (mg\/dL) (.+)$/;

  // What a phone card shows, made only of the vector lines, in glance order:
  // the status, then the hero (a number with its unit and arrow, or the
  // sentinel words), the struck 'last:' line on STALE, the age, and the
  // context. STALE and NO DATA (and any unknown headline) have no hero, so an
  // old value is never the largest thing on the card.
  function glance(lines) {
    const kind = treatment(lines[0]);
    const model = { treatment: kind, status: lines[0], hero: null, struck: null, age: null, context: [] };
    if (FRESH.includes(kind)) {
      if (lines.length > 1) {
        const parts = VALUE_PARTS.exec(lines[1]);
        model.hero = parts ? { digits: parts[1], unit: parts[2], arrow: parts[3] } : { word: lines[1] };
      }
      model.age = lines.length > 2 ? lines[2] : null;
      model.context = lines.slice(3);
    } else if (kind === STALE) {
      model.struck = lines.length > 1 ? lines[1] : null;
      model.age = lines.length > 2 ? lines[2] : null;
      model.context = lines.slice(3);
    } else {
      model.context = lines.slice(1);
    }
    return model;
  }

  root.LightkeeperPanel = Object.freeze({
    CONSTANTS,
    TREATMENTS,
    UNKNOWN_TREATMENT,
    treatment,
    checkSize,
    planPanel,
    renderPanel,
    rowBytes,
    isInk,
    inkCount,
    crc32,
    parseHash,
    chooseState,
    haGlucose,
    glance,
  });
})(globalThis);
