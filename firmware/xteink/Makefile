# Host tests for the firmware safety rules. Needs a C++17 compiler and Python 3.
#   make test          build and run both suites with AddressSanitizer + UBSan
#   make format-check  confirm the C++ matches .clang-format
#   make coverage      line and branch coverage of the libraries (gcov)
#   make clean
#
# On Windows, run in WSL (`wsl -- make -C firmware/xteink test`): MinGW
# toolchains cannot link the sanitizers. The PlatformIO "native" environment
# is another option once the device project is added.

CXX ?= g++
PYTHON ?= python3
BUILD := build
VECTORS := ../../spec/display_vectors.json
RESPONSES := ../../spec/response_vectors.json
INCLUDES := -Ilib/glucose_rules -Ilib/nightscout_json -I$(BUILD)
CXXFLAGS := -std=c++17 -Wall -Wextra -Werror -Wconversion -Wshadow -g \
            -fsanitize=address,undefined -fno-sanitize-recover=all $(INCLUDES)
RULES := lib/glucose_rules/glucose_rules.cpp
JSON := lib/nightscout_json/nightscout_json.cpp

.PHONY: test format-check coverage clean

$(BUILD)/vectors.inc: $(VECTORS) tools/gen_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_vectors.py $(VECTORS) $@

$(BUILD)/response_vectors.inc: $(RESPONSES) tools/gen_response_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_response_vectors.py $(RESPONSES) $@

$(BUILD)/host_tests: $(RULES) lib/glucose_rules/glucose_rules.h test/host/test_glucose_rules.cpp $(BUILD)/vectors.inc
	$(CXX) $(CXXFLAGS) $(RULES) test/host/test_glucose_rules.cpp -o $@

$(BUILD)/json_tests: $(RULES) $(JSON) lib/nightscout_json/nightscout_json.h test/host/test_nightscout_json.cpp $(BUILD)/response_vectors.inc
	$(CXX) $(CXXFLAGS) $(RULES) $(JSON) test/host/test_nightscout_json.cpp -o $@

test: $(BUILD)/host_tests $(BUILD)/json_tests
	./$(BUILD)/host_tests
	./$(BUILD)/json_tests

# Fails if any C++ file differs from .clang-format. Skips with a warning when
# clang-format isn't installed, so a missing linter never blocks the tests.
format-check:
	@if command -v clang-format >/dev/null 2>&1; then \
	  clang-format --dry-run --Werror lib/*/*.h lib/*/*.cpp test/host/*.cpp && echo "clang-format: OK"; \
	else echo "clang-format not installed; skipping format check"; fi

# Coverage build: no sanitizers (they distort counts), -O0 so lines map 1:1.
# Prints gcov's summary for each library; the annotated sources land in
# $(BUILD)/coverage/. Needs gcc's gcov (Linux, WSL).
coverage: $(BUILD)/vectors.inc $(BUILD)/response_vectors.inc
	mkdir -p $(BUILD)/coverage
	$(CXX) -std=c++17 -O0 --coverage $(INCLUDES) \
	  $(RULES) test/host/test_glucose_rules.cpp -o $(BUILD)/coverage/host_tests
	$(CXX) -std=c++17 -O0 --coverage $(INCLUDES) \
	  $(RULES) $(JSON) test/host/test_nightscout_json.cpp -o $(BUILD)/coverage/json_tests
	./$(BUILD)/coverage/host_tests
	./$(BUILD)/coverage/json_tests
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/host_tests-glucose_rules.gcda \
	  | sed -n "/glucose_rules.cpp'/,/^$$/p"
	gcov -b -c -o $(BUILD)/coverage $(BUILD)/coverage/json_tests-nightscout_json.gcda \
	  | sed -n "/nightscout_json.cpp'/,/^$$/p"
	mv -f *.gcov $(BUILD)/coverage/

clean:
	rm -rf $(BUILD)
