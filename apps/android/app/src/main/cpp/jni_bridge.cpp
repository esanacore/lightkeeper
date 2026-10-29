// jni_bridge: the only C++ the Android app owns. It hands the firmware's own
// libraries (firmware/xteink/lib, compiled in place by CMakeLists.txt) to
// Kotlin, so the phone runs the same rules and draws the same pixels as the
// bedside panel: there is no fourth implementation of the rules.
//
// Three calls, each pure and stateless (NativeRules.kt is their only caller):
// - nativeReadBody: the newest trustworthy reading in a raw Nightscout
//   entries body, by lk::newest_reading_from_json, the firmware's parser;
// - nativeRenderLines: lk::classify then lk::render for a reading (or none)
//   at a given time, thresholds and fetch outcome. A fetched body becomes
//   lines this way, and the last good reading is re-aged this way with no
//   fetch at all;
// - nativeRenderPanel: the 1-bit panel image for lines, by lk::render_panel,
//   as packed rows.
//
// Safety: a reading that comes back from Kotlin goes through lk::parse_entry
// again before it is classified, so a value the parser would never have
// produced can only ever show as NO DATA. Every refusal is a null (or NO
// DATA), never a guess, and nothing here keeps state between calls.

#include <jni.h>
#include <stddef.h>
#include <stdint.h>

#include "glucose_rules.h"
#include "nightscout_json.h"
#include "panel_bitmap.h"

namespace {

// The trend codes Kotlin round-trips, in lk::Trend's order. An unknown code
// becomes Trend::Unknown ("?"), never another arrow.
constexpr lk::Trend kTrends[] = {
    lk::Trend::DoubleUp,      lk::Trend::SingleUp,   lk::Trend::FortyFiveUp, lk::Trend::Flat,
    lk::Trend::FortyFiveDown, lk::Trend::SingleDown, lk::Trend::DoubleDown,  lk::Trend::Unknown,
};
constexpr int kTrendCount = static_cast<int>(sizeof(kTrends) / sizeof(kTrends[0]));

int trend_code(lk::Trend trend) {
  for (int i = 0; i < kTrendCount; i++) {
    if (kTrends[i] == trend) return i;
  }
  return kTrendCount - 1;
}

lk::Trend trend_from_code(jint code) {
  return code >= 0 && code < kTrendCount ? kTrends[code] : lk::Trend::Unknown;
}

// The JSON outcome as NativeRules.kt numbers it.
jlong status_code(lk::JsonStatus status) {
  switch (status) {
    case lk::JsonStatus::Ok:
      return 0;
    case lk::JsonStatus::NotAList:
      return 1;
    case lk::JsonStatus::Malformed:
      return 2;
    case lk::JsonStatus::TooDeep:
      return 3;
  }
  return 2;
}

// Where each field sits in nativeReadBody's result; NativeRules.kt reads the same slots.
enum BodyField { kStatus, kFound, kMgdl, kTimestamp, kTrend, kEntriesSeen, kBodyFieldCount };

// The lines as a Java String[]; nullptr (with OutOfMemoryError pending) if allocation fails.
jobjectArray to_java_lines(JNIEnv* env, const lk::Lines& lines) {
  jclass string_class = env->FindClass("java/lang/String");
  if (string_class == nullptr) return nullptr;
  jobjectArray out = env->NewObjectArray(lines.count, string_class, nullptr);
  env->DeleteLocalRef(string_class);
  if (out == nullptr) return nullptr;
  for (int i = 0; i < lines.count; i++) {
    // glucose_rules writes ASCII only, which is valid modified UTF-8.
    jstring text = env->NewStringUTF(lines.text[i]);
    if (text == nullptr) return nullptr;
    env->SetObjectArrayElement(out, i, text);
    env->DeleteLocalRef(text);
  }
  return out;
}

// Copies `text` into `out` as modified UTF-8 with a terminating null. False,
// for the caller to refuse, when `text` is null or does not fit `size` bytes.
bool copy_string(JNIEnv* env, jstring text, char* out, size_t size) {
  if (text == nullptr) return false;
  const jsize length = env->GetStringUTFLength(text);
  if (length < 0 || static_cast<size_t>(length) >= size) return false;
  env->GetStringUTFRegion(text, 0, env->GetStringLength(text), out);
  out[length] = '\0';
  return env->ExceptionCheck() == JNI_FALSE;
}

}  // namespace

