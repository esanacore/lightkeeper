// Host tests for panel_bitmap: the C++ port of the Python panel rasterizer.
// Built with AddressSanitizer and UBSan by `make test`.
//
// Three layers:
//   1. Every case in spec/panel_vectors.json (each display vector at each
//      panel profile, plus the stamped cases): the CRC-32 of the packed rows
//      and the ink count must equal Python's. A mismatch writes the image to
//      build/<vector>_<W>x<H>.pbm (P4, viewable and diffable) for comparing
//      with the Python render.
//   2. Inputs the spec does not pin, drawn or judged by the Python reference
//      when tools/gen_panel_vectors.py writes the include: stamps at every
//      profile, unknown headlines, eight lines, edge, odd and maximum sizes,
//      bytes outside the font, the size and stamp checks, the portrait buffer.
//   3. Firmware-only guarantees: a refusal leaves the buffer untouched,
//      nothing is written past the image, no heap allocation, the CRC check
//      value, and the device skeleton (src/device_config.h): its NO DATA
//      screen at each board's size, and pins left unset until verified.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <new>

#include "../../src/device_config.h"
#include "glucose_rules.h"
#include "nightscout_json.h"
#include "panel_bitmap.h"

// Every allocation through operator new is counted, so a test can prove the
// rasterizer makes none (it has no other way to reach the heap: `make test`
// also greps lib/panel_bitmap for the allocation functions).
static long g_allocations = 0;

void* operator new(size_t size) {
  g_allocations++;
  void* p = malloc(size == 0 ? 1 : size);
  if (p == nullptr) throw std::bad_alloc();
  return p;
}
void* operator new[](size_t size) {
  g_allocations++;
  void* p = malloc(size == 0 ? 1 : size);
  if (p == nullptr) throw std::bad_alloc();
  return p;
}
void operator delete(void* p) noexcept { free(p); }
void operator delete[](void* p) noexcept { free(p); }
void operator delete(void* p, size_t) noexcept { free(p); }
void operator delete[](void* p, size_t) noexcept { free(p); }

