// serial_panel: the lo-fi bench "driver". Until the e-paper driver lands
// (L-08), the device prints its screen over USB serial instead of drawing it:
// the display lines as text, then the panel image as rows of '#' (ink) and
// '.' (paper), with its CRC-32 and ink count so a bench reading can be
// compared with the case spec/panel_vectors.json pins for that screen and
// size. ASCII only, one dump per wake, nothing animated.
//
// Plain C++, no Arduino: src/main.cpp hands print_panel a function that
// prints to Serial, and the host tests (test/host/test_panel_bitmap.cpp)
// build this file with a recorder in its place, read the rows back and
// compare them with the pinned case. The screen the skeleton shows is built
// here too, so the device and the tests run the same steps.

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "glucose_rules.h"

namespace lk {

// The screen while the device has no Wi-Fi and no clock, which is all the
// skeleton has: no response body, so the JSON layer reports an error and
// finds no reading, and glucose_rules says NO DATA (Nightscout unreachable),
// never a number. Fills *lines, then draws them on a width x height panel
// into `buffer` by render_panel's rules. Returns false when render_panel
// refused; the buffer is then untouched and nothing must be shown as drawn.
bool draw_offline_screen(int width, int height, Lines* lines, uint8_t* buffer, size_t buffer_size);

// Where print_panel sends each line of text, without the line ending (on the
// device, Serial.println).
using PrintLine = void (*)(const char* line);

// Print the display lines, then the `width` x `height` packed rows that
// lk::render_panel wrote (1 = ink, most significant bit first) as '#'/'.'
// text, one row a line. `rows` is nullptr when nothing was drawn, and an
// empty, short or wider-than-any-profile image is refused: either way it
// says so in words and prints no rows.
void print_panel(PrintLine print_line, const Lines& lines, const uint8_t* rows, size_t rows_size,
                 int width, int height);

}  // namespace lk
