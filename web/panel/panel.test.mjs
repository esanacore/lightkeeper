// Tests for web/panel/panel.js, the browser port of the panel rasterizer.
//
// Run from the repository root with `node --test web/panel/panel.test.mjs`
// (Node 20 or later; no packages). tests/test_demo_panel.py runs it too, so
// the Python suite fails when the port drifts.
//
// - FR-016: every case in spec/panel_vectors.json (every vector at every
//   profile, plus the stamped cases) gives the pinned CRC-32 and ink count.
// - FR-011: a deep link selects only a state that exists.
// - HAZ-013: the Home Assistant tile shows a number only for a fresh,
//   measured reading, checked for every vector against its raw entries.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInThisContext } from "node:vm";

const here = new URL(".", import.meta.url);
const read = (relative) => readFileSync(new URL(relative, here), "utf8");
const SOURCE = read("panel.js");

// A classic script: run it the way a browser runs the page's inline copy.
runInThisContext(SOURCE, { filename: "panel.js" });
const P = globalThis.LightkeeperPanel;

const PANEL = JSON.parse(read("../../spec/panel_vectors.json"));
const FONT = JSON.parse(read("../../spec/font5x8.json"));
const DISPLAY = JSON.parse(read("../../spec/display_vectors.json")).cases;
const STATES = Object.fromEntries(DISPLAY.map((c) => [c.name, { level: c.level, lines: c.lines }]));
const DEFAULT_STATE = "in_range_flat";

function render(lines, width, height, stamp) {
  return P.renderPanel(lines, width, height, FONT, stamp === undefined ? undefined : { stamp });
}

test("FR-016: CRC-32 is the standard one", () => {
  assert.equal(P.crc32(new TextEncoder().encode("123456789")), 0xcbf43926);
  assert.equal(P.crc32(new Uint8Array(0)), 0);
});

test("FR-016: every pixel vector gives its CRC-32 and ink count", () => {
  assert.equal(PANEL.panel_spec_version, 1);
  assert.equal(PANEL.cases.length, 237);
  const wrong = [];
  for (const c of PANEL.cases) {
    const packed = render(c.lines, c.width, c.height, c.stamp);
    const crc = P.crc32(packed);
    const ink = P.inkCount(packed);
    if (crc !== c.crc32 || ink !== c.ink) {
      wrong.push(`${c.vector} at ${c.profile}${c.stamp ? ` stamped ${c.stamp}` : ""}`);
    }
  }
  assert.deepEqual(wrong, []);
});

test("FR-016: every display vector is drawn at every profile", () => {
  const profiles = Object.keys(PANEL.profiles);
  assert.equal(profiles.length, 6);
  for (const profile of profiles) {
    const drawn = PANEL.cases.filter((c) => c.profile === profile && !c.stamp).map((c) => c.vector);
    assert.deepEqual(drawn.sort(), DISPLAY.map((c) => c.name).sort(), profile);
  }
});

test("FR-016: packed rows follow the written hash rule", () => {
  for (const c of PANEL.cases.filter((x) => x.profile === "waveshare_2in13")) {
    const packed = render(c.lines, c.width, c.height, c.stamp);
    const stride = Math.ceil(c.width / 8);
    assert.equal(P.rowBytes(c.width), stride);
    assert.equal(packed.length, stride * c.height);
    const pad = stride * 8 - c.width;
    assert.ok(pad > 0, "250 px rows end mid-byte, so the padding is tested");
    for (let y = 0; y < c.height; y += 1) {
      assert.equal(packed[y * stride + stride - 1] & ((1 << pad) - 1), 0, `${c.vector} row ${y}`);
    }
  }
  const packed = render(STATES.in_range_flat.lines, 296, 128);
  let ink = 0;
  for (let y = 0; y < 128; y += 1) {
    for (let x = 0; x < 296; x += 1) {
      ink += P.isInk(packed, 296, x, y) ? 1 : 0;
    }
  }
  assert.equal(ink, P.inkCount(packed));
});

test("FR-016: tables and constants match the spec", () => {
  assert.deepEqual({ ...P.TREATMENTS }, PANEL.treatments);
  assert.equal(P.UNKNOWN_TREATMENT, PANEL.unknown_treatment);
  assert.deepEqual({ ...P.CONSTANTS }, PANEL.layout.constants);
  assert.equal(FONT.name, "Keeper 5x8");
});

