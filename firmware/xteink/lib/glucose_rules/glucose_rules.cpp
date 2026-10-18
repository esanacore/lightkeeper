#include "glucose_rules.h"

#include <stdio.h>
#include <string.h>

namespace gw {

namespace {

struct TrendName {
  const char* name;
  Trend trend;
  const char* arrow;
};

// Nightscout direction strings and their plain-ASCII arrows.
const TrendName kTrends[] = {
    {"DoubleUp", Trend::DoubleUp, "^^"},         {"SingleUp", Trend::SingleUp, "^"},
    {"FortyFiveUp", Trend::FortyFiveUp, "/"},    {"Flat", Trend::Flat, "->"},
    {"FortyFiveDown", Trend::FortyFiveDown, "\\"}, {"SingleDown", Trend::SingleDown, "v"},
    {"DoubleDown", Trend::DoubleDown, "vv"},     {"Unknown", Trend::Unknown, "?"},
};

void set_line(Lines* out, const char* text) {
  if (out->count >= kMaxLines) return;
  snprintf(out->text[out->count], kLineChars, "%s", text);
  out->count++;
}

// Integer floor division, so -59 seconds is -1 minute (like Python's //).
int64_t floor_div(int64_t a, int64_t b) {
  int64_t q = a / b;
  if ((a % b != 0) && ((a < 0) != (b < 0))) q--;
  return q;
}

}  // namespace

bool Thresholds::valid() const {
  return 40 <= urgent_low && urgent_low < low && low < high && high < urgent_high && urgent_high <= 400 &&
         stale_after_ms > 0;
}

Trend trend_from_string(const char* direction) {
  if (direction == nullptr) return Trend::Unknown;
  for (const TrendName& t : kTrends) {
    if (strcmp(t.name, direction) == 0) return t.trend;
  }
  // An unrecognized arrow is not a reason to drop the number itself.
  return Trend::Unknown;
}

const char* trend_arrow(Trend trend) {
  for (const TrendName& t : kTrends) {
    if (t.trend == trend) return t.arrow;
  }
  return "?";
}

const char* level_name(Level level) {
  switch (level) {
    case Level::NoData: return "NO DATA";
    case Level::Stale: return "STALE";
    case Level::UrgentLow: return "URGENT LOW";
    case Level::Low: return "LOW";
    case Level::InRange: return "IN RANGE";
    case Level::High: return "HIGH";
    case Level::UrgentHigh: return "URGENT HIGH";
  }
  return "NO DATA";
}

bool needs_attention(Level level) { return level != Level::InRange; }

bool parse_entry(const RawEntry& entry, Reading* out) {
  if (out == nullptr) return false;
  if (entry.type != nullptr && strcmp(entry.type, "sgv") != 0) return false;

  if (!entry.has_sgv) return false;
  // Range check on the double first, so the int conversion below is safe.
  if (entry.sgv < kSensorMinMgdl || entry.sgv > kSensorMaxMgdl) return false;
  int mgdl = static_cast<int>(entry.sgv);
  if (static_cast<double>(mgdl) != entry.sgv) return false;  // fractional value

  if (!entry.has_date || !(entry.date_ms > 0)) return false;  // also rejects NaN

  out->mgdl = mgdl;
  out->timestamp_ms = static_cast<int64_t>(entry.date_ms);
  out->trend = trend_from_string(entry.direction);
  return true;
}

Status classify(const Reading* reading, int64_t now_ms, const Thresholds& t) {
  Status status;
  if (reading == nullptr) {
    status.level = Level::NoData;
    return status;
  }

  status.has_reading = true;
  status.reading = *reading;
  int64_t age = now_ms - reading->timestamp_ms;

  // Checked first, on purpose: stale or future-dated data is never trusted.
  if (age > t.stale_after_ms || age < -kMaxFutureSkewMs) {
    status.level = Level::Stale;
    status.age_ms = age;
    return status;
  }

  int mgdl = reading->mgdl;
  if (mgdl <= t.urgent_low) {
    status.level = Level::UrgentLow;
  } else if (mgdl < t.low) {
    status.level = Level::Low;
  } else if (mgdl >= t.urgent_high) {
    status.level = Level::UrgentHigh;
  } else if (mgdl > t.high) {
    status.level = Level::High;
  } else {
    status.level = Level::InRange;
  }
  status.age_ms = age < 0 ? 0 : age;
  return status;
}

int64_t age_minutes(const Status& status) { return floor_div(status.age_ms / 1000, 60); }

void render(const Status& status, bool fetch_error, Lines* out) {
  if (out == nullptr) return;
  *out = Lines();
  // Room for "last: " plus a full value; set_line truncates to the line size.
  char buf[kLineChars + 8];

  if (status.level == Level::NoData || !status.has_reading) {
    set_line(out, "NO DATA");
    set_line(out, "Check sensor and phone");
    set_line(out, "Confirm on primary device");
  } else {
    const Reading& r = status.reading;
    char value[kLineChars];
    if (r.mgdl <= kSensorMinMgdl) {
      snprintf(value, sizeof(value), "LOW (<40)");
    } else if (r.mgdl >= kSensorMaxMgdl) {
      snprintf(value, sizeof(value), "HIGH (>400)");
    } else {
      snprintf(value, sizeof(value), "%d mg/dL %s", r.mgdl, trend_arrow(r.trend));
    }

    int64_t minutes = age_minutes(status);
    char age_text[kLineChars];
    if (minutes == 0) {
      snprintf(age_text, sizeof(age_text), "just now");
    } else {
      snprintf(age_text, sizeof(age_text), "%lld min ago", static_cast<long long>(minutes));
    }

    if (status.level == Level::Stale) {
      if (minutes < 0) snprintf(age_text, sizeof(age_text), "time is in the future");
      set_line(out, "STALE - DO NOT TRUST");
      snprintf(buf, sizeof(buf), "last: %s", value);
      set_line(out, buf);
      set_line(out, age_text);
      set_line(out, "Confirm on primary device");
    } else {
      set_line(out, level_name(status.level));
      set_line(out, value);
      set_line(out, age_text);
    }
  }

  if (fetch_error) {
    if (out->count < kMaxLines) {
      set_line(out, "Nightscout unreachable");
    } else {
      // The four-line STALE screen is full; the warning matters more than
      // the "confirm" hint, which STALE's first line already implies.
      snprintf(out->text[kMaxLines - 1], kLineChars, "%s", "Nightscout unreachable");
    }
  }
}

}  // namespace gw
