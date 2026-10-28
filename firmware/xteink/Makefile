# Host tests for the firmware safety rules and the panel rasterizer. Needs a
# C++17 compiler and Python 3.
#   make test          build and run the three suites with AddressSanitizer + UBSan
#   make format-check  confirm the C++ matches .clang-format
#   make coverage      line and branch coverage of the libraries (gcov)
#   make font-header   regenerate lib/panel_bitmap/font5x8_data.h from spec/font5x8.json
#   make clean
#
# On Windows, run in WSL (`wsl -- make -C firmware/xteink test`): MinGW
# toolchains cannot link the sanitizers. src/main.cpp is the device sketch
# (Arduino, PlatformIO only: `pio run`, see README.md); nothing here compiles
# it. The panel test does build src/serial_panel.cpp, the skeleton's screen and
# serial dump, which is plain C++, and reads src/device_config.h, which is
# plain constants.

CXX ?= g++
PYTHON ?= python3
BUILD := build
VECTORS := ../../spec/display_vectors.json
RESPONSES := ../../spec/response_vectors.json
PANEL_VECTORS := ../../spec/panel_vectors.json
# gen_panel_vectors.py also draws cases the spec does not pin with the Python
# reference, so a change there regenerates the panel include too.
PANEL_REFERENCE := $(wildcard ../../src/lightkeeper/infrastructure/panel_*.py \
                     ../../src/lightkeeper/infrastructure/epaper_bitmap.py \
                     ../../src/lightkeeper/infrastructure/font5x7.py)
INCLUDES := -Ilib/glucose_rules -Ilib/nightscout_json -Ilib/panel_bitmap -I$(BUILD)
CXXFLAGS := -std=c++17 -Wall -Wextra -Werror -Wconversion -Wshadow -g \
            -fsanitize=address,undefined -fno-sanitize-recover=all $(INCLUDES)
RULES := lib/glucose_rules/glucose_rules.cpp
JSON := lib/nightscout_json/nightscout_json.cpp
PANEL := lib/panel_bitmap/panel_bitmap.cpp
SERIAL_PANEL := src/serial_panel.cpp
# Every header the panel test reaches: the rasterizer's, the two libraries the
# skeleton's screen comes from, and the skeleton's own.
PANEL_HEADERS := lib/panel_bitmap/panel_bitmap.h lib/panel_bitmap/font5x8_data.h \
                 lib/glucose_rules/glucose_rules.h lib/nightscout_json/nightscout_json.h \
                 src/device_config.h src/serial_panel.h

.PHONY: test format-check coverage clean font-header panel-lint

$(BUILD)/vectors.inc: $(VECTORS) tools/gen_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_vectors.py $(VECTORS) $@

$(BUILD)/response_vectors.inc: $(RESPONSES) tools/gen_response_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_response_vectors.py $(RESPONSES) $@

$(BUILD)/panel_vectors.inc: $(PANEL_VECTORS) tools/gen_panel_vectors.py $(PANEL_REFERENCE)
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_panel_vectors.py $(PANEL_VECTORS) $@

$(BUILD)/host_tests: $(RULES) lib/glucose_rules/glucose_rules.h test/host/test_glucose_rules.cpp $(BUILD)/vectors.inc
	$(CXX) $(CXXFLAGS) $(RULES) test/host/test_glucose_rules.cpp -o $@

$(BUILD)/json_tests: $(RULES) $(JSON) lib/glucose_rules/glucose_rules.h lib/nightscout_json/nightscout_json.h test/host/test_nightscout_json.cpp $(BUILD)/response_vectors.inc
	$(CXX) $(CXXFLAGS) $(RULES) $(JSON) test/host/test_nightscout_json.cpp -o $@

$(BUILD)/panel_tests: $(RULES) $(JSON) $(PANEL) $(SERIAL_PANEL) $(PANEL_HEADERS) test/host/test_panel_bitmap.cpp $(BUILD)/panel_vectors.inc
	$(CXX) $(CXXFLAGS) $(RULES) $(JSON) $(PANEL) $(SERIAL_PANEL) test/host/test_panel_bitmap.cpp -o $@

# The rasterizer is integers only and never touches the heap: fail on any
# floating-point type or allocation call in its sources, comments included.
panel-lint:
	@if grep -nwE 'float|double|new|delete|malloc|calloc|realloc|free' lib/panel_bitmap/*; then \
	  echo "lib/panel_bitmap must stay integer-only and heap-free"; exit 1; \
	else echo "panel_bitmap: no float, double, new or malloc"; fi
	@$(PYTHON) tools/gen_font_header.py --check

test: panel-lint $(BUILD)/host_tests $(BUILD)/json_tests $(BUILD)/panel_tests
	./$(BUILD)/host_tests
	./$(BUILD)/json_tests
	./$(BUILD)/panel_tests $(BUILD)

font-header:
	$(PYTHON) tools/gen_font_header.py

# Fails if any C++ file differs from .clang-format. Skips with a warning when
# clang-format isn't installed, so a missing linter never blocks the tests.
format-check:
	@if command -v clang-format >/dev/null 2>&1; then \
	  clang-format --dry-run --Werror lib/*/*.h lib/*/*.cpp test/host/*.cpp src/*.h src/*.cpp && echo "clang-format: OK"; \
	else echo "clang-format not installed; skipping format check"; fi

# Coverage build: no sanitizers (they distort counts), -O0 so lines map 1:1.
# Prints gcov's summary for each library and src/serial_panel.cpp; the
# annotated sources land in $(BUILD)/coverage/. Needs gcc's gcov (Linux, WSL).
coverage: $(BUILD)/vectors.inc $(BUILD)/response_vectors.inc $(BUILD)/panel_vectors.inc
	mkdir -p $(BUILD)/coverage
	$(CXX) -std=c++17 -O0 --coverage $(INCLUDES) \
	  $(RULES) test/host/test_glucose_rules.cpp -o $(BUILD)/coverage/host_tests
	$(CXX) -std=c++17 -O0 --coverage $(INCLUDES) \
	  $(RULES) $(JSON) test/host/test_nightscout_json.cpp -o $(BUILD)/coverage/json_tests
	$(CXX) -std=c++17 -O0 --coverage $(INCLUDES) \
	  $(RULES) $(JSON) $(PANEL) $(SERIAL_PANEL) test/host/test_panel_bitmap.cpp \
	  -o $(BUILD)/coverage/panel_tests
	./$(BUILD)/coverage/host_tests
	./$(BUILD)/coverage/json_tests
	./$(BUILD)/coverage/panel_tests $(BUILD)
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/host_tests-glucose_rules.gcda \
	  | sed -n "/glucose_rules.cpp'/,/^$$/p"
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/json_tests-nightscout_json.gcda \
	  | sed -n "/nightscout_json.cpp'/,/^$$/p"
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/panel_tests-panel_bitmap.gcda \
	  | sed -n "/panel_bitmap.cpp'/,/^$$/p"
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/panel_tests-serial_panel.gcda \
	  | sed -n "/serial_panel.cpp'/,/^$$/p"
	mv -f *.gcov $(BUILD)/coverage/

clean:
	rm -rf $(BUILD)
