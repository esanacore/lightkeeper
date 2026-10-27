#include "nightscout_json.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

namespace lk {

namespace {

// A string value read into a fixed buffer. `overflow` means it was longer
// than the buffer and so cannot equal any name this parser compares against.
struct Text {
  char data[kMaxFieldChars + 1] = {};
  int size = 0;
  bool overflow = false;

  void push(char c) {
    if (size < kMaxFieldChars) {
      data[size++] = c;
      data[size] = '\0';
    } else {
      overflow = true;
    }
  }
  bool equals(const char* name) const { return !overflow && strcmp(data, name) == 0; }
};

// What a field we care about held, last occurrence wins (like Python's json).
enum class Kind { Absent, Number, String, Other };

struct Field {
  Kind kind = Kind::Absent;
  double number = 0;
  Text text;
};

class Parser {
 public:
  Parser(const char* body, size_t length) : p_(body), end_(body + length) {}

  JsonResult run() {
    JsonResult result;
    skip_ws();
    if (p_ == end_) return fail(result, JsonStatus::Malformed);
    if (*p_ != '[') {
      // Python reports any other JSON value as "not a list". Whether the rest
      // would parse doesn't change the outcome: the response is unusable.
      return fail(result, starts_value(*p_) ? JsonStatus::NotAList : JsonStatus::Malformed);
    }
    ++p_;
    skip_ws();
    if (consume(']')) return finish(result);
    while (true) {
      skip_ws();
      if (p_ == end_) return fail(result, JsonStatus::Malformed);
      result.entries_seen++;
      bool ok = (*p_ == '{') ? entry(result) : skip_value(1);
      if (!ok) return fail(result, status_);
      skip_ws();
      if (consume(',')) continue;
      if (consume(']')) return finish(result);
      return fail(result, JsonStatus::Malformed);
    }
  }

 private:
  const char* p_;
  const char* end_;
  JsonStatus status_ = JsonStatus::Malformed;

  JsonResult fail(JsonResult& result, JsonStatus status) {
    result.status = status;
    result.found = false;
    return result;
  }

  JsonResult finish(JsonResult& result) {
    skip_ws();
    if (p_ != end_) return fail(result, JsonStatus::Malformed);  // trailing garbage
    result.status = JsonStatus::Ok;
    return result;
  }

  static bool starts_value(char c) {
    return c == '{' || c == '"' || c == '-' || (c >= '0' && c <= '9') || c == 't' || c == 'f' ||
           c == 'n' || c == 'N' || c == 'I';
  }

  bool error(JsonStatus status) {
    status_ = status;
    return false;
  }

  void skip_ws() {
    while (p_ != end_ && (*p_ == ' ' || *p_ == '\t' || *p_ == '\n' || *p_ == '\r')) ++p_;
  }

  bool consume(char c) {
    if (p_ != end_ && *p_ == c) {
      ++p_;
      return true;
    }
    return false;
  }

  bool literal(const char* word) {
    size_t n = strlen(word);
    if (static_cast<size_t>(end_ - p_) < n || memcmp(p_, word, n) != 0) {
      return error(JsonStatus::Malformed);
    }
    p_ += n;
    return true;
  }

  static int hex(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
  }

  // Reads a string starting at the opening quote. `out` may be null (skip).
  bool string(Text* out) {
    ++p_;  // opening quote
    while (true) {
      if (p_ == end_) return error(JsonStatus::Malformed);
      unsigned char c = static_cast<unsigned char>(*p_++);
      if (c == '"') return true;
      if (c < 0x20) return error(JsonStatus::Malformed);  // raw control character
      if (c != '\\') {
        if (out) out->push(static_cast<char>(c));
        continue;
      }
      if (p_ == end_) return error(JsonStatus::Malformed);
      char e = *p_++;
      char decoded;
      switch (e) {
        case '"':
          decoded = '"';
          break;
        case '\\':
          decoded = '\\';
          break;
        case '/':
          decoded = '/';
          break;
        case 'b':
          decoded = '\b';
          break;
        case 'f':
          decoded = '\f';
          break;
        case 'n':
          decoded = '\n';
          break;
        case 'r':
          decoded = '\r';
          break;
        case 't':
          decoded = '\t';
          break;
        case 'u': {
          if (end_ - p_ < 4) return error(JsonStatus::Malformed);
          int code = 0;
          for (int i = 0; i < 4; i++) {
            int digit = hex(p_[i]);
            if (digit < 0) return error(JsonStatus::Malformed);
            code = code * 16 + digit;
          }
          p_ += 4;
          // Field names and values we compare are ASCII; anything else just
          // has to not match, so it becomes a byte no name contains.
          decoded = code < 0x80 ? static_cast<char>(code) : '\x01';
          break;
        }
        default:
          return error(JsonStatus::Malformed);
      }
      if (out) out->push(decoded);
    }
  }

