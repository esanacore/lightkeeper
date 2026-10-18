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

#define CHECK(cond, msg)                                                  \
  do {                                                                    \
    g_checks++;                                                           \
    if (!(cond)) {                                                        \
      g_failures++;                                                       \
      printf("FAIL %s:%d %s (%s)\n", __FILE__, __LINE__, msg, #cond);     \
    }                                                                     \
  } while (0)

const int64_t kNowMs = 1792324800000LL;  // 2026-10-18T12:00:00Z
const int64_t kMinute = 60LL * 1000;

struct Vector {
  const char* name;
  bool has_entry;
  const char* type;
  bool has_sgv;
  double sgv;
  const char* direction;
  int minutes_ago;
  bool error;
  const char* level;
  int line_count;
  const char* lines[4];
};

const Vector kVectors[] = {
#include "vectors.inc"
};

void run_vectors() {
  for (const Vector& v : kVectors) {
    lk::Reading reading;
    bool ok = false;
    if (v.has_entry) {
      lk::RawEntry raw;
      raw.type = v.type;
      raw.has_sgv = v.has_sgv;
      raw.sgv = v.sgv;
      raw.has_date = true;
      raw.date_ms = static_cast<double>(kNowMs - v.minutes_ago * kMinute);
      raw.direction = v.direction;
      ok = lk::parse_entry(raw, &reading);
    }
    lk::Status status = lk::classify(ok ? &reading : nullptr, kNowMs, lk::Thresholds());
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
  e.direction = nullptr;
  CHECK(lk::parse_entry(e, &r) && r.trend == lk::Trend::Unknown, "missing direction is unknown");

  CHECK(!lk::parse_entry(good_entry(), nullptr), "null output pointer is safe");
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
  CHECK(lk::needs_attention(lk::Level::Stale) && !lk::needs_attention(lk::Level::InRange), "attention rule");
  CHECK(strcmp(lk::trend_arrow(lk::trend_from_string("DoubleDown")), "vv") == 0, "arrow lookup");
}

void test_age_floor() {
  lk::Status s;
  s.age_ms = -59 * 1000;
  CHECK(lk::age_minutes(s) == -1, "negative age floors like Python");
  s.age_ms = 119 * 1000;
  CHECK(lk::age_minutes(s) == 1, "positive age floors");
}

}  // namespace

int main() {
  run_vectors();
  test_parse_edges();
  test_thresholds();
  test_render_limits();
  test_age_floor();
  printf("%d checks, %d failures (%d shared vectors)\n", g_checks, g_failures,
         static_cast<int>(sizeof(kVectors) / sizeof(kVectors[0])));
  return g_failures == 0 ? 0 : 1;
}
