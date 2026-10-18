// glucose_rules: the safety rules from lightkeeper, ported to C++ for the
// ESP32-C3 in the Xteink X4/X3 pocket e-ink readers.
//
// This file is pure logic: no Arduino, no Wi-Fi, no display, no heap. The
// device code (still to come) extracts fields from the Nightscout JSON, calls
// parse_entry -> classify -> render, and draws the lines. Keeping it pure
// means the exact same code runs in host tests on a PC and on the device.
//
// It must behave identically to src/lightkeeper. The shared vectors in
// spec/display_vectors.json are run against both implementations.
//
// Safety: stale or future-dated data is never shown as current, and bad
// entries are rejected rather than repaired. See docs/SAFETY.md.

#pragma once

#include <stdint.h>

namespace lk {

// Dexcom and Libre sensors report 40-400 mg/dL; 39 and 401 are the
// Nightscout sentinels for below and above range.
constexpr int kSensorMinMgdl = 39;
constexpr int kSensorMaxMgdl = 401;

// A reading this far in the future means a clock is wrong somewhere.
constexpr int64_t kMaxFutureSkewMs = 2LL * 60 * 1000;

constexpr int kMaxLines = 4;
constexpr int kLineChars = 32;  // buffer size per line, including the null

enum class Trend {
  DoubleUp,
  SingleUp,
  FortyFiveUp,
  Flat,
  FortyFiveDown,
  SingleDown,
  DoubleDown,
  Unknown
};

enum class Level { NoData, Stale, UrgentLow, Low, InRange, High, UrgentHigh };

struct Thresholds {
  int urgent_low = 55;
  int low = 70;
  int high = 180;
  int urgent_high = 250;
  int64_t stale_after_ms = 15LL * 60 * 1000;

  // Same rule as the Python Thresholds: 40 <= urgent_low < low < high < urgent_high <= 400.
  bool valid() const;
};

// Fields pulled out of one Nightscout entry by the JSON layer. A field that
// is missing or not a number sets its has_ flag to false.
struct RawEntry {
  const char* type = nullptr;  // nullptr means "not present" (treated as "sgv")
  bool has_sgv = false;
  double sgv = 0;
  bool has_date = false;
  double date_ms = 0;
  const char* direction = nullptr;  // nullptr means "not present"
};

struct Reading {
  int mgdl = 0;
  int64_t timestamp_ms = 0;
  Trend trend = Trend::Unknown;
};

struct Status {
  Level level = Level::NoData;
  bool has_reading = false;
  Reading reading;
  int64_t age_ms = 0;  // clamped to 0 for fresh readings; raw for STALE
};

struct Lines {
  int count = 0;
  char text[kMaxLines][kLineChars] = {};
};

// Returns true and fills *out only when the entry can be trusted.
bool parse_entry(const RawEntry& entry, Reading* out);

Trend trend_from_string(const char* direction);
const char* trend_arrow(Trend trend);
const char* level_name(Level level);
bool needs_attention(Level level);

// reading may be nullptr (no data). now_ms is Unix time in milliseconds.
// Invalid thresholds yield NoData: a number is never judged against bad limits.
Status classify(const Reading* reading, int64_t now_ms, const Thresholds& thresholds);

// Floor of age in whole minutes, matching Python's `seconds // 60`.
int64_t age_minutes(const Status& status);

// fetch_error: true when the latest Nightscout fetch failed.
void render(const Status& status, bool fetch_error, Lines* out);

}  // namespace lk