extern "C" JNIEXPORT jlongArray JNICALL
Java_com_esanacore_lightkeeper_NativeRules_nativeReadBody(JNIEnv* env, jclass, jbyteArray body) {
  lk::JsonResult result;
  if (body == nullptr) {
    result = lk::newest_reading_from_json(nullptr, 0);
  } else {
    const jsize length = env->GetArrayLength(body);
    jbyte* bytes = env->GetByteArrayElements(body, nullptr);
    if (bytes == nullptr) return nullptr;
    result = lk::newest_reading_from_json(reinterpret_cast<const char*>(bytes),
                                          static_cast<size_t>(length));
    env->ReleaseByteArrayElements(body, bytes, JNI_ABORT);
  }

  jlong fields[kBodyFieldCount] = {};
  fields[kStatus] = status_code(result.status);
  fields[kFound] = result.found ? 1 : 0;
  fields[kMgdl] = result.reading.mgdl;
  fields[kTimestamp] = result.reading.timestamp_ms;
  fields[kTrend] = trend_code(result.reading.trend);
  fields[kEntriesSeen] = result.entries_seen;

  jlongArray out = env->NewLongArray(kBodyFieldCount);
  if (out == nullptr) return nullptr;
  env->SetLongArrayRegion(out, 0, kBodyFieldCount, fields);
  return out;
}

extern "C" JNIEXPORT jobjectArray JNICALL
Java_com_esanacore_lightkeeper_NativeRules_nativeRenderLines(
    JNIEnv* env, jclass, jboolean has_reading, jint mgdl, jlong timestamp_ms, jint trend,
    jlong now_ms, jlong stale_after_ms, jint urgent_low, jint low, jint high, jint urgent_high,
    jboolean fetch_error) {
  lk::Thresholds thresholds;
  thresholds.urgent_low = urgent_low;
  thresholds.low = low;
  thresholds.high = high;
  thresholds.urgent_high = urgent_high;
  thresholds.stale_after_ms = stale_after_ms;

  // The reading is checked again, by the parser's own rule, before it is
  // trusted: Kotlin only ever holds what nativeReadBody returned, but a
  // value outside the sensor range or the plausible dates shows NO DATA.
  lk::Reading reading;
  bool usable = false;
  if (has_reading == JNI_TRUE) {
    lk::RawEntry raw;
    raw.has_sgv = true;
    raw.sgv = static_cast<double>(mgdl);
    raw.has_date = true;
    raw.date_ms = static_cast<double>(timestamp_ms);
    usable = lk::parse_entry(raw, &reading);
    reading.trend = trend_from_code(trend);
  }

  // Invalid thresholds classify as NO DATA (glucose_rules): a number is never
  // judged against limits that could hide a low.
  const lk::Status status = lk::classify(usable ? &reading : nullptr, now_ms, thresholds);
  lk::Lines lines;
  lk::render(status, fetch_error == JNI_TRUE, &lines);
  return to_java_lines(env, lines);
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_esanacore_lightkeeper_NativeRules_nativeRenderPanel(JNIEnv* env, jclass,
                                                             jobjectArray lines, jint width,
                                                             jint height, jstring stamp) {
  if (lines == nullptr) return nullptr;
  const jsize count = env->GetArrayLength(lines);
  if (count < 1 || count > lk::kMaxPanelLines) return nullptr;
  // Checked before packed_size, whose arithmetic assumes a sane side.
  if (width < 1 || height < 1 || width > lk::kMaxSide || height > lk::kMaxSide) return nullptr;

  char text[lk::kMaxPanelLines][lk::kMaxPanelLineChars + 1] = {};
  const char* pointers[lk::kMaxPanelLines] = {};
  for (jsize i = 0; i < count; i++) {
    jstring line = static_cast<jstring>(env->GetObjectArrayElement(lines, i));
    const bool copied = copy_string(env, line, text[i], sizeof(text[i]));
    if (line != nullptr) env->DeleteLocalRef(line);
    if (!copied) return nullptr;
    pointers[i] = text[i];
  }
  // "HH:MM" and its null fit; anything longer is a bad stamp, refused.
  char stamp_text[8] = {};
  if (stamp != nullptr && !copy_string(env, stamp, stamp_text, sizeof(stamp_text))) {
    return nullptr;
  }

  // The image is drawn straight into the Java array: no heap of our own.
  const size_t size = lk::packed_size(width, height);
  jbyteArray out = env->NewByteArray(static_cast<jsize>(size));
  if (out == nullptr) return nullptr;
  jbyte* rows = env->GetByteArrayElements(out, nullptr);
  if (rows == nullptr) return nullptr;
  const bool drawn = lk::render_panel(pointers, static_cast<int>(count), width, height,
                                      stamp == nullptr ? nullptr : stamp_text,
                                      reinterpret_cast<uint8_t*>(rows), size);
  env->ReleaseByteArrayElements(out, rows, drawn ? 0 : JNI_ABORT);
  if (!drawn) {
    env->DeleteLocalRef(out);
    return nullptr;
  }
  return out;
}
