// device_config: the two boards the device skeleton builds for, and which one
// this build is. platformio.ini defines LK_BOARD_BENCH_S3 or LK_BOARD_X4.
//
// Every value marked VERIFY is a placeholder until someone checks it on the
// bench against the board's schematic. Nothing drives a panel yet (the
// e-paper driver is the next device step, L-08), so no pin is used: each one
// is kPinUnset, and the driver must not use any pin while kPinsVerified is
// false. The host tests hold the file to that, and check that each panel size
// is one spec/panel_vectors.json pins.
//
// Plain constants: no Arduino and no secrets. The Nightscout URL and token
// never go in source; when networking lands they live in NVS and the token
// travels only in the api-secret header (ADR-0009).

#pragma once

#include <stdint.h>

namespace lk {

constexpr int kPinUnset = -1;

// VERIFY: set true only once every pin below is checked on the bench.
constexpr bool kPinsVerified = false;

struct BoardConfig {
  const char* name;  // the PlatformIO environment
  // The panel in the orientation the lines read; a pinned profile, so the
  // image is the one every other display draws.
  int panel_width;
  int panel_height;
  // The e-paper panel's SPI bus and control lines, and the GPIO that powers
  // it where the board switches it (kPinUnset where it has none).
  int pin_epd_sck;
  int pin_epd_mosi;
  int pin_epd_cs;
  int pin_epd_dc;
  int pin_epd_rst;
  int pin_epd_busy;
  int pin_epd_power;
};

// The bench board: Waveshare ESP32-S3-ePaper-1.54, 200x200 black and white
// (docs/HARDWARE.md). Pins: VERIFY against the Waveshare wiki schematic.
constexpr BoardConfig kBenchS3 = {
    "bench_s3",
    200,        // VERIFY: panel width
    200,        // VERIFY: panel height
    kPinUnset,  // VERIFY: SCK
    kPinUnset,  // VERIFY: MOSI
    kPinUnset,  // VERIFY: CS
    kPinUnset,  // VERIFY: DC
    kPinUnset,  // VERIFY: RST
    kPinUnset,  // VERIFY: BUSY
    kPinUnset,  // VERIFY: panel power enable
};

// The pocket display: Xteink X4 (ESP32-C3), 4.3" e-ink. The size is the
// pinned 800x480 profile, read in landscape; VERIFY the panel's resolution
// and controller on the bench (D11). Pins: VERIFY against the X4 board.
constexpr BoardConfig kX4 = {
    "x4",
    800,        // VERIFY: panel width
    480,        // VERIFY: panel height
    kPinUnset,  // VERIFY: SCK
    kPinUnset,  // VERIFY: MOSI
    kPinUnset,  // VERIFY: CS
    kPinUnset,  // VERIFY: DC
    kPinUnset,  // VERIFY: RST
    kPinUnset,  // VERIFY: BUSY
    kPinUnset,  // VERIFY: panel power enable
};

#if defined(LK_BOARD_BENCH_S3)
constexpr BoardConfig kBoard = kBenchS3;
#elif defined(LK_BOARD_X4)
constexpr BoardConfig kBoard = kX4;
#endif

// Serial is the board's native USB port (ARDUINO_USB_CDC_ON_BOOT in
// platformio.ini, VERIFY on both boards); USB ignores the baud rate, a UART
// bridge uses it.
constexpr unsigned long kSerialBaud = 115200;
// How long to wait for a serial monitor before printing anyway.
constexpr uint32_t kSerialWaitMs = 2000;
// Deep sleep between wakes. Each wake starts again from setup().
constexpr uint64_t kSleepSeconds = 60;

}  // namespace lk
