// Host tests for nightscout_json: the heap-free parser for raw Nightscout
// responses. Built with AddressSanitizer and UBSan by `make test`.
//
// Three layers:
//   1. The shared response corpus (spec/response_vectors.json), which the
//      Python and Swift suites also run: same body, same conclusion.
//   2. Edge cases only the firmware has: nesting and number-length limits,
//      the NaN / Infinity literals, a null body.
//   3. A deterministic fuzz pass: thousands of mutated bodies must never
//      crash, and anything found must still be a trustworthy reading.

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "nightscout_json.h"

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

struct ResponseVector {
  const char* name;
  const char* body;
  unsigned length;
  int expect;  // 0 error, 1 no reading, 2 reading
  int mgdl;
  long long date;
  const char* trend;
};

const ResponseVector kResponses[] = {
#include "response_vectors.inc"
};

// Bump when an existing case changes (Python and Swift carry the same check).
const int kExpectedSpecVersion = 1;
const int kSpecVersion =
#include "response_vectors_version.inc"
    ;

lk::JsonResult parse(const char* text) { return lk::newest_reading_from_json(text, strlen(text)); }

void run_corpus() {
  CHECK(kSpecVersion == kExpectedSpecVersion, "response spec_version matches");
  for (const ResponseVector& v : kResponses) {
    lk::JsonResult r = lk::newest_reading_from_json(v.body, v.length);
    char msg[128];
    snprintf(msg, sizeof(msg), "response %s: status %s", v.name, lk::json_status_name(r.status));
    if (v.expect == 0) {
      CHECK(r.status != lk::JsonStatus::Ok, msg);
      continue;
    }
    CHECK(r.status == lk::JsonStatus::Ok, msg);
    snprintf(msg, sizeof(msg), "response %s: found", v.name);
    CHECK(r.found == (v.expect == 2), msg);
    if (v.expect == 2 && r.found) {
      snprintf(msg, sizeof(msg), "response %s: mgdl %d", v.name, r.reading.mgdl);
      CHECK(r.reading.mgdl == v.mgdl, msg);
      snprintf(msg, sizeof(msg), "response %s: date", v.name);
      CHECK(r.reading.timestamp_ms == v.date, msg);
      snprintf(msg, sizeof(msg), "response %s: trend %s", v.name, lk::trend_arrow(r.reading.trend));
      CHECK(r.reading.trend == lk::trend_from_string(v.trend), msg);
    }
  }
}

void test_firmware_only_edges() {
  CHECK(lk::newest_reading_from_json(nullptr, 10).status == lk::JsonStatus::Malformed,
        "null body is malformed, not a crash");

  // Python parses these literals as numbers, then rejects the entry (HAZ-011):
  // the good reading beside it still wins.
  lk::JsonResult r = parse(
      "[{\"sgv\": NaN, \"date\": 1792324800000, \"type\": \"sgv\"},"
      " {\"sgv\": Infinity, \"date\": 1792324800000},"
      " {\"sgv\": -Infinity, \"date\": 1792324800000},"
      " {\"sgv\": 111, \"date\": 1792324500000, \"direction\": \"Flat\"}]");
  CHECK(r.status == lk::JsonStatus::Ok && r.found && r.reading.mgdl == 111,
        "NaN and Infinity entries are skipped, the good one is kept");
  CHECK(parse("[NaN, Infinity, -Infinity]").status == lk::JsonStatus::Ok,
        "the literals are valid list elements");
  CHECK(parse("[-Inf]").status == lk::JsonStatus::Malformed, "a partial literal is malformed");

  // Nesting: exactly at the limit is fine, one more is refused.
  char deep[256];
  int depth = lk::kMaxJsonDepth;
  int n = 0;
  for (int i = 0; i < depth; i++) deep[n++] = '[';
  for (int i = 0; i < depth; i++) deep[n++] = ']';
  deep[n] = '\0';
  CHECK(parse(deep).status == lk::JsonStatus::Ok, "nesting at the limit is accepted");
  n = 0;
  for (int i = 0; i <= depth; i++) deep[n++] = '[';
  for (int i = 0; i <= depth; i++) deep[n++] = ']';
  deep[n] = '\0';
  CHECK(parse(deep).status == lk::JsonStatus::TooDeep, "nesting past the limit is refused");

  // A well-formed number too long to read makes that entry invalid, nothing more.
  char longnum[256];
  snprintf(longnum, sizeof(longnum),
           "[{\"sgv\": 120.%060d1, \"date\": 1792324800000}, "
           "{\"sgv\": 90, \"date\": 1792324500000}]",
           0);
  r = parse(longnum);
  CHECK(r.status == lk::JsonStatus::Ok && r.found && r.reading.mgdl == 90,
        "an over-long number skips its entry");

  // A string field longer than the buffer can't match "sgv" or a direction.
  r = parse(
      "[{\"type\": \"sgvsgvsgvsgvsgvsgvsgvsgvsgv\", \"sgv\": 120, \"date\": 1792324800000},"
      " {\"sgv\": 91, \"date\": 1792324500000,"
      " \"direction\": \"FlatFlatFlatFlatFlatFlatFlat\"}]");
  CHECK(r.found && r.reading.mgdl == 91 && r.reading.trend == lk::Trend::Unknown,
        "over-long strings never match");

  // Uppercase hex escape, '+' exponent, an over-long key, and a timestamp tie
  // where the higher value comes second.
  r = parse(
      "[{\"\u0073gv\": 1.2E+2, \"date\": 1792324800000, \"direction\": \"\u0046lat\"},"
      " {\"a_key_much_longer_than_the_field_buffer\": 1, \"sgv\": 150, \"date\": 1792324800000}]");
  CHECK(r.status == lk::JsonStatus::Ok && r.found && r.reading.mgdl == 120 &&
            r.reading.trend == lk::Trend::Flat,
        "escaped key, uppercase hex, '+' exponent; the lower tied value wins");

  CHECK(parse("  ").status == lk::JsonStatus::Malformed, "whitespace only is malformed");
  CHECK(parse("\"text\"").status == lk::JsonStatus::NotAList, "a string is not a list");
  CHECK(parse("[{\"a\" 1}]").status == lk::JsonStatus::Malformed, "missing colon");
  CHECK(parse("[{1: 2}]").status == lk::JsonStatus::Malformed, "non-string key");
  CHECK(parse("[1 2]").status == lk::JsonStatus::Malformed, "missing comma");
  CHECK(parse("[\"\\u12\"]").status == lk::JsonStatus::Malformed, "short unicode escape");
  CHECK(parse("[\"\\u12g4\"]").status == lk::JsonStatus::Malformed, "bad hex digit");
  CHECK(parse("[1.]").status == lk::JsonStatus::Malformed, "fraction without digits");
  CHECK(parse("[1e]").status == lk::JsonStatus::Malformed, "exponent without digits");
  CHECK(parse("[-]").status == lk::JsonStatus::Malformed, "lone minus");
  CHECK(parse("[tru]").status == lk::JsonStatus::Malformed, "partial true");
  CHECK(strcmp(lk::json_status_name(lk::JsonStatus::TooDeep), "too deep") == 0, "status names");
  CHECK(strcmp(lk::json_status_name(lk::JsonStatus::NotAList), "not a list") == 0, "status names");
  CHECK(strcmp(lk::json_status_name(static_cast<lk::JsonStatus>(99)), "malformed") == 0,
        "unknown status names as malformed");
}

