// The Lightkeeper device skeleton for the bench ESP32-S3 and the Xteink X4.
//
// Build only for now. It has no Wi-Fi, no clock and no secrets, so it proves
// the safe default and nothing more: with no Nightscout body there is no
// reading, glucose_rules says NO DATA, and that screen (never a number) is
// rasterized by panel_bitmap and printed over USB serial as '#'/'.' rows
// (serial_panel). Nothing is drawn on a panel yet. Then it deep sleeps for a
// minute, and every wake starts again from setup().
//
// The libraries are the ones the host tests check (lib/), not copies, and
// test_fr010_device_skeleton_draws_the_pinned_no_data_screen runs the same
// steps on a PC for both boards.
//
// When networking lands (L-08): never setInsecure(), keep the token in NVS
// and send it only in the api-secret header (ADR-0009), and draw the stamp
// and a "not updating" screen before sleeping, because e-ink keeps its last
// image after the device stops.

#include <Arduino.h>
#include <esp_sleep.h>

#include "device_config.h"
#include "glucose_rules.h"
#include "nightscout_json.h"
#include "panel_bitmap.h"
#include "serial_panel.h"

#if !defined(LK_BOARD_BENCH_S3) && !defined(LK_BOARD_X4)
#error "build with -DLK_BOARD_BENCH_S3 or -DLK_BOARD_X4 (platformio.ini sets one per environment)"
#endif

namespace {

static_assert(lk::is_profile_size(lk::kBoard.panel_width, lk::kBoard.panel_height),
              "the panel must be a size spec/panel_vectors.json pins");
static_assert(lk::packed_size(lk::kBoard.panel_width, lk::kBoard.panel_height) <=
                  lk::kMaxPanelBytes,
              "the panel buffer holds the largest pinned profile");

// No clock yet. Without a reading, classify never reads the time; and if a
// reading ever got here, every plausible timestamp is decades after 0, so it
// would be future-dated and shown as STALE, never as current.
constexpr int64_t kNoClockMs = 0;

uint8_t g_panel[lk::kMaxPanelBytes];

}  // namespace

void setup() {
  Serial.begin(lk::kSerialBaud);
  const uint32_t start = millis();
  while (!Serial && millis() - start < lk::kSerialWaitMs) delay(10);

  // No Wi-Fi yet, so no response body: the JSON layer reports an error and
  // finds no reading, exactly as for a failed fetch.
  const lk::JsonResult fetched = lk::newest_reading_from_json(nullptr, 0);
  const bool fetch_error = fetched.status != lk::JsonStatus::Ok;
  const lk::Reading* reading = !fetch_error && fetched.found ? &fetched.reading : nullptr;
  const lk::Status status = lk::classify(reading, kNoClockMs, lk::Thresholds());
  lk::Lines lines;
  lk::render(status, fetch_error, &lines);

  const char* text[lk::kMaxLines] = {};
  for (int i = 0; i < lines.count; i++) text[i] = lines.text[i];
  const int width = lk::kBoard.panel_width;
  const int height = lk::kBoard.panel_height;
  const bool drawn =
      lk::render_panel(text, lines.count, width, height, nullptr, g_panel, sizeof(g_panel));

  Serial.printf("o))) lightkeeper %s: bench dump, nothing is drawn on a panel yet",
                lk::kBoard.name);
  Serial.println();
  lk::print_panel(Serial, text, lines.count, drawn ? g_panel : nullptr, sizeof(g_panel), width,
                  height);
  Serial.flush();

  esp_sleep_enable_timer_wakeup(lk::kSleepSeconds * 1000000ULL);
  esp_deep_sleep_start();
}

// Never reached: deep sleep ends in a reset, which runs setup() again.
void loop() {}
