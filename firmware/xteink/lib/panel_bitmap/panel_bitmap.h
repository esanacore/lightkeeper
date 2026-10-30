// panel_bitmap: draw the display lines as the 1-bit e-paper panel image, the
// same pixels the Python reference rasterizer draws.
//
// A port of src/lightkeeper/infrastructure/panel_layout.py and epaper_bitmap.py,
// with the same names, steps and order (ADR-0007). The layout is whole-number
// arithmetic only, and every division divides a number that is not negative,
// so C++'s `/` gives exactly Python's `//` and nothing is ever rounded: no
// half-away-from-zero or fused multiply-add drift between the ports
// (proposed HAZ-016). spec/panel_vectors.json pins every display vector at
// every panel profile by the CRC-32 of its packed rows, and the host tests
// (test/host/test_panel_bitmap.cpp) check every case.
//
// No heap, no Arduino, integers only. The caller owns the buffer, and every
// argument is checked before the first byte is written: a refusal returns
// false and leaves the buffer exactly as it was.
//
// The status shape comes from the headline (lines[0]) alone, so the rules in
// glucose_rules (STALE before any range check) are never redone here:
// IN RANGE plain; LOW and HIGH a rule under the headline; URGENT LOW and
// URGENT HIGH an ink band; STALE the ink band, a hatched frame and a strike
// through the `last:` line; NO DATA and any headline not in the table a
// dashed frame, the most cautious shape.
//
// Known differences from Python, all refusals (Python would draw), never a
// different image:
// - more than kMaxPanelLines lines, or a line longer than kMaxPanelLineChars
//   (the display shows at most four lines of at most 25 characters);
// - a byte outside ASCII (Python counts a UTF-8 character as one glyph, this
//   port would count its bytes; glucose_rules only writes ASCII).

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace lk {

// Layout constants, named as in panel_layout.py; spec/panel_vectors.json lists
// them under layout.constants and the host tests compare the two. The band
// pad is the space around the headline glyphs inside the band; the hatch
// inks one diagonal every kHatchPitch pixels; kMinGap is the least space
// above, between and below the lines under the band; context shrinks to
// kReadableScale before the hero shrinks at all; a four-line screen has
// kReservedBodyLines under the band. The band is sized from
// kReferenceHeadline, and every accepted panel holds kWidestLine at scale 1.
constexpr int kBandPad = 2;
constexpr int kRuleThickness = 2;
constexpr int kHatchWidth = 4;
constexpr int kHatchPitch = 4;
constexpr int kDashWidth = 2;
constexpr int kDashOn = 4;
constexpr int kDashOff = 4;
constexpr int kMinGap = 2;
constexpr int kReadableScale = 2;
constexpr int kReservedBodyLines = 3;
constexpr int kStampMinScale = 2;
constexpr int kMaxSide = 4096;  // larger is only a typo
inline constexpr char kReferenceHeadline[] = "IN RANGE";
inline constexpr char kWidestLine[] = "Confirm on primary device";

// What render_panel accepts beyond Python's rules (see the differences above).
constexpr int kMaxPanelLines = 8;
constexpr int kMaxPanelLineChars = 64;

// The six panel sizes spec/panel_vectors.json pins, as panel_profiles.py names
// them: width and height in the orientation the lines read.
struct PanelProfile {
  const char* name;
  int width;
  int height;
};

inline constexpr PanelProfile kPanelProfiles[] = {
    {"waveshare_2in9", 296, 128}, {"waveshare_1in54", 200, 200}, {"waveshare_2in13", 250, 122},
    {"waveshare_4in2", 400, 300}, {"waveshare_7in5", 800, 480},  {"kindle", 600, 800},
};
constexpr int kPanelProfileCount =
    static_cast<int>(sizeof(kPanelProfiles) / sizeof(kPanelProfiles[0]));

// Bytes of packed rows for a width x height image: ceil(width / 8) per row.
constexpr size_t packed_size(int width, int height) {
  return width < 1 || height < 1
             ? 0
             : static_cast<size_t>((width + 7) / 8) * static_cast<size_t>(height);
}

// The largest packed image among the profiles (the kindle, 75 x 800 = 60,000
// bytes; 800x480 needs 48,000): a buffer this big holds any pinned profile.
constexpr size_t max_profile_bytes() {
  size_t most = 0;
  for (const PanelProfile& p : kPanelProfiles) {
    size_t size = packed_size(p.width, p.height);
    most = size > most ? size : most;
  }
  return most;
}
constexpr size_t kMaxPanelBytes = max_profile_bytes();

// True when width x height is one of the pinned profiles, so its pixels are
// checked against Python case by case. The device asserts this at compile time.
constexpr bool is_profile_size(int width, int height) {
  for (const PanelProfile& p : kPanelProfiles) {
    if (p.width == width && p.height == height) return true;
  }
  return false;
}

enum class Treatment { Plain, Rule, Inverse, Stale, Dashed };

// The shape for a headline. nullptr, or any headline not in the table, gets
// the dashed frame.
Treatment treatment(const char* headline);
// "plain", "rule", "inverse", "stale" or "dashed", as spec/panel_vectors.json spells them.
const char* treatment_name(Treatment kind);

// panel_layout.check_size: true when every screen fits a width x height panel,
// the widest line at scale 1 inside the margins and a stamped four-line screen
// under the band. Any other size is refused, never clipped.
bool check_size(int width, int height);

// panel_layout.check_stamp: true for a 24-hour "HH:MM" and nothing else.
bool check_stamp(const char* stamp);

// Draw `count` lines (lines[0] is the headline) on a width x height panel
// into `buffer` as packed rows: top row first, ceil(width / 8) bytes a row,
// 1 = ink, the leftmost pixel in the most significant bit, padding bits 0.
// This is the layout spec/panel_vectors.json hashes; packed_size() gives the
// byte count. `stamp` is nullptr or an "HH:MM" drawn at the right of the age
// row (or in a strip at the bottom): the time the image was drawn, not the
// time of the reading (proposed HAZ-014). It is chrome: never below
// kStampMinScale, and above that no larger than the age line (the hero with
// no age line), the band, or the panel's stamp ceiling.
//
// Returns false, writing nothing, for a refused size, no lines, too many or
// too long lines, a bad stamp, or a buffer smaller than packed_size(). Bytes
// past packed_size() are never touched. A device that gets false must blank
// its panel rather than leave the last image up: e-ink keeps it.
bool render_panel(const char* const* lines, int count, int width, int height, const char* stamp,
                  uint8_t* buffer, size_t buffer_size);

// Bitmap.to_epd_buffer: rotate the packed landscape rows render_panel wrote a
// quarter turn counterclockwise into the panel's native portrait order, and
// pack them as Waveshare's getbuffer does: `height` pixels a row, `width`
// rows, 1 = white (paper), most significant bit first, padding bits 0.
// Needs packed_size(height, width) bytes of `out`; `rows` and `out` must not
// overlap. Returns false, writing nothing, for a bad size or short buffers.
// Not yet checked on a physical panel (GAP-001).
bool to_epd_portrait(const uint8_t* rows, size_t rows_size, int width, int height, uint8_t* out,
                     size_t out_size);

// CRC-32 as zlib.crc32 computes it (CRC-32/ISO-HDLC), which the pixel vectors
// pin: crc32("123456789") is 0xCBF43926. nullptr hashes as no bytes.
uint32_t crc32(const uint8_t* data, size_t length);

// The number of 1 bits, which for packed rows is the number of ink pixels.
uint32_t ink_count(const uint8_t* data, size_t length);

}  // namespace lk
