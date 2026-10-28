// serial_panel: the lo-fi bench "driver". Until the e-paper driver lands
// (L-08), the device prints its screen over USB serial instead of drawing it:
// the display lines as text, then the panel image as rows of '#' (ink) and
// '.' (paper), with its CRC-32 and ink count so a bench reading can be
// compared with the case spec/panel_vectors.json pins for that screen and
// size. ASCII only, one dump per wake, nothing animated.

#pragma once

#include <Print.h>
#include <stddef.h>
#include <stdint.h>

namespace lk {

// Print `count` display lines, then the `width` x `height` packed rows that
// lk::render_panel wrote (1 = ink, most significant bit first). `rows` is
// nullptr when nothing was drawn, and a short or oversized image is refused:
// either way it says so in words and prints no rows.
void print_panel(Print& out, const char* const* lines, int count, const uint8_t* rows,
                 size_t rows_size, int width, int height);

}  // namespace lk
