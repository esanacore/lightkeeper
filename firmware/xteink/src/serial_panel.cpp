#include "serial_panel.h"

#include <stdio.h>

#include "nightscout_json.h"
#include "panel_bitmap.h"

namespace lk {

namespace {

// glucose_rules writes at most kMaxLines lines of kLineChars - 1 characters.
// Were it ever to write more than render_panel takes, the device would print
// "not drawn" on every wake; this stops the build instead.
static_assert(kMaxLines <= kMaxPanelLines && kLineChars - 1 <= kMaxPanelLineChars,
              "every screen glucose_rules writes is one render_panel accepts");

// No clock yet. Without a reading, classify never reads the time; and if a
// reading ever got here, every plausible timestamp is decades after 0, so it
// would be future-dated and shown as STALE, never as current.
constexpr int64_t kNoClockMs = 0;

// The widest pinned profile: no device panel is wider, so one row of text
// fits a fixed buffer.
constexpr int widest_profile() {
  int most = 0;
  for (const PanelProfile& p : kPanelProfiles) most = p.width > most ? p.width : most;
  return most;
}
constexpr int kMaxDumpWidth = widest_profile();

char g_text[kMaxDumpWidth + 1];

}  // namespace

bool draw_offline_screen(int width, int height, Lines* lines, uint8_t* buffer, size_t buffer_size) {
  // No Wi-Fi yet, so no response body: the JSON layer reports an error and
  // finds no reading, exactly as for a failed fetch.
  const JsonResult fetched = newest_reading_from_json(nullptr, 0);
  const bool fetch_error = fetched.status != JsonStatus::Ok;
  const Reading* reading = !fetch_error && fetched.found ? &fetched.reading : nullptr;
  const Status status = classify(reading, kNoClockMs, Thresholds());
  render(status, fetch_error, lines);

  const char* text[kMaxLines] = {};
  for (int i = 0; i < lines->count; i++) text[i] = lines->text[i];
  return render_panel(text, lines->count, width, height, nullptr, buffer, buffer_size);
}

void print_panel(PrintLine print_line, const Lines& lines, const uint8_t* rows, size_t rows_size,
                 int width, int height) {
  print_line("screen:");
  for (int i = 0; i < lines.count && i < kMaxLines; i++) print_line(lines.text[i]);

  const size_t size = packed_size(width, height);
  if (rows == nullptr || size == 0 || width > kMaxDumpWidth || rows_size < size) {
    snprintf(g_text, sizeof(g_text), "panel %dx%d not drawn", width, height);
    print_line(g_text);
    return;
  }
  // The CRC-32 in decimal, as spec/panel_vectors.json writes it, and in hex.
  const unsigned long crc = crc32(rows, size);
  snprintf(g_text, sizeof(g_text), "panel %dx%d crc32 %lu (0x%08lx) ink %lu", width, height, crc,
           crc, static_cast<unsigned long>(ink_count(rows, size)));
  print_line(g_text);
  const int stride = (width + 7) / 8;
  for (int y = 0; y < height; y++) {
    const uint8_t* row = rows + y * stride;
    for (int x = 0; x < width; x++) g_text[x] = (row[x / 8] >> (7 - x % 8)) & 1 ? '#' : '.';
    g_text[width] = '\0';
    print_line(g_text);
  }
  print_line("end of panel");
}

}  // namespace lk
