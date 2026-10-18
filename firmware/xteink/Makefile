# Host tests for the firmware safety rules. Needs a C++17 compiler and Python 3.
#   make test          build and run with AddressSanitizer + UBSan
#   make format-check  confirm the C++ matches .clang-format
#   make clean
#
# On Windows, run from Git Bash or WSL with g++ and make installed, or use
# the PlatformIO "native" environment once the device project is added.

CXX ?= g++
PYTHON ?= python3
BUILD := build
VECTORS := ../../spec/display_vectors.json
CXXFLAGS := -std=c++17 -Wall -Wextra -Werror -Wconversion -Wshadow -g \
            -fsanitize=address,undefined -fno-sanitize-recover=all \
            -Ilib/glucose_rules -I$(BUILD)

.PHONY: test format-check clean

$(BUILD)/vectors.inc: $(VECTORS) tools/gen_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_vectors.py $(VECTORS) $@

$(BUILD)/host_tests: lib/glucose_rules/glucose_rules.cpp lib/glucose_rules/glucose_rules.h test/host/test_glucose_rules.cpp $(BUILD)/vectors.inc
	$(CXX) $(CXXFLAGS) lib/glucose_rules/glucose_rules.cpp test/host/test_glucose_rules.cpp -o $@

test: $(BUILD)/host_tests
	./$(BUILD)/host_tests

# Fails if any C++ file differs from .clang-format. Skips with a warning when
# clang-format isn't installed, so a missing linter never blocks the tests.
format-check:
	@if command -v clang-format >/dev/null 2>&1; then \
	  clang-format --dry-run --Werror lib/glucose_rules/*.h lib/glucose_rules/*.cpp test/host/*.cpp && echo "clang-format: OK"; \
	else echo "clang-format not installed; skipping format check"; fi

clean:
	rm -rf $(BUILD)
