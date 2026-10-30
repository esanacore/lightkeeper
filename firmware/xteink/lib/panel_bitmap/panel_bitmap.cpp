#include "panel_bitmap.h"

#include <string.h>

#include "font5x8_data.h"

namespace lk {

namespace {

static_assert(kGlyphWidth == 5 && kGlyphHeight == 8, "the layout is drawn in Keeper 5x8 cells");

// Glyph rows above the baseline; the last row is for descenders.
constexpr int kCapRows = kGlyphHeight - 1;
constexpr int kStampChars = 5;  // every stamp is "HH:MM", so every stamp is as wide as "00:00"
constexpr int kMaxBodyLines = kMaxPanelLines - 1;

struct TreatmentEntry {
  const char* headline;
  Treatment kind;
};

// Keyed by the exact headline text (panel_layout.TREATMENTS); anything else is dashed.
const TreatmentEntry kTreatments[] = {
    {"IN RANGE", Treatment::Plain},      {"LOW", Treatment::Rule},
    {"HIGH", Treatment::Rule},           {"URGENT LOW", Treatment::Inverse},
    {"URGENT HIGH", Treatment::Inverse}, {"STALE - DO NOT TRUST", Treatment::Stale},
    {"NO DATA", Treatment::Dashed},
};

// Line roles, in glance order: status, value, age, context, then the stamp.
enum class Role { Headline, Value, Last, Age, Context, Stamp };

struct Box {
  int x = 0;
  int y = 0;
  int w = 0;
  int h = 0;
};

// One line of text where it is drawn. `scale` is the width of a glyph cell
// in pixels and `tall` its height; they differ only for a headline narrowed
// to fit the band.
struct PlacedText {
  const char* text = nullptr;
  int length = 0;
  Role role = Role::Context;
  int x = 0;
  int y = 0;
  int scale = 1;
  int tall = 1;
  int width = 0;
};

// A texture ring in the margin: `box` is its outer edge.
struct Frame {
  Treatment kind = Treatment::Dashed;  // Stale draws a hatch, Dashed a dashed line
  Box box;
  int thickness = 0;
};

// panel_layout.PanelPlan: everything the drawer needs, in whole pixels.
struct PanelPlan {
  int width = 0;
  int height = 0;
  Treatment kind = Treatment::Dashed;
  PlacedText headline;
  PlacedText lines[kMaxBodyLines];
  int line_count = 0;
  bool has_stamp = false;
  PlacedText stamp;
  bool has_ink_band = false;  // filled with ink, the headline drawn in paper on it
  Box ink_band;
  bool has_rule = false;
  Box rule;
  bool has_strike = false;
  Box strike;
  bool has_frame = false;
  Frame frame;
};

// Scales of the lines under the band while they are fitted to the height.
struct Sizes {
  int value;
  int age;
  int small;  // the `last:` line and the context lines

