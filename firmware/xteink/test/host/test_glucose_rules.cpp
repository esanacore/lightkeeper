// Host-side tests for glucose_rules. Builds with any C++17 compiler and runs
// on a PC, no device needed: `make test` in firmware/xteink.
//
// Two layers of tests:
//   1. The shared golden vectors (spec/display_vectors.json), proving this
//      code renders exactly what the Python implementation renders.
//   2. Edge cases specific to C++: NaN, huge values, null pointers, buffer limits.

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "glucose_rules.h"

namespace {

int g_failures = 0;
int g_checks = 0;

#define CHECK(cond, msg)                                              \
  do {                                                                \
    g_checks++;                                                       \
    if (!(cond)) {                                                    \
      g_failures++;                                                   \
      printf("FAIL %s:%d %s (%s)\n", __FILE__, __LINE__, msg, #cond); \
    }                                                                 \
  } while (0)

const int64_t kNowMs = 1792324800000LL;  // 2026-10-18T12:00:00Z
const int64_t kMinute = 60LL * 1000;

// One raw entry in a vector, dated seconds_ago before kNowMs.
struct VectorEntry {
  const char* type;
  bool has_sgv;
  double sgv;
  const char* direction;
  long long seconds_ago;
};

struct Vector {
  const char* name;
  int entry_count;
  const VectorEntry* entries;  // nullptr when entry_count is 0
  bool error;
  bool custom_thresholds;  // false: use lk::Thresholds() defaults
  int urgent_low;
  int low;
  int high;
  int urgent_high;
  int stale_after_minutes;
  const char* level;
  int line_count;
  const char* lines[4];
};

#include "vectors.inc"

const int kMaxVectorEntries = 8;

// Bump when an existing vector changes (Python and Swift carry the same check).
const int kExpectedSpecVersion = 1;
const int kSpecVersion =
#include "vectors_version.inc"
    ;

void run_vectors() {
  CHECK(kSpecVersion == kExpectedSpecVersion, "spec_version matches the one these tests target");
  for (const Vector& v : kVectors) {
    lk::RawEntry raws[kMaxVectorEntries];
    CHECK(v.entry_count <= kMaxVectorEntries, "vector fits the entry buffer");
    int count = v.entry_count < kMaxVectorEntries ? v.entry_count : kMaxVectorEntries;
    for (int i = 0; i < count; i++) {
      const VectorEntry& e = v.entries[i];
      raws[i].type = e.type;
      raws[i].has_sgv = e.has_sgv;
      raws[i].sgv = e.sgv;
      raws[i].has_date = true;
      raws[i].date_ms = static_cast<double>(kNowMs - e.seconds_ago * 1000);
      raws[i].direction = e.direction;
    }
    lk::Thresholds thresholds;
    if (v.custom_thresholds) {
      thresholds.urgent_low = v.urgent_low;
      thresholds.low = v.low;
      thresholds.high = v.high;
      thresholds.urgent_high = v.urgent_high;
      thresholds.stale_after_ms = v.stale_after_minutes * kMinute;
      CHECK(thresholds.valid(), "vector thresholds are valid");
    }
    lk::Reading reading;
    bool ok = lk::newest_reading(raws, count, &reading);
    lk::Status status = lk::classify(ok ? &reading : nullptr, kNowMs, thresholds);
    lk::Lines lines;
    lk::render(status, v.error, &lines);

    char msg[96];
    snprintf(msg, sizeof(msg), "vector %s: level", v.name);
    CHECK(strcmp(lk::level_name(status.level), v.level) == 0, msg);
    snprintf(msg, sizeof(msg), "vector %s: line count", v.name);
    CHECK(lines.count == v.line_count, msg);
    for (int i = 0; i < v.line_count && i < lines.count; i++) {
      snprintf(msg, sizeof(msg), "vector %s: line %d '%s'", v.name, i, lines.text[i]);
      CHECK(strcmp(lines.text[i], v.lines[i]) == 0, msg);
    }
  }
}

lk::RawEntry good_entry() {
  lk::RawEntry e;
  e.type = "sgv";
  e.has_sgv = true;
  e.sgv = 120;
  e.has_date = true;
  e.date_ms = static_cast<double>(kNowMs);
  e.direction = "Flat";
  return e;
}

void test_parse_edges() {
  lk::Reading r;
  lk::RawEntry e = good_entry();
  CHECK(lk::parse_entry(e, &r) && r.mgdl == 120, "good entry parses");

  e = good_entry();
  e.type = nullptr;
  CHECK(lk::parse_entry(e, &r), "missing type is treated as sgv");

  e = good_entry();
  e.sgv = NAN;
  CHECK(!lk::parse_entry(e, &r), "NaN value rejected");

  e = good_entry();
  e.sgv = 1e300;
  CHECK(!lk::parse_entry(e, &r), "huge value rejected without overflow");

  e = good_entry();
  e.sgv = -5;
  CHECK(!lk::parse_entry(e, &r), "negative value rejected");

  e = good_entry();
  e.sgv = 120.5;
  CHECK(!lk::parse_entry(e, &r), "fractional value rejected");

  e = good_entry();
  e.has_sgv = false;
  CHECK(!lk::parse_entry(e, &r), "missing value rejected");

  e = good_entry();
  e.has_date = false;
  CHECK(!lk::parse_entry(e, &r), "missing date rejected");

  e = good_entry();
  e.date_ms = NAN;
  CHECK(!lk::parse_entry(e, &r), "NaN date rejected");

  e = good_entry();
  e.date_ms = 0;
  CHECK(!lk::parse_entry(e, &r), "zero date rejected");

  e = good_entry();
  e.date_ms = 1e300;
  CHECK(!lk::parse_entry(e, &r), "huge date rejected before the int64 cast");

  e = good_entry();
  e.date_ms = static_cast<double>(kNowMs) / 1000.0;  // seconds, not milliseconds
  CHECK(!lk::parse_entry(e, &r), "date in seconds rejected instead of reading as 1970");

  e = good_entry();
  e.sgv = 1e30;
  CHECK(!lk::parse_entry(e, &r), "sgv 1e30 rejected without a cast");

  e = good_entry();
  e.direction = nullptr;
  CHECK(lk::parse_entry(e, &r) && r.trend == lk::Trend::Unknown, "missing direction is unknown");

  CHECK(!lk::parse_entry(good_entry(), nullptr), "null output pointer is safe");
}

void test_newest_reading_edges() {
  lk::Reading r;
  CHECK(!lk::newest_reading(nullptr, 0, &r), "no entries is no reading");
  CHECK(!lk::newest_reading(nullptr, 3, &r), "null entries with a count is safe");
  lk::RawEntry one[1] = {good_entry()};
  CHECK(!lk::newest_reading(one, 1, nullptr), "null output pointer is safe");
  r.mgdl = 77;
  lk::RawEntry bad = good_entry();
  bad.sgv = NAN;
  lk::RawEntry only_bad[1] = {bad};
  CHECK(!lk::newest_reading(only_bad, 1, &r) && r.mgdl == 77, "output untouched when none parse");
}

void test_thresholds() {
  lk::Thresholds t;
  CHECK(t.valid(), "defaults are valid");
  t.low = t.urgent_low;
  CHECK(!t.valid(), "urgent_low must be below low");
  t = lk::Thresholds();
  t.urgent_high = 450;
  CHECK(!t.valid(), "urgent_high capped at 400");
  t = lk::Thresholds();
  t.stale_after_ms = 0;
  CHECK(!t.valid(), "stale limit must be positive");
}

void test_render_limits() {
  lk::Lines lines;
  lk::render(lk::Status(), true, &lines);
  CHECK(lines.count == 4, "no data + error fits four lines");
  for (int i = 0; i < lines.count; i++) {
    CHECK(strlen(lines.text[i]) <= 26, "every line fits the panel width");
  }
  lk::render(lk::Status(), false, nullptr);  // must not crash
  CHECK(lk::needs_attention(lk::Level::Stale) && !lk::needs_attention(lk::Level::InRange),
        "attention rule");
  CHECK(strcmp(lk::trend_arrow(lk::trend_from_string("DoubleDown")), "vv") == 0, "arrow lookup");
}

void test_age_floor() {
  lk::Status s;
  s.age_ms = -59 * 1000;
  CHECK(lk::age_minutes(s) == -1, "negative age floors like Python");
  s.age_ms = 119 * 1000;
  CHECK(lk::age_minutes(s) == 1, "positive age floors");
  s.age_ms = -120500;
  CHECK(lk::age_minutes(s) == -3, "sub-second negative age floors like Python (-120.5 s // 60)");
  s.age_ms = 59999;
  CHECK(lk::age_minutes(s) == 0, "59.999 s is still 0 minutes");
}

void test_invalid_thresholds_never_classify() {
  lk::Reading r;
  r.mgdl = 45;
  r.timestamp_ms = kNowMs;
  lk::Thresholds bad;
  bad.low = bad.urgent_low;  // inverted: would hide lows
  lk::Status s = lk::classify(&r, kNowMs, bad);
  CHECK(s.level == lk::Level::NoData && !s.has_reading, "invalid thresholds give NO DATA");
}

}  // namespace

int main() {
  run_vectors();
  test_parse_edges();
  test_newest_reading_edges();
  test_thresholds();
  test_render_limits();
  test_age_floor();
  test_invalid_thresholds_never_classify();
  printf("%d checks, %d failures (%d shared vectors)\n", g_checks, g_failures,
         static_cast<int>(sizeof(kVectors) / sizeof(kVectors[0])));
  return g_failures == 0 ? 0 : 1;
}