namespace {

int g_failures = 0;
int g_checks = 0;
const char* g_dump_dir = "build";

#define CHECK(cond, msg)                                              \
  do {                                                                \
    g_checks++;                                                       \
    if (!(cond)) {                                                    \
      g_failures++;                                                   \
      printf("FAIL %s:%d %s (%s)\n", __FILE__, __LINE__, msg, #cond); \
    }                                                                 \
  } while (0)

// The tables and their row types (PanelCase, EpdCase, SizeCheck, ...), written
// by tools/gen_panel_vectors.py so each row's fields are declared where they
// are filled in.
#include "panel_vectors.inc"

// Bump when an existing case's pixels change (the Python suite asserts the same).
const int kExpectedPanelSpecVersion = 1;

constexpr size_t kGuard = 64;  // bytes after the image that must stay untouched
constexpr size_t kImageBytes =
    lk::kMaxPanelBytes > kLargestExtraBytes ? lk::kMaxPanelBytes : kLargestExtraBytes;
uint8_t g_image[kImageBytes + kGuard];
uint8_t g_portrait[kImageBytes + kGuard];

int count_of(const PanelCase* cases, size_t bytes) {
  return static_cast<int>(bytes / sizeof(cases[0]));
}

bool all_bytes_are(const uint8_t* data, size_t length, uint8_t value) {
  for (size_t i = 0; i < length; i++) {
    if (data[i] != value) return false;
  }
  return true;
}

bool render(const PanelCase& c, uint8_t* out, size_t size) {
  return lk::render_panel(c.lines, c.line_count, c.width, c.height, c.stamp, out, size);
}

// Writes the image as a binary PBM (P4), whose rows are exactly the packed
// rows render_panel writes: 1 = black, most significant bit first.
bool write_pbm(const char* path, const uint8_t* rows, int width, int height) {
  FILE* f = fopen(path, "wb");
  if (f == nullptr) return false;
  const size_t size = lk::packed_size(width, height);
  bool ok = fprintf(f, "P4\n%d %d\n", width, height) > 0;
  ok = fwrite(rows, 1, size, f) == size && ok;
  return fclose(f) == 0 && ok;
}

// Draws one case and checks it against Python's CRC-32 and ink count, and
// that nothing past the image was touched. On a mismatch the image is written
// to <dump dir>/<vector>_<W>x<H>[_stamp].pbm.
void check_case(const PanelCase& c, const char* table) {
  const size_t size = lk::packed_size(c.width, c.height);
  char msg[192];
  snprintf(msg, sizeof(msg), "%s %s at %dx%d%s fits the test buffer", table, c.vector, c.width,
           c.height, c.stamp ? " stamped" : "");
  CHECK(size <= kImageBytes, msg);
  if (size > kImageBytes) return;
  memset(g_image, 0xA5, size + kGuard);
  const bool ok = render(c, g_image, size);
  const uint32_t crc = lk::crc32(g_image, size);
  const uint32_t ink = lk::ink_count(g_image, size);
  snprintf(msg, sizeof(msg), "%s %s at %dx%d%s: drawn %d, crc32 %lu (want %lu), ink %lu (want %lu)",
           table, c.vector, c.width, c.height, c.stamp ? " stamped" : "", ok,
           static_cast<unsigned long>(crc), static_cast<unsigned long>(c.crc32),
           static_cast<unsigned long>(ink), static_cast<unsigned long>(c.ink));
  const bool match = ok && crc == c.crc32 && ink == c.ink;
  CHECK(match, msg);
  snprintf(msg, sizeof(msg), "%s %s at %dx%d: nothing written past the image", table, c.vector,
           c.width, c.height);
  CHECK(all_bytes_are(g_image + size, kGuard, 0xA5), msg);
  if (!match) {
    char path[256];
    snprintf(path, sizeof(path), "%s/%s_%dx%d%s.pbm", g_dump_dir, c.vector, c.width, c.height,
             c.stamp ? "_stamp" : "");
    printf("  wrote %s to diff against the Python render: %s\n", path,
           write_pbm(path, g_image, c.width, c.height) ? "ok" : "FAILED");
  }
}

void test_fr016_crc32_check_value() {
  const char check[] = "123456789";
  CHECK(lk::crc32(reinterpret_cast<const uint8_t*>(check), 9) == 0xCBF43926u,
        "CRC-32/ISO-HDLC check value, as zlib.crc32 gives");
  CHECK(lk::crc32(nullptr, 9) == 0 && lk::crc32(g_image, 0) == 0, "no bytes hash to 0");
  const uint8_t bits[] = {0xFF, 0x01, 0x80, 0x00};
  CHECK(lk::ink_count(bits, sizeof(bits)) == 10, "ink count is the number of 1 bits");
  CHECK(lk::ink_count(nullptr, 4) == 0, "a null buffer has no ink");
}

void test_fr016_spec_tables_match_the_code() {
  CHECK(kPanelSpecVersion == kExpectedPanelSpecVersion, "panel_spec_version is the one targeted");

  const int profiles = static_cast<int>(sizeof(kSpecProfiles) / sizeof(kSpecProfiles[0]));
  CHECK(profiles == lk::kPanelProfileCount, "the C++ has every spec profile");
  size_t most = 0;
  for (int i = 0; i < profiles && i < lk::kPanelProfileCount; i++) {
    const SpecProfile& p = kSpecProfiles[i];
    const lk::PanelProfile& q = lk::kPanelProfiles[i];
    char msg[96];
    snprintf(msg, sizeof(msg), "profile %s is %dx%d in both", p.name, p.width, p.height);
    CHECK(strcmp(p.name, q.name) == 0 && p.width == q.width && p.height == q.height, msg);
    CHECK(lk::check_size(p.width, p.height) && lk::is_profile_size(p.width, p.height), msg);
    const size_t size = lk::packed_size(p.width, p.height);
    most = size > most ? size : most;
  }
  CHECK(lk::kMaxPanelBytes == most, "the buffer cap is sized from the profile list");
  CHECK(lk::kMaxPanelBytes == 60000, "the kindle, 75 bytes x 800 rows, is the largest");
  CHECK(!lk::is_profile_size(297, 128) && !lk::is_profile_size(128, 296), "only pinned sizes");
  CHECK(lk::packed_size(0, 10) == 0 && lk::packed_size(10, -1) == 0, "no size, no bytes");
  CHECK(lk::packed_size(9, 2) == 4, "rows pad to whole bytes");

  for (const SpecTreatment& t : kSpecTreatments) {
    char msg[96];
    snprintf(msg, sizeof(msg), "headline '%s' is %s", t.headline, t.kind);
    CHECK(strcmp(lk::treatment_name(lk::treatment(t.headline)), t.kind) == 0, msg);
  }
  CHECK(strcmp(kSpecUnknownTreatment, "dashed") == 0, "the spec's unknown treatment is dashed");

  struct Named {
    const char* name;
    int value;
  };
  const Named ints[] = {
      {"band_pad", lk::kBandPad},
      {"rule_thickness", lk::kRuleThickness},
      {"hatch_width", lk::kHatchWidth},
      {"hatch_pitch", lk::kHatchPitch},
      {"dash_width", lk::kDashWidth},
      {"dash_on", lk::kDashOn},
      {"dash_off", lk::kDashOff},
      {"min_gap", lk::kMinGap},
      {"readable_scale", lk::kReadableScale},
      {"reserved_body_lines", lk::kReservedBodyLines},
      {"stamp_min_scale", lk::kStampMinScale},
      {"max_side", lk::kMaxSide},
  };
  for (const SpecIntConstant& spec : kSpecIntConstants) {
    bool found = false;
    for (const Named& mine : ints) {
      if (strcmp(mine.name, spec.name) != 0) continue;
      found = true;
      char msg[96];
      snprintf(msg, sizeof(msg), "constant %s is %d in both", spec.name, spec.value);
      CHECK(mine.value == spec.value, msg);
    }
    char msg[96];
    snprintf(msg, sizeof(msg), "spec constant %s has a C++ counterpart", spec.name);
    CHECK(found, msg);
  }
  for (const SpecTextConstant& spec : kSpecTextConstants) {
    const char* mine = nullptr;
    if (strcmp(spec.name, "reference_headline") == 0) mine = lk::kReferenceHeadline;
    if (strcmp(spec.name, "widest_line") == 0) mine = lk::kWidestLine;
    char msg[96];
    snprintf(msg, sizeof(msg), "spec constant %s matches", spec.name);
    CHECK(mine != nullptr && strcmp(mine, spec.value) == 0, msg);
  }
}

void test_fr016_every_panel_vector_matches_python() {
  for (const PanelCase& c : kPanelCases) check_case(c, "vector");
}

void test_fr016_extra_cases_match_python() {
  for (const PanelCase& c : kExtraCases) check_case(c, "extra");
}

void test_fr016_size_checks_match_python() {
  for (const SizeCheck& s : kSizeChecks) {
    char msg[96];
    snprintf(msg, sizeof(msg), "check_size(%d, %d) is %s, as in Python", s.width, s.height,
             s.ok ? "accepted" : "refused");
    CHECK(lk::check_size(s.width, s.height) == s.ok, msg);
  }
}

void test_fr016_stamp_checks_match_python() {
  const char* lines[] = {"IN RANGE", "112 mg/dL ->", "3 min ago"};
  for (const StampCheck& s : kStampChecks) {
    char msg[96];
    snprintf(msg, sizeof(msg), "check_stamp(\"%s\") is %s, as in Python", s.stamp,
             s.ok ? "accepted" : "refused");
    CHECK(lk::check_stamp(s.stamp) == s.ok, msg);
    CHECK(lk::render_panel(lines, 3, 296, 128, s.stamp, g_image, sizeof(g_image)) == s.ok, msg);
  }
  CHECK(!lk::check_stamp(nullptr), "no stamp is not a stamp");
}

// The dashed ring, worked out here from the written rule rather than the
// port: inset (margin - 2) / 2, 2 px thick, 4 on and 4 off from its corner.
bool ink_at(const uint8_t* rows, int width, int x, int y) {
  return (rows[y * ((width + 7) / 8) + x / 8] >> (7 - x % 8)) & 1;
}

bool margin_is_dashed(const uint8_t* rows, int width, int height, int edge) {
  const int t = lk::kDashWidth;
  const int inset = (edge - t) / 2;
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      const bool in_margin = x < edge || y < edge || x >= width - edge || y >= height - edge;
      if (!in_margin) continue;
      const bool in_box = x >= inset && y >= inset && x < width - inset && y < height - inset;
      const bool in_hole =
          x >= inset + t && y >= inset + t && x < width - inset - t && y < height - inset - t;
      const bool across = y < inset + t || y >= height - inset - t;
      const int along = across ? x - inset : y - inset;
      const bool want = in_box && !in_hole && along % (lk::kDashOn + lk::kDashOff) < lk::kDashOn;
      if (ink_at(rows, width, x, y) != want) return false;
    }
  }
  return true;
}