// xorshift32: deterministic, so a failure reproduces exactly.
unsigned g_rng = 0x2545F491u;
unsigned next_random() {
  g_rng ^= g_rng << 13;
  g_rng ^= g_rng >> 17;
  g_rng ^= g_rng << 5;
  return g_rng;
}

void check_trustworthy(const lk::JsonResult& r, const char* what) {
  if (!r.found) return;
  CHECK(r.status == lk::JsonStatus::Ok, what);
  CHECK(r.reading.mgdl >= lk::kSensorMinMgdl && r.reading.mgdl <= lk::kSensorMaxMgdl, what);
  CHECK(r.reading.timestamp_ms >= static_cast<long long>(lk::kMinDateMs) &&
            r.reading.timestamp_ms <= static_cast<long long>(lk::kMaxDateMs),
        what);
}

void fuzz() {
  const char interesting[] = "{}[]\":,\\-.eE0123456789ntfuNI \n";
  char buf[1024];
  int runs = 0;
  for (const ResponseVector& v : kResponses) {
    for (int round = 0; round < 400; round++) {
      unsigned length = v.length < sizeof(buf) ? v.length : sizeof(buf) - 1;
      memcpy(buf, v.body, length);
      int edits = 1 + static_cast<int>(next_random() % 4);
      for (int k = 0; k < edits && length > 0; k++) {
        unsigned at = next_random() % length;
        switch (next_random() % 4) {
          case 0:  // overwrite with a structural character
            buf[at] = interesting[next_random() % (sizeof(interesting) - 1)];
            break;
          case 1:  // overwrite with any byte
            buf[at] = static_cast<char>(next_random() & 0xFF);
            break;
          case 2:  // truncate
            length = at;
            break;
          default:  // delete one byte
            memmove(buf + at, buf + at + 1, length - at - 1);
            length--;
            break;
        }
      }
      check_trustworthy(lk::newest_reading_from_json(buf, length), v.name);
      runs++;
    }
  }
  // Pure noise, too.
  for (int round = 0; round < 2000; round++) {
    unsigned length = next_random() % sizeof(buf);
    for (unsigned i = 0; i < length; i++) {
      buf[i] = (next_random() & 1) ? interesting[next_random() % (sizeof(interesting) - 1)]
                                   : static_cast<char>(next_random() & 0xFF);
    }
    check_trustworthy(lk::newest_reading_from_json(buf, length), "noise");
    runs++;
  }
  printf("fuzz: %d mutated bodies, no crash\n", runs);
}

}  // namespace

int main() {
  run_corpus();
  test_firmware_only_edges();
  fuzz();
  printf("%d checks, %d failures (%d response vectors)\n", g_checks, g_failures,
         static_cast<int>(sizeof(kResponses) / sizeof(kResponses[0])));
  return g_failures == 0 ? 0 : 1;
}