test("FR-016: an unknown headline gets the cautious dashed frame", () => {
  for (const headline of ["MYSTERY", "constructor", "__proto__", "toString", "in range", ""]) {
    assert.equal(P.treatment(headline), "dashed", JSON.stringify(headline));
  }
  // The margin of an unknown headline's screen is NO DATA's dashed ring, pixel for pixel.
  const width = 296;
  const height = 128;
  const known = render(["NO DATA", "Check sensor and phone"], width, height);
  const unknown = render(["toString", "Check sensor and phone"], width, height);
  const edge = P.planPanel(["NO DATA"], width, height).margin;
  let ring = 0;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (x < edge || y < edge || x >= width - edge || y >= height - edge) {
        assert.equal(P.isInk(unknown, width, x, y), P.isInk(known, width, x, y), `${x},${y}`);
        ring += P.isInk(known, width, x, y) ? 1 : 0;
      }
    }
  }
  assert.ok(ring > 0, "the dashed ring is drawn");
});

test("FR-016: refuses what the Python reference refuses", () => {
  const lines = STATES.in_range_flat.lines;
  for (const [width, height] of [
    [0, 128],
    [296, 0],
    [4097, 128],
    [296, 4097],
    [164, 128], // too narrow: 149 px of content plus two 8 px margins
    [296, 69], // too short for a four-line screen with its stamp
    [296.5, 128],
    ["296", 128],
  ]) {
    assert.throws(() => render(lines, width, height), RangeError, `${width}x${height}`);
  }
  assert.doesNotThrow(() => render(lines, 165, 128));
  assert.throws(() => render([], 296, 128), RangeError);
  assert.throws(() => render([1, 2], 296, 128), TypeError);
  for (const stamp of ["24:00", "7:05", "07:5", "07:05\n", "07:60", 705]) {
    assert.throws(() => render(lines, 296, 128, stamp), RangeError, JSON.stringify(stamp));
  }
  assert.doesNotThrow(() => render(lines, 296, 128, null));
  assert.throws(() => P.renderPanel(lines, 296, 128, { ...FONT, glyph_width: 6 }), TypeError);
  const broken = { ...FONT, glyphs: { ...FONT.glyphs, A: ["#####"] } };
  assert.throws(() => P.renderPanel(lines, 296, 128, broken), TypeError);
  const noFallback = { ...FONT, glyphs: { A: FONT.glyphs.A } };
  assert.throws(() => P.renderPanel(lines, 296, 128, noFallback), TypeError);
});

test("FR-016: a character outside the font draws as the fallback", () => {
  const odd = render(["IN RANGE", "112 mg/dL →", "3 min ago"], 296, 128);
  const fallback = render(["IN RANGE", `112 mg/dL ${FONT.fallback}`, "3 min ago"], 296, 128);
  assert.equal(P.crc32(odd), P.crc32(fallback));
});