void test_fr007_unknown_headline_gets_the_dashed_frame() {
  CHECK(lk::treatment(nullptr) == lk::Treatment::Dashed, "no headline is dashed");
  CHECK(lk::treatment("CHECK NIGHTSCOUT") == lk::Treatment::Dashed, "unknown headline is dashed");
  CHECK(lk::treatment("in range") == lk::Treatment::Dashed, "headlines match exactly");
  CHECK(lk::treatment("IN RANGE ") == lk::Treatment::Dashed, "a trailing space is unknown");
  CHECK(lk::treatment("") == lk::Treatment::Dashed, "an empty headline is dashed");
  CHECK(lk::treatment("STALE") == lk::Treatment::Dashed, "a short STALE is not the STALE screen");

  const char* unknown[] = {"CHECK NIGHTSCOUT", "112 mg/dL ->", "3 min ago"};
  const char* fresh[] = {"IN RANGE", "112 mg/dL ->", "3 min ago"};
  const int edge = 8;  // margin(128): (128 * 6 + 50) / 100
  CHECK(lk::render_panel(unknown, 3, 296, 128, nullptr, g_image, sizeof(g_image)),
        "an unknown headline still draws");
  CHECK(margin_is_dashed(g_image, 296, 128, edge), "the unknown headline's margin is dashed");
  CHECK(lk::render_panel(fresh, 3, 296, 128, nullptr, g_image, sizeof(g_image)), "IN RANGE draws");
  CHECK(!margin_is_dashed(g_image, 296, 128, edge), "IN RANGE has no frame");
}