  // Strict JSON number, plus Python's NaN / Infinity / -Infinity literals.
  bool number(double* out) {
    const char* start = p_;
    if (consume('-')) {
      if (p_ != end_ && *p_ == 'I') {
        if (!literal("Infinity")) return false;
        *out = -HUGE_VAL;
        return true;
      }
    }
    if (p_ == end_) return error(JsonStatus::Malformed);
    if (*p_ == '0') {
      ++p_;
    } else if (*p_ >= '1' && *p_ <= '9') {
      while (p_ != end_ && *p_ >= '0' && *p_ <= '9') ++p_;
    } else {
      return error(JsonStatus::Malformed);
    }
    if (p_ != end_ && *p_ >= '0' && *p_ <= '9') return error(JsonStatus::Malformed);  // 0120
    if (consume('.')) {
      if (p_ == end_ || *p_ < '0' || *p_ > '9') return error(JsonStatus::Malformed);
      while (p_ != end_ && *p_ >= '0' && *p_ <= '9') ++p_;
    }
    if (p_ != end_ && (*p_ == 'e' || *p_ == 'E')) {
      ++p_;
      if (p_ != end_ && (*p_ == '+' || *p_ == '-')) ++p_;
      if (p_ == end_ || *p_ < '0' || *p_ > '9') return error(JsonStatus::Malformed);
      while (p_ != end_ && *p_ >= '0' && *p_ <= '9') ++p_;
    }
    long n = static_cast<long>(p_ - start);
    if (n > kMaxNumberChars) {
      *out = NAN;  // well-formed but too long to read here: the entry is skipped
      return true;
    }
    char buf[kMaxNumberChars + 1];
    memcpy(buf, start, static_cast<size_t>(n));
    buf[n] = '\0';
    *out = strtod(buf, nullptr);  // "C" locale on the host and on newlib
    return true;
  }

  // Skips any value. `depth` is the nesting level of the container holding it.
  bool skip_value(int depth) {
    skip_ws();
    if (p_ == end_) return error(JsonStatus::Malformed);
    switch (*p_) {
      case '{':
      case '[':
        return skip_container(depth + 1);
      case '"':
        return string(nullptr);
      case 't':
        return literal("true");
      case 'f':
        return literal("false");
      case 'n':
        return literal("null");
      case 'N':
        return literal("NaN");
      case 'I':
        return literal("Infinity");
      default: {
        double ignored;
        return number(&ignored);
      }
    }
  }

  bool skip_container(int depth) {
    if (depth > kMaxJsonDepth) return error(JsonStatus::TooDeep);
    char open = *p_++;
    char close = open == '{' ? '}' : ']';
    skip_ws();
    if (consume(close)) return true;
    while (true) {
      skip_ws();
      if (open == '{') {
        if (p_ == end_ || *p_ != '"') return error(JsonStatus::Malformed);
        if (!string(nullptr)) return false;
        skip_ws();
        if (!consume(':')) return error(JsonStatus::Malformed);
      }
      if (!skip_value(depth)) return false;
      skip_ws();
      if (consume(',')) continue;
      if (consume(close)) return true;
      return error(JsonStatus::Malformed);
    }
  }

  // Reads the value of a field we care about.
  bool field(Field* f) {
    skip_ws();
    if (p_ == end_) return error(JsonStatus::Malformed);
    char c = *p_;
    if (c == '"') {
      f->kind = Kind::String;
      f->text = Text();
      return string(&f->text);
    }
    if (c == '-' || (c >= '0' && c <= '9') || c == 'N' || c == 'I') {
      f->kind = Kind::Number;
      if (c == 'N') {
        f->number = NAN;
        return literal("NaN");
      }
      if (c == 'I') {
        f->number = HUGE_VAL;
        return literal("Infinity");
      }
      return number(&f->number);
    }
    f->kind = Kind::Other;  // true, false, null, an object or a list
    return skip_value(2);
  }

  // One list element that is an object: read the four fields, then judge it.
  bool entry(JsonResult& result) {
    Field type, sgv, date, direction;
    ++p_;  // '{'
    skip_ws();
    if (!consume('}')) {
      while (true) {
        skip_ws();
        if (p_ == end_ || *p_ != '"') return error(JsonStatus::Malformed);
        Text key;
        if (!string(&key)) return false;
        skip_ws();
        if (!consume(':')) return error(JsonStatus::Malformed);
        Field* target = key.equals("type")        ? &type
                        : key.equals("sgv")       ? &sgv
                        : key.equals("date")      ? &date
                        : key.equals("direction") ? &direction
                                                  : nullptr;
        if (target) {
          if (!field(target)) return false;
        } else if (!skip_value(2)) {
          return false;
        }
        skip_ws();
        if (consume(',')) continue;
        if (consume('}')) break;
        return error(JsonStatus::Malformed);
      }
    }

    RawEntry raw;
    // Missing type means "sgv"; a non-string or unreadable type matches nothing.
    if (type.kind == Kind::String) {
      raw.type = type.text.overflow ? "" : type.text.data;
    } else if (type.kind != Kind::Absent) {
      raw.type = "";
    }
    raw.has_sgv = sgv.kind == Kind::Number;
    raw.sgv = sgv.number;
    raw.has_date = date.kind == Kind::Number;
    raw.date_ms = date.number;
    // A non-string or unknown direction is Trend::Unknown, as in Python.
    raw.direction = (direction.kind == Kind::String && !direction.text.overflow)
                        ? direction.text.data
                        : nullptr;

    Reading r;
    if (parse_entry(raw, &r)) {
      if (!result.found || r.timestamp_ms > result.reading.timestamp_ms ||
          (r.timestamp_ms == result.reading.timestamp_ms && r.mgdl < result.reading.mgdl)) {
        result.reading = r;
        result.found = true;
      }
    }
    return true;
  }
};

}  // namespace

JsonResult newest_reading_from_json(const char* body, size_t length) {
  if (body == nullptr) {
    JsonResult result;
    result.status = JsonStatus::Malformed;
    return result;
  }
  return Parser(body, length).run();
}

const char* json_status_name(JsonStatus status) {
  switch (status) {
    case JsonStatus::Ok:
      return "ok";
    case JsonStatus::NotAList:
      return "not a list";
    case JsonStatus::Malformed:
      return "malformed";
    case JsonStatus::TooDeep:
      return "too deep";
  }
  return "malformed";
}

}  // namespace lk
