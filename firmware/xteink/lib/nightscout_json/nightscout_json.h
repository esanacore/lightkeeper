// nightscout_json: find the newest trustworthy reading in a raw Nightscout
// /api/v1/entries response, on a microcontroller.
//
// The body comes off the network, so it is untrusted input. This parser is a
// strict, streaming JSON reader with no heap and a fixed nesting limit: it
// reads only the `type`, `sgv`, `date`, and `direction` fields of each entry,
// skips everything else, and hands each entry to lk::parse_entry, keeping the
// newest survivor with the same lower-value tie-break as newest_reading. It
// mirrors Python's json.loads followed by parse_entries, and the shared
// corpus in spec/response_vectors.json is run against both.
//
// Known differences from Python, all in the safe direction (an error, which
// the display shows as NO DATA or an aging last-good reading):
// - Nesting deeper than kMaxJsonDepth is an error (Python allows about 1000).
// - A number longer than kMaxNumberChars is read as invalid, so that entry is
//   skipped.
// - Bytes outside ASCII inside strings are passed through, not validated as
//   UTF-8 (Python rejects invalid UTF-8 for the whole response).
// Like Python, the NaN, Infinity, and -Infinity literals parse as numbers and
// the entry holding them is then rejected (HAZ-011).

#pragma once

#include <stddef.h>

#include "glucose_rules.h"

namespace lk {

constexpr int kMaxJsonDepth = 32;
constexpr int kMaxNumberChars = 64;
constexpr int kMaxFieldChars = 24;  // longer strings can't match any field we read

enum class JsonStatus {
  Ok,         // a JSON list; `found` says whether it held a usable reading
  NotAList,   // valid JSON start, but not a list (an error object, for example)
  Malformed,  // not JSON at all, or trailing garbage
  TooDeep,    // nesting beyond kMaxJsonDepth
};

struct JsonResult {
  JsonStatus status = JsonStatus::Malformed;
  bool found = false;
  Reading reading;
  int entries_seen = 0;  // list elements examined, valid or not
};

// `body` need not be null-terminated; exactly `length` bytes are read.
JsonResult newest_reading_from_json(const char* body, size_t length);

const char* json_status_name(JsonStatus status);

}  // namespace lk