void test_fr016_refusals_leave_the_buffer_untouched() {
  const size_t size = lk::packed_size(296, 128);
  const char* good[] = {"IN RANGE", "112 mg/dL ->", "3 min ago"};
  const char* holes[] = {"IN RANGE", nullptr, "3 min ago"};
  char long_line[lk::kMaxPanelLineChars + 2];
  memset(long_line, 'x', sizeof(long_line) - 1);
  long_line[sizeof(long_line) - 1] = '\0';
  const char* too_long[] = {"NO DATA", long_line};
  const char* not_ascii[] = {"NO DATA", "caf\xc3\xa9"};
  const char* nine[] = {"NO DATA", "1", "2", "3", "4", "5", "6", "7", "8"};

  struct Refusal {
    const char* what;
    const char* const* lines;
    int count;
    int width;
    int height;
    const char* stamp;
    uint8_t* buffer;
    size_t buffer_size;
  };
  const Refusal refusals[] = {
      {"no lines array", nullptr, 3, 296, 128, nullptr, g_image, size},
      {"zero lines", good, 0, 296, 128, nullptr, g_image, size},
      {"negative count", good, -1, 296, 128, nullptr, g_image, size},
      {"more than kMaxPanelLines", nine, 9, 296, 128, nullptr, g_image, size},
      {"a null line", holes, 3, 296, 128, nullptr, g_image, size},
      {"a line past kMaxPanelLineChars", too_long, 2, 296, 128, nullptr, g_image, size},
      {"a byte outside ASCII", not_ascii, 2, 296, 128, nullptr, g_image, size},
      {"zero size", good, 3, 0, 0, nullptr, g_image, size},
      {"negative width", good, 3, -296, 128, nullptr, g_image, size},
      {"too narrow", good, 3, 156, 70, nullptr, g_image, size},
      {"too short", good, 3, 157, 69, nullptr, g_image, size},
      {"wider than kMaxSide", good, 3, 4097, 128, nullptr, g_image, size},
      {"a bad stamp", good, 3, 296, 128, "24:00", g_image, size},
      {"no buffer", good, 3, 296, 128, nullptr, nullptr, size},
      {"a buffer one byte short", good, 3, 296, 128, nullptr, g_image, size - 1},
      {"an empty buffer", good, 3, 296, 128, nullptr, g_image, 0},
  };
  for (const Refusal& r : refusals) {
    memset(g_image, 0x5A, size + kGuard);
    const bool drawn =
        lk::render_panel(r.lines, r.count, r.width, r.height, r.stamp, r.buffer, r.buffer_size);
    char msg[96];
    snprintf(msg, sizeof(msg), "refused and untouched: %s", r.what);
    CHECK(!drawn && all_bytes_are(g_image, size + kGuard, 0x5A), msg);
  }
  // The limits themselves are accepted.
  long_line[lk::kMaxPanelLineChars] = '\0';
  const char* at_limit[] = {"NO DATA", long_line, "1", "2", "3", "4", "5", "6"};
  CHECK(lk::render_panel(at_limit, lk::kMaxPanelLines, 296, 128, nullptr, g_image, size),
        "kMaxPanelLines lines of kMaxPanelLineChars draw");
}