  int of(Role role) const {
    if (role == Role::Value) return value;
    if (role == Role::Age) return age;
    return small;
  }
};

int max_of(int a, int b) { return a > b ? a : b; }
int min_of(int a, int b) { return a < b ? a : b; }

// The length of `text` when it is at most `limit` ASCII bytes, else -1. It
// never reads past the limit, so a missing terminator cannot run away.
int bounded_length(const char* text, int limit) {
  for (int i = 0; i <= limit; i++) {
    unsigned char byte = static_cast<unsigned char>(text[i]);
    if (byte == 0) return i;
    if (byte > 0x7F) return -1;
  }
  return -1;
}

// Space between characters: at least one pixel, wider at large sizes.
int glyph_gap(int scale) { return max_of(1, scale / 2); }

// Width in pixels of `length` characters drawn at `scale`.
int text_width(int length, int scale) {
  if (length == 0) return 0;
  return length * kGlyphWidth * scale + (length - 1) * glyph_gap(scale);
}

// Largest whole-number scale (up to `max_scale`) at which every line fits;
// with no lines, `max_scale` itself (from 2 up), as Python's all([]) is true.
int fit_scale(const int* lengths, int count, int usable_width, int max_scale) {
  for (int scale = max_scale; scale > 1; scale--) {
    bool fits = true;
    for (int i = 0; i < count; i++) fits = fits && text_width(lengths[i], scale) <= usable_width;
    if (fits) return scale;
  }
  return 1;
}

// Clear space on every side: 6% of the height, rounded half up, at least 4 px.
int margin(int height) { return max_of(4, (height * 6 + 50) / 100); }

// The largest headline scale for a panel this tall.
int headline_cap(int height) { return max_of(4, height / 32); }

// The largest age and context scale: about half the headline, at least 3.
int body_cap(int band_scale) { return min_of(band_scale, max_of(3, band_scale / 2)); }

// The stamp's scale: 2, or more on tall panels, never wider than the content box.
int stamp_scale(int width, int height) {
  const int stamp_length = kStampChars;
  return fit_scale(&stamp_length, 1, width - 2 * margin(height),
                   max_of(kStampMinScale, height / 240));
}

// Height a four-line screen needs under the band at scale 1, gaps and stamp strip included.
int body_reserve(int strip) {
  return kReservedBodyLines * kGlyphHeight + (kReservedBodyLines + 1) * kMinGap + strip;
}

// The narrowest content box: the widest line or padded headline at scale 1.
int min_content_width() {
  int headline = 0;
  for (const TreatmentEntry& entry : kTreatments) {
    headline = max_of(headline, static_cast<int>(strlen(entry.headline)));
  }
  const int widest = static_cast<int>(sizeof(kWidestLine)) - 1;
  return max_of(text_width(widest, 1), 2 * kBandPad + text_width(headline, 1));
}

// The shortest content box: the band and a stamped four-line screen, all at scale 1.
int min_content_height(int width, int height) {
  const int strip = kGlyphHeight * stamp_scale(width, height) + kMinGap;
  return 2 * kBandPad + kGlyphHeight + body_reserve(strip);
}

bool is_fresh(Treatment kind) {
  return kind == Treatment::Plain || kind == Treatment::Rule || kind == Treatment::Inverse;
}

// The role of each of the `count` lines under the headline.
void roles_for(Treatment kind, int count, Role* roles) {
  for (int i = 0; i < count; i++) {
    Role role = Role::Context;
    if (is_fresh(kind) && i < 2) role = i == 0 ? Role::Value : Role::Age;
    if (kind == Treatment::Stale && i < 2) role = i == 0 ? Role::Last : Role::Age;
    roles[i] = role;
  }
}

// Place a line of text at `scale`, its top-left corner at (x, y).
PlacedText place(const char* text, int length, Role role, int x, int y, int scale) {
  PlacedText line;
  line.text = text;
  line.length = length;
  line.role = role;
  line.x = x;
  line.y = y;
  line.scale = scale;
  line.tall = scale;
  line.width = text_width(length, scale);
  return line;
}

// Place the stamp with its right edge at `right`.
PlacedText place_right(const char* text, int right, int y, int scale) {
  return place(text, kStampChars, Role::Stamp, right - text_width(kStampChars, scale), y, scale);
}

// A rule through the middle of the line's capitals, across its full width:
// 1 px thick at scale 2 or less, 2 px from scale 3.
Box strike_box(const PlacedText& line) {
  const int thickness = line.scale <= 2 ? 1 : 2;
  const int middle = line.y + (kCapRows * line.scale) / 2 - thickness / 2;
  return Box{line.x, middle, line.width, thickness};
}

// panel_layout.plan_panel, for arguments render_panel has already checked:
// check_size accepts the size, 1 <= count <= kMaxPanelLines, `lengths` holds
// each line's length, and `stamp` is nullptr or passes check_stamp.
void plan_panel(const char* const* lines, const int* lengths, int count, int width, int height,
                const char* stamp, PanelPlan* plan) {
  const int edge = margin(height);
  const Box content{edge, edge, width - 2 * edge, height - 2 * edge};
  const Treatment kind = treatment(lines[0]);
  // The stamp's ceiling. The band reserves a strip this tall, as check_size
  // does, but the stamp is drawn no larger than the lines it sits under.
  const int stamp_max = stamp_scale(width, height);
  const bool stamped = stamp != nullptr;
  const int strip = stamped ? kGlyphHeight * stamp_max + kMinGap : 0;

  // The band: one height per panel, sized from IN RANGE. It leaves room for
  // a four-line screen at scale 1 (and the stamp), so even the smallest
  // panel check_size accepts never overlaps its lines.
  const int inner = content.w - 2 * kBandPad;
  const int reserve = body_reserve(strip);
  const int tallest = max_of(0, content.h - 2 * kBandPad - reserve) / kGlyphHeight;
  const int reference = static_cast<int>(sizeof(kReferenceHeadline)) - 1;
  const int band_scale =
      fit_scale(&reference, 1, inner, max_of(1, min_of(headline_cap(height), tallest)));
  const Box band{content.x, content.y, content.w, 2 * kBandPad + kGlyphHeight * band_scale};
  const int head_scale = fit_scale(&lengths[0], 1, inner, band_scale);
  plan->width = width;
  plan->height = height;
  plan->kind = kind;
  plan->headline =
      place(lines[0], lengths[0], Role::Headline, band.x + kBandPad, band.y + kBandPad, head_scale);
  plan->headline.tall = band_scale;

  const int body = count - 1;
  Role roles[kMaxBodyLines];
  roles_for(kind, body, roles);
  int value_lines[kMaxBodyLines];
  int age_lines[kMaxBodyLines];
  int small_lines[kMaxBodyLines];  // the `last:` line, then the context lines
  int values = 0;
  int ages = 0;
  int smalls = 0;
  for (int i = 0; i < body; i++) {
    if (roles[i] == Role::Value) value_lines[values++] = lengths[i + 1];
    if (roles[i] == Role::Age) age_lines[ages++] = lengths[i + 1];
    if (roles[i] == Role::Last || roles[i] == Role::Context) small_lines[smalls++] = lengths[i + 1];
  }

  // Widest that fits: the hero up to the headline, the age up to the hero,
  // the rest up to the age (and, on STALE, up to the headline as well).
  const int cap = body_cap(band_scale);
  const int value = fit_scale(value_lines, values, content.w, head_scale);
  const int age = fit_scale(age_lines, ages, content.w, values > 0 ? min_of(cap, value) : cap);
  int small_cap = ages > 0 ? min_of(cap, age) : cap;
  if (kind == Treatment::Stale) small_cap = min_of(small_cap, head_scale);
  Sizes sizes{value, age, fit_scale(small_lines, smalls, content.w, small_cap)};

  // The stamp is chrome, so it never outranks what it sits under: no larger
  // than the age (or, with no age line, the hero), the headline band or its
  // ceiling, and never below kStampMinScale. It sits at the right of the age
  // row when it fits there beside the age and a one-character gap; otherwise
  // it gets the bottom strip. All three follow the current sizes, so the
  // stamp shrinks with the lines and never forces the age below what it
  // would be unstamped.
  auto stamp_size = [&]() {
    const int anchor = ages > 0 ? sizes.age : values > 0 ? sizes.value : stamp_max;
    return max_of(kStampMinScale, min_of(min_of(stamp_max, band_scale), anchor));
  };
  auto on_age_row = [&]() {
    return stamped && ages > 0 &&
           text_width(age_lines[0], sizes.age) + kGlyphWidth * sizes.age +
                   text_width(kStampChars, stamp_size()) <=
               content.w;
  };
  const int top = band.y + band.h;
  auto bottom = [&]() {
    const bool in_strip = stamped && !on_age_row();
    return content.y + content.h - (in_strip ? kGlyphHeight * stamp_size() + kMinGap : 0);
  };

  // Each line's row height in glyph cells: the age row is as tall as its stamp.
  int rows[kMaxBodyLines];
  auto row_total = [&]() {
    const bool shared = on_age_row();
    int sum = 0;
    for (int i = 0; i < body; i++) {
      int row = sizes.of(roles[i]);
      if (roles[i] == Role::Age && shared) row = max_of(row, stamp_size());
      rows[i] = row;
      sum += row;
    }
    return sum;
  };

  // Shrink in glance order until the lines and their gaps fit the height:
  // context to a readable 2, the hero down to the age, then context to 1,
  // then the age. check_size leaves room for any four-line screen at scale
  // 1, so only more lines than a screen has can reach the end.
  const int gaps = body + 1;
  while (kGlyphHeight * row_total() + gaps * kMinGap > bottom() - top) {
    if (smalls > 0 && sizes.small > kReadableScale) {
      sizes.small--;
    } else if (values > 0 && sizes.value > (ages > 0 ? sizes.age : 1)) {
      sizes.value--;
    } else if (smalls > 0 && sizes.small > 1) {
      sizes.small--;
    } else if (ages > 0 && sizes.age > 1) {
      sizes.age--;
    } else {
      break;  // still too tall: the lines past the content box are clipped
    }
  }

  const int total = row_total();
  const int final_stamp = stamp_size();
  const bool final_on_age_row = on_age_row();
  const int gap = max_of(0, bottom() - top - kGlyphHeight * total) / gaps;
  int y = top + gap;
  for (int i = 0; i < body; i++) {
    const int scale = sizes.of(roles[i]);
    // Text sharing a row shares its baseline.
    plan->lines[i] = place(lines[i + 1], lengths[i + 1], roles[i], content.x,
                           y + kCapRows * (rows[i] - scale), scale);
    if (roles[i] == Role::Age && final_on_age_row) {
      const int stamp_y = y + kCapRows * (rows[i] - final_stamp);
      plan->stamp = place_right(stamp, content.x + content.w, stamp_y, final_stamp);
      plan->has_stamp = true;
    }
    y += kGlyphHeight * rows[i] + gap;
  }
  plan->line_count = body;
  if (stamped && !final_on_age_row) {
    const int stamp_y = content.y + content.h - kGlyphHeight * final_stamp;
    plan->stamp = place_right(stamp, content.x + content.w, stamp_y, final_stamp);
    plan->has_stamp = true;
  }

  plan->has_ink_band = kind == Treatment::Inverse || kind == Treatment::Stale;
  plan->ink_band = band;
  plan->has_rule = kind == Treatment::Rule;
  plan->rule = Box{content.x, band.y + band.h - kRuleThickness, content.w, kRuleThickness};
  // Under a STALE headline the first line is always the `last:` line.
  plan->has_strike = kind == Treatment::Stale && body > 0;
  if (plan->has_strike) plan->strike = strike_box(plan->lines[0]);
  // The texture ring for STALE or DASHED, centred in the margin (at least 4,
  // so the inset is never negative).
  plan->has_frame = kind == Treatment::Stale || kind == Treatment::Dashed;
  plan->frame.kind = kind;
  plan->frame.thickness = kind == Treatment::Stale ? kHatchWidth : kDashWidth;
  const int inset = (edge - plan->frame.thickness) / 2;
  plan->frame.box = Box{inset, inset, width - 2 * inset, height - 2 * inset};
}

// The packed rows being drawn: 1 = ink, most significant bit first.
struct Canvas {
  uint8_t* rows;
  int width;
  int height;
  int stride;
};

// Ink a rectangle (or clear it to paper), clipped to the panel.
void fill(const Canvas& canvas, int x, int y, int w, int h, bool ink) {
  const int left = max_of(0, x);
  const int right = min_of(canvas.width, x + w);
  if (left >= right) return;
  for (int row = max_of(0, y); row < min_of(canvas.height, y + h); row++) {
    uint8_t* bytes = canvas.rows + row * canvas.stride;
    for (int col = left; col < right; col++) {
      const uint8_t bit = static_cast<uint8_t>(0x80u >> (col % 8));
      if (ink) {
        bytes[col / 8] = static_cast<uint8_t>(bytes[col / 8] | bit);
      } else {
        bytes[col / 8] = static_cast<uint8_t>(bytes[col / 8] & ~bit);
      }
    }
  }
}

void fill_box(const Canvas& canvas, const Box& box) {
  fill(canvas, box.x, box.y, box.w, box.h, true);
}

// The rows of a character's glyph; any byte outside the table draws as the fallback.
const uint8_t* glyph(char c) {
  int code = static_cast<unsigned char>(c);
  if (code < kFirstGlyph || code > kLastGlyph) code = kFallbackGlyph;
  return kFont5x8[code - kFirstGlyph];
}

// epaper_bitmap.draw_text: the line's glyph cells, `tall` pixels high when
// larger than `scale`, so a narrowed headline keeps the band's height.
void draw_line(const Canvas& canvas, const PlacedText& line, bool ink) {
  const int sy = max_of(line.scale, line.tall);
  int x = line.x;
  for (int i = 0; i < line.length; i++) {
    const uint8_t* rows = glyph(line.text[i]);
    for (int row = 0; row < kGlyphHeight; row++) {
      for (int col = 0; col < kGlyphWidth; col++) {
        if ((rows[row] >> (kGlyphWidth - 1 - col)) & 1) {
          fill(canvas, x + col * line.scale, line.y + row * sy, line.scale, sy, ink);
        }
      }
    }
    x += kGlyphWidth * line.scale + glyph_gap(line.scale);
  }
}

// One pixel of the frame ring. `across` is true in the ring's top and bottom
// strips, where dashes count along x; on the sides they count along y.
void frame_pixel(const Canvas& canvas, const Frame& frame, int x, int y, bool across) {
  bool on = (x + y) % kHatchPitch == 0;
  if (frame.kind == Treatment::Dashed) {
    const int along = across ? x - frame.box.x : y - frame.box.y;
    on = along % (kDashOn + kDashOff) < kDashOn;
  }
  if (on) fill(canvas, x, y, 1, 1, true);
}

// A ring `thickness` wide just inside `box`: hatched for STALE, else dashed.
// The hatch inks every pixel where x + y is a multiple of kHatchPitch (45
// degree lines). Dashes run kDashOn pixels on and kDashOff off, counted from
// the ring's top-left corner along each side.
void draw_frame(const Canvas& canvas, const Frame& frame) {
  const Box& box = frame.box;
  const int t = frame.thickness;
  for (int y = box.y; y < box.y + box.h; y++) {
    if (y < box.y + t || y >= box.y + box.h - t) {
      for (int x = box.x; x < box.x + box.w; x++) frame_pixel(canvas, frame, x, y, true);
    } else {
      for (int x = box.x; x < box.x + t; x++) frame_pixel(canvas, frame, x, y, false);
      for (int x = box.x + box.w - t; x < box.x + box.w; x++)
        frame_pixel(canvas, frame, x, y, false);
    }
  }
}

// epaper_bitmap.draw_plan: band, headline, rule, strike, lines, stamp, then
// the frame. Only the headline on an ink band clears pixels (its glyphs are
// paper); everything after it only adds ink, so the order is fixed.
void draw_plan(const PanelPlan& plan, const Canvas& canvas) {
  if (plan.has_ink_band) fill_box(canvas, plan.ink_band);
  draw_line(canvas, plan.headline, !plan.has_ink_band);
  if (plan.has_rule) fill_box(canvas, plan.rule);
  if (plan.has_strike) fill_box(canvas, plan.strike);
  for (int i = 0; i < plan.line_count; i++) draw_line(canvas, plan.lines[i], true);
  if (plan.has_stamp) draw_line(canvas, plan.stamp, true);
  if (plan.has_frame) draw_frame(canvas, plan.frame);
}

}  // namespace

Treatment treatment(const char* headline) {
  if (headline == nullptr) return Treatment::Dashed;
  for (const TreatmentEntry& entry : kTreatments) {
    if (strcmp(entry.headline, headline) == 0) return entry.kind;
  }
  return Treatment::Dashed;  // unknown: the most cautious shape
}

const char* treatment_name(Treatment kind) {
  switch (kind) {
    case Treatment::Plain:
      return "plain";
    case Treatment::Rule:
      return "rule";
    case Treatment::Inverse:
      return "inverse";
    case Treatment::Stale:
      return "stale";
    case Treatment::Dashed:
      return "dashed";
  }
  return "dashed";
}

bool check_size(int width, int height) {
  // The bounds come first, so no division below ever sees a negative number.
  if (!(1 <= width && width <= kMaxSide && 1 <= height && height <= kMaxSide)) return false;
  const int edge = margin(height);
  if (width - 2 * edge < min_content_width()) return false;
  return height - 2 * edge >= min_content_height(width, height);
}

bool check_stamp(const char* stamp) {
  if (stamp == nullptr) return false;
  for (int i = 0; i < kStampChars; i++) {
    if (stamp[i] == '\0') return false;
  }
  if (stamp[kStampChars] != '\0') return false;
  auto digit = [](char c, char most) { return c >= '0' && c <= most; };
  const bool hours =
      (digit(stamp[0], '1') && digit(stamp[1], '9')) || (stamp[0] == '2' && digit(stamp[1], '3'));
  return hours && stamp[2] == ':' && digit(stamp[3], '5') && digit(stamp[4], '9');
}

bool render_panel(const char* const* lines, int count, int width, int height, const char* stamp,
                  uint8_t* buffer, size_t buffer_size) {
  if (lines == nullptr || count < 1 || count > kMaxPanelLines) return false;
  int lengths[kMaxPanelLines];
  for (int i = 0; i < count; i++) {
    if (lines[i] == nullptr) return false;
    lengths[i] = bounded_length(lines[i], kMaxPanelLineChars);
    if (lengths[i] < 0) return false;
  }
  if (!check_size(width, height)) return false;
  if (stamp != nullptr && !check_stamp(stamp)) return false;
  const size_t size = packed_size(width, height);
  if (buffer == nullptr || buffer_size < size) return false;

  PanelPlan plan;
  plan_panel(lines, lengths, count, width, height, stamp, &plan);
  memset(buffer, 0, size);
  draw_plan(plan, Canvas{buffer, width, height, (width + 7) / 8});
  return true;
}

bool to_epd_portrait(const uint8_t* rows, size_t rows_size, int width, int height, uint8_t* out,
                     size_t out_size) {
  if (width < 1 || width > kMaxSide || height < 1 || height > kMaxSide) return false;
  if (rows == nullptr || rows_size < packed_size(width, height)) return false;
  if (out == nullptr || out_size < packed_size(height, width)) return false;

  // The portrait image is `height` pixels wide and `width` tall: landscape
  // pixel (x, y) lands at (y, width - 1 - x). A 1 bit there is paper.
  const int stride = (width + 7) / 8;
  const int out_stride = (height + 7) / 8;
  memset(out, 0, packed_size(height, width));
  for (int py = 0; py < width; py++) {
    const int x = width - 1 - py;
    uint8_t* line = out + py * out_stride;
    for (int px = 0; px < height; px++) {
      const bool ink = (rows[px * stride + x / 8] >> (7 - x % 8)) & 1;
      if (!ink) line[px / 8] = static_cast<uint8_t>(line[px / 8] | (0x80u >> (px % 8)));
    }
  }
  return true;
}

uint32_t crc32(const uint8_t* data, size_t length) {
  if (data == nullptr) length = 0;
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return crc ^ 0xFFFFFFFFu;
}

uint32_t ink_count(const uint8_t* data, size_t length) {
  if (data == nullptr) return 0;
  uint32_t count = 0;
  for (size_t i = 0; i < length; i++) {
    for (unsigned byte = data[i]; byte != 0; byte &= byte - 1) count++;
  }
  return count;
}

}  // namespace lk
