# The app's native library: the firmware's own C++ rules, JSON reader and
# panel rasterizer, compiled in place from firmware/xteink/lib, plus the one
# JNI file the app owns. Nothing is copied: a change to the firmware libraries
# is a change to the app, and the instrumented tests run every shared vector
# against this build. tests/test_android.py checks that no copy of these
# sources appears under apps/android.

cmake_minimum_required(VERSION 3.22.1)
project(lightkeeper CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# apps/android/app/src/main/cpp -> the repository root.
get_filename_component(LK_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../.." ABSOLUTE)
set(LK_FIRMWARE_LIB "${LK_REPO_ROOT}/firmware/xteink/lib")
if(NOT EXISTS "${LK_FIRMWARE_LIB}/glucose_rules/glucose_rules.cpp")
  message(FATAL_ERROR "firmware libraries not found at ${LK_FIRMWARE_LIB}")
endif()

add_library(lightkeeper SHARED
  jni_bridge.cpp
  "${LK_FIRMWARE_LIB}/glucose_rules/glucose_rules.cpp"
  "${LK_FIRMWARE_LIB}/nightscout_json/nightscout_json.cpp"
  "${LK_FIRMWARE_LIB}/panel_bitmap/panel_bitmap.cpp"
)

target_include_directories(lightkeeper PRIVATE
  "${LK_FIRMWARE_LIB}/glucose_rules"
  "${LK_FIRMWARE_LIB}/nightscout_json"
  "${LK_FIRMWARE_LIB}/panel_bitmap"
)

# The firmware host tests' warning set; any warning stops the build.
target_compile_options(lightkeeper PRIVATE
  -Wall -Wextra -Werror -Wconversion -Wshadow
)

# Small, like the device build: the debug APK is the one people sideload, so
# its library is optimized for size whatever the build type (a later -O wins
# over the -O0 a debug build passes). The libraries use the C library only
# (build.gradle.kts sets ANDROID_STL=none), so no C++ runtime, exceptions or
# RTTI are linked in. Only the JNI entry points are exported.
target_compile_options(lightkeeper PRIVATE
  -Os -fno-exceptions -fno-rtti
  -fvisibility=hidden -ffunction-sections -fdata-sections
)
target_link_options(lightkeeper PRIVATE -Wl,--gc-sections)
