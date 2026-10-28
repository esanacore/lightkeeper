#include "serial_panel.h"

#include "panel_bitmap.h"

namespace lk {

namespace {

// The widest pinned profile: no device panel is wider, so one row of text
// fits a fixed buffer.
constexpr int widest_profile() {
  int most = 0;
  for (const PanelProfile& p : kPanelProfiles) most = p.width > most ? p.width : most;
  return most;
}
constexpr int kMaxDumpWidth = widest_profile();

char g_row[kMaxDumpWidth + 1];

}  // namespace

void print_panel(Print& out, const char* const* lines, int count, const uint8_t* rows,
                 size_t rows_size, int width, int height) {
  out.println("screen:");
  for (int i = 0; lines != nullptr && i < count; i++) {
    if (lines[i] != nullptr) out.println(lines[i]);
  }

  const size_t size = packed_size(width, height);
  if (rows == nullptr || size == 0 || width > kMaxDumpWidth || rows_size < size) {
    out.printf("panel %dx%d not drawn", width, height);
    out.println();
    return;
  }
  // The CRC-32 in decimal, as spec/panel_vectors.json writes it, and in hex.
  const unsigned long crc = crc32(rows, size);
  out.printf("panel %dx%d crc32 %lu (0x%08lx) ink %lu", width, height, crc, crc,
             static_cast<unsigned long>(ink_count(rows, size)));
  out.println();
  const int stride = (width + 7) / 8;
  for (int y = 0; y < height; y++) {
    const uint8_t* row = rows + y * stride;
    for (int x = 0; x < width; x++) g_row[x] = (row[x / 8] >> (7 - x % 8)) & 1 ? '#' : '.';
    g_row[width] = '\0';
    out.println(g_row);
  }
  out.println("end of panel");
}

}  // namespace lk