void test_fr016_small_buffer_refused_and_untouched() {
  const char* lines[] = {"STALE - DO NOT TRUST", "last: 120 mg/dL ->", "16 min ago",
                         "Confirm on primary device"};
  for (const lk::PanelProfile& p : lk::kPanelProfiles) {
    const size_t size = lk::packed_size(p.width, p.height);
    char msg[96];
    memset(g_image, 0x3C, size + kGuard);
    snprintf(msg, sizeof(msg), "%s: a buffer one byte short is refused and untouched", p.name);
    CHECK(!lk::render_panel(lines, 4, p.width, p.height, "02:14", g_image, size - 1) &&
              all_bytes_are(g_image, size + kGuard, 0x3C),
          msg);
    snprintf(msg, sizeof(msg), "%s: the exact size draws and stops at its end", p.name);
    CHECK(lk::render_panel(lines, 4, p.width, p.height, "02:14", g_image, size) &&
              !all_bytes_are(g_image, size, 0x3C) && all_bytes_are(g_image + size, kGuard, 0x3C),
          msg);
  }
}

void test_fr016_portrait_mapping_matches_epd_buffer() {
  for (const EpdCase& c : kEpdCases) {
    const size_t size = lk::packed_size(c.width, c.height);
    const size_t out = lk::packed_size(c.height, c.width);
    memset(g_portrait, 0x77, out + kGuard);
    const bool drawn =
        lk::render_panel(c.lines, c.line_count, c.width, c.height, c.stamp, g_image, size);
    const bool rotated = lk::to_epd_portrait(g_image, size, c.width, c.height, g_portrait, out);
    const uint32_t crc = lk::crc32(g_portrait, out);
    char msg[128];
    snprintf(msg, sizeof(msg), "portrait %s at %dx%d equals Bitmap.to_epd_buffer (crc32 %lu)",
             c.name, c.width, c.height, static_cast<unsigned long>(crc));
    CHECK(drawn && rotated && out == c.length && crc == c.crc32, msg);
    CHECK(all_bytes_are(g_portrait + out, kGuard, 0x77), "nothing written past the portrait");
  }

  // Independently of Python: every pixel lands where the rule says, and the
  // padding bits stay 0, for one case at every profile.
  for (const lk::PanelProfile& p : lk::kPanelProfiles) {
    const char* lines[] = {"URGENT LOW", "55 mg/dL vv", "1 min ago"};
    const size_t size = lk::packed_size(p.width, p.height);
    const size_t out = lk::packed_size(p.height, p.width);
    const int out_stride = (p.height + 7) / 8;
    lk::render_panel(lines, 3, p.width, p.height, nullptr, g_image, size);
    lk::to_epd_portrait(g_image, size, p.width, p.height, g_portrait, out);
    bool mapped = true;
    for (int y = 0; y < p.height; y++) {
      for (int x = 0; x < p.width; x++) {
        const bool paper = ink_at(g_portrait, p.height, y, p.width - 1 - x);
        mapped = mapped && paper != ink_at(g_image, p.width, x, y);
      }
    }
    for (int row = 0; row < p.width; row++) {
      for (int px = p.height; px < out_stride * 8; px++) {
        mapped = mapped && !ink_at(g_portrait, out_stride * 8, px, row);
      }
    }
    char msg[96];
    snprintf(msg, sizeof(msg), "%s: (x, y) lands at (y, width - 1 - x), 1 = paper", p.name);
    CHECK(mapped, msg);
  }

  // A hand-worked 10x3 image: ink at (0, 0) and (9, 2) only.
  uint8_t landscape[6] = {0x80, 0x00, 0x00, 0x00, 0x00, 0x40};
  uint8_t portrait[10 + 1];
  memset(portrait, 0x11, sizeof(portrait));
  CHECK(lk::to_epd_portrait(landscape, 6, 10, 3, portrait, 10), "a 10x3 image rotates");
  const uint8_t want[10] = {0xC0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0x60};
  CHECK(memcmp(portrait, want, 10) == 0 && portrait[10] == 0x11, "the 10x3 image rotates exactly");

  struct Refusal {
    const char* what;
    const uint8_t* rows;
    size_t rows_size;
    int width;
    int height;
    uint8_t* out;
    size_t out_size;
  };
  const Refusal refusals[] = {
      {"zero width", landscape, 6, 0, 3, portrait, 10},
      {"zero height", landscape, 6, 10, 0, portrait, 10},
      {"wider than kMaxSide", landscape, 6, 4097, 3, portrait, 10},
      {"taller than kMaxSide", landscape, 6, 10, 4097, portrait, 10},
      {"no rows", nullptr, 6, 10, 3, portrait, 10},
      {"short rows", landscape, 5, 10, 3, portrait, 10},
      {"no output", landscape, 6, 10, 3, nullptr, 10},
      {"short output", landscape, 6, 10, 3, portrait, 9},
  };
  for (const Refusal& r : refusals) {
    memset(portrait, 0x11, sizeof(portrait));
    char msg[96];
    snprintf(msg, sizeof(msg), "portrait refused and untouched: %s", r.what);
    CHECK(!lk::to_epd_portrait(r.rows, r.rows_size, r.width, r.height, r.out, r.out_size) &&
              all_bytes_are(portrait, sizeof(portrait), 0x11),
          msg);
  }
}