test("FR-016: integer arithmetic only", () => {
  // Comments, then strings, then regular expression literals, leave the code's own slashes.
  const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/\/\/.*$/gm, " ")
    .replace(/"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`/g, '""')
    .replace(/([=(,:!&|?{};[]|return)\s*\/(?:[^/\\\n[]|\\.|\[(?:[^\]\\\n]|\\.)*\])+\/[a-z]*/g, "$1 R");
  for (const banned of ["Math.round", "Math.floor", "Math.ceil", "Math.trunc", "parseFloat", "toFixed"]) {
    assert.ok(!code.includes(banned), banned);
  }
  // The only division is the exact one inside idiv.
  assert.equal((code.match(/\//g) || []).length, 1);
  assert.ok(code.includes("return (a - (a % b)) / b;"));
});

test("FR-011: a deep link opens only a state that exists", () => {
  for (const name of Object.keys(STATES)) {
    assert.equal(P.chooseState(`#${name}`, STATES, DEFAULT_STATE), name);
    assert.equal(P.chooseState(name, STATES, DEFAULT_STATE), name);
  }
  assert.equal(P.chooseState("#stale_beats_urgent_low", STATES, DEFAULT_STATE), "stale_beats_urgent_low");
  assert.equal(P.chooseState("#%73tale_beats_urgent_low", STATES, DEFAULT_STATE), "stale_beats_urgent_low");
  for (const hash of [
    "",
    "#",
    "#no_such_state",
    "#STALE_BEATS_URGENT_LOW",
    "#stale_beats_urgent_low ",
    "#stale_beats_urgent_low&x=1",
    "#constructor",
    "#__proto__",
    "#toString",
    "#hasOwnProperty",
    "#%E0%A4%A",
    "#in_range_flat%00",
    `#${"a".repeat(65)}`,
    null,
    undefined,
    42,
  ]) {
    assert.equal(P.chooseState(hash, STATES, DEFAULT_STATE), DEFAULT_STATE, String(hash));
  }
  assert.equal(P.parseHash("#no_such_state"), "no_such_state");
  assert.equal(P.parseHash("#<b>"), null);
  assert.equal(P.parseHash(7), null);
});

// The entry the display classified, found from the raw vector by the rule
// spec/display_vectors.json states: bad entries are skipped and the newest
// survivor (the lower value on a timestamp tie) wins.
function survivor(c) {
  const items = c.entries ? c.entries : [c];
  const ageSeconds = (item) => ("seconds_ago" in item ? item.seconds_ago : item.minutes_ago * 60);
  const good = items.filter(({ entry }) => {
    if (entry === null || (entry.type ?? "sgv") !== "sgv") {
      return false;
    }
    return Number.isInteger(entry.sgv) && entry.sgv >= 39 && entry.sgv <= 401;
  });
  good.sort((a, b) => ageSeconds(a) - ageSeconds(b) || a.entry.sgv - b.entry.sgv);
  return good.length ? good[0].entry : null;
}

test("HAZ-013: the Home Assistant tile number for every vector", () => {
  let numbers = 0;
  for (const c of DISPLAY) {
    const entry = survivor(c);
    const untrusted = c.level === "STALE" || c.level === "NO DATA";
    const sentinel = entry !== null && (entry.sgv <= 39 || entry.sgv >= 401);
    const expected = untrusted || entry === null || sentinel ? null : entry.sgv;
    assert.equal(P.haGlucose(c.level, c.lines), expected, c.name);
    numbers += expected === null ? 0 : 1;
  }
  assert.ok(numbers > 0 && numbers < DISPLAY.length);
  for (const name of ["stale_beats_urgent_low", "no_data", "sensor_low_sentinel", "sensor_high_sentinel"]) {
    assert.equal(P.haGlucose(STATES[name].level, STATES[name].lines), null, name);
  }
});

test("HAZ-013: the tile rule is cautious with anything it cannot place", () => {
  const fresh = ["IN RANGE", "112 mg/dL ->", "3 min ago"];
  assert.equal(P.haGlucose("IN RANGE", fresh), 112);
  assert.equal(P.haGlucose("STALE", fresh), null);
  assert.equal(P.haGlucose("MYSTERY", fresh), null);
  assert.equal(P.haGlucose("IN RANGE", ["MYSTERY", "112 mg/dL ->"]), null);
  assert.equal(P.haGlucose("IN RANGE", ["STALE - DO NOT TRUST", "112 mg/dL ->"]), null);
  assert.equal(P.haGlucose("IN RANGE", ["IN RANGE"]), null);
  assert.equal(P.haGlucose("IN RANGE", ["IN RANGE", "1120 mg/dL ->"]), null);
  assert.equal(P.haGlucose("IN RANGE", ["IN RANGE", "39 mg/dL ->"]), null);
  assert.equal(P.haGlucose("IN RANGE", ["IN RANGE", "last: 112 mg/dL ->"]), null);
  assert.equal(P.haGlucose("IN RANGE", "IN RANGE"), null);
});

test("glance: the phone card is the vector lines, and STALE has no hero", () => {
  for (const c of DISPLAY) {
    const g = P.glance(c.lines);
    const hero = g.hero === null ? [] : [g.hero.word ?? `${g.hero.digits} ${g.hero.unit} ${g.hero.arrow}`];
    const parts = [g.status, ...hero, ...(g.struck === null ? [] : [g.struck])];
    const rebuilt = [...parts, ...(g.age === null ? [] : [g.age]), ...g.context];
    assert.deepEqual(rebuilt, c.lines, c.name);
    assert.equal(g.treatment, P.treatment(c.lines[0]), c.name);
    if (c.level === "STALE" || c.level === "NO DATA") {
      assert.equal(g.hero, null, `${c.name}: an old or missing value is never the hero`);
    }
    if (c.level === "STALE") {
      assert.equal(g.struck, c.lines[1], c.name);
      assert.ok(g.struck.startsWith("last: "), c.name);
    }
    const number = P.haGlucose(c.level, c.lines);
    if (number !== null) {
      assert.equal(g.hero.digits, String(number), c.name);
    }
  }
  assert.deepEqual(P.glance(["MYSTERY", "112 mg/dL ->", "3 min ago"]).hero, null);
  assert.deepEqual(P.glance(["URGENT LOW", "LOW (<40)", "just now"]).hero, { word: "LOW (<40)" });
  assert.deepEqual(P.glance(["IN RANGE"]), {
    treatment: "plain",
    status: "IN RANGE",
    hero: null,
    struck: null,
    age: null,
    context: [],
  });
  assert.equal(P.glance(["STALE - DO NOT TRUST"]).struck, null);
});

test("the port defines one global and nothing else", () => {
  assert.ok(Object.isFrozen(P));
  assert.ok(!/^\s*(import|export)\b/m.test(SOURCE));
  for (const banned of ["</script", "<!--", "fetch(", "XMLHttpRequest", "localStorage", "eval("]) {
    assert.ok(!SOURCE.toLowerCase().includes(banned.toLowerCase()), banned);
  }
});