void test_fr016_no_heap_allocation() {
  static int* volatile probe = nullptr;
  const long before = g_allocations;
  probe = new int(7);
  delete probe;
  CHECK(g_allocations == before + 1, "the allocation counter sees operator new");

  g_allocations = 0;
  for (const PanelCase& c : kPanelCases) {
    const size_t size = lk::packed_size(c.width, c.height);
    render(c, g_image, size);
    lk::to_epd_portrait(g_image, size, c.width, c.height, g_portrait, sizeof(g_portrait));
    lk::crc32(g_image, size);
    lk::ink_count(g_image, size);
    lk::check_size(c.width, c.height);
    lk::check_stamp(c.stamp);
    lk::treatment(c.lines[0]);
  }
  CHECK(g_allocations == 0, "rendering every vector allocates nothing");
}

void test_fr016_pbm_dump_round_trips() {
  const PanelCase& c = kPanelCases[0];
  const size_t size = lk::packed_size(c.width, c.height);
  render(c, g_image, size);
  char path[256];
  snprintf(path, sizeof(path), "%s/selftest_%dx%d.pbm", g_dump_dir, c.width, c.height);
  CHECK(write_pbm(path, g_image, c.width, c.height), "the PBM dump writes");
  char header[32];
  snprintf(header, sizeof(header), "P4\n%d %d\n", c.width, c.height);
  const size_t header_size = strlen(header);
  FILE* f = fopen(path, "rb");
  bool same = f != nullptr;
  if (f != nullptr) {
    char head[32] = {};
    same = fread(head, 1, header_size, f) == header_size && memcmp(head, header, header_size) == 0;
    same = same && fread(g_portrait, 1, size + 1, f) == size;  // exactly the rows, then the end
    fclose(f);
  }
  CHECK(same && memcmp(g_portrait, g_image, size) == 0, "the PBM holds the packed rows as drawn");
  remove(path);
}

void test_fr016_treatment_names() {
  CHECK(strcmp(lk::treatment_name(lk::Treatment::Plain), "plain") == 0, "plain");
  CHECK(strcmp(lk::treatment_name(lk::Treatment::Rule), "rule") == 0, "rule");
  CHECK(strcmp(lk::treatment_name(lk::Treatment::Inverse), "inverse") == 0, "inverse");
  CHECK(strcmp(lk::treatment_name(lk::Treatment::Stale), "stale") == 0, "stale");
  CHECK(strcmp(lk::treatment_name(lk::Treatment::Dashed), "dashed") == 0, "dashed");
  CHECK(strcmp(lk::treatment_name(static_cast<lk::Treatment>(99)), "dashed") == 0,
        "an out-of-range treatment names as the cautious dashed");
}

// The boards src/device_config.h defines, which platformio.ini builds.
const lk::BoardConfig kBoards[] = {lk::kBenchS3, lk::kX4};

// The steps src/main.cpp runs on the device, which has no Wi-Fi and no clock
// yet: there is no response body, so there is no reading, and the panel shows
// NO DATA with Nightscout unreachable, never a number. For each board in
// src/device_config.h, the size is a pinned profile and the pixels are that
// profile's pinned no_data_unreachable case. (The device sketch itself is
// Arduino code and only PlatformIO builds it; its config is plain constants.)
void test_fr010_device_skeleton_draws_the_pinned_no_data_screen() {
  const lk::JsonResult fetched = lk::newest_reading_from_json(nullptr, 0);
  const bool fetch_error = fetched.status != lk::JsonStatus::Ok;
  const lk::Reading* reading = !fetch_error && fetched.found ? &fetched.reading : nullptr;
  const lk::Status status = lk::classify(reading, 0, lk::Thresholds());
  lk::Lines lines;
  lk::render(status, fetch_error, &lines);
  CHECK(fetch_error && reading == nullptr && status.level == lk::Level::NoData,
        "no body, no reading, NO DATA");
  CHECK(lines.count == 4 && strcmp(lines.text[0], "NO DATA") == 0 &&
            strcmp(lines.text[3], "Nightscout unreachable") == 0,
        "the device names the failing link, without a number");
  const char* text[lk::kMaxLines] = {};
  for (int i = 0; i < lines.count; i++) text[i] = lines.text[i];

  for (const lk::BoardConfig& board : kBoards) {
    char msg[128];
    snprintf(msg, sizeof(msg), "%s: %dx%d is a pinned profile that fits the device buffer",
             board.name, board.panel_width, board.panel_height);
    const size_t size = lk::packed_size(board.panel_width, board.panel_height);
    CHECK(lk::is_profile_size(board.panel_width, board.panel_height) && size <= lk::kMaxPanelBytes,
          msg);
    int matched = 0;
    for (const PanelCase& c : kPanelCases) {
      if (strcmp(c.vector, "no_data_unreachable") != 0 || c.stamp != nullptr) continue;
      if (c.width != board.panel_width || c.height != board.panel_height) continue;
      const bool drawn = lk::render_panel(text, lines.count, c.width, c.height, nullptr, g_image,
                                          lk::kMaxPanelBytes);
      snprintf(msg, sizeof(msg), "%s: the device screen is the pinned %s case", board.name,
               c.profile);
      CHECK(drawn && lk::crc32(g_image, size) == c.crc32 && lk::ink_count(g_image, size) == c.ink,
            msg);
      matched++;
    }
    snprintf(msg, sizeof(msg), "%s: exactly one pinned no_data_unreachable case", board.name);
    CHECK(matched == 1, msg);
  }
}

// No pin is used until someone checks it on the bench: while kPinsVerified is
// false, every pin stays unset, so the coming e-paper driver cannot drive a
// guessed GPIO.
void test_fr010_device_pins_stay_unset_until_verified() {
  for (const lk::BoardConfig& board : kBoards) {
    const int pins[] = {board.pin_epd_sck, board.pin_epd_mosi, board.pin_epd_cs,   board.pin_epd_dc,
                        board.pin_epd_rst, board.pin_epd_busy, board.pin_epd_power};
    bool unset = true;
    for (int pin : pins) unset = unset && pin == lk::kPinUnset;
    char msg[96];
    snprintf(msg, sizeof(msg), "%s: pins are unset until verified", board.name);
    CHECK(lk::kPinsVerified || unset, msg);
  }
  CHECK(strcmp(lk::kBenchS3.name, "bench_s3") == 0 && strcmp(lk::kX4.name, "x4") == 0,
        "board names are the PlatformIO environments");
}

}  // namespace

int main(int argc, char** argv) {
  if (argc > 1) g_dump_dir = argv[1];
  test_fr016_crc32_check_value();
  test_fr016_spec_tables_match_the_code();
  test_fr016_every_panel_vector_matches_python();
  test_fr016_extra_cases_match_python();
  test_fr016_size_checks_match_python();
  test_fr016_stamp_checks_match_python();
  test_fr007_unknown_headline_gets_the_dashed_frame();
  test_fr016_refusals_leave_the_buffer_untouched();
  test_fr016_small_buffer_refused_and_untouched();
  test_fr016_portrait_mapping_matches_epd_buffer();
  test_fr016_no_heap_allocation();
  test_fr016_pbm_dump_round_trips();
  test_fr016_treatment_names();
  test_fr010_device_skeleton_draws_the_pinned_no_data_screen();
  test_fr010_device_pins_stay_unset_until_verified();
  printf("%d checks, %d failures (%d panel vectors, %d extra cases, %d sizes, %d stamps)\n",
         g_checks, g_failures, count_of(kPanelCases, sizeof(kPanelCases)),
         count_of(kExtraCases, sizeof(kExtraCases)),
         static_cast<int>(sizeof(kSizeChecks) / sizeof(kSizeChecks[0])),
         static_cast<int>(sizeof(kStampChecks) / sizeof(kStampChecks[0])));
  return g_failures == 0 ? 0 : 1;
}
