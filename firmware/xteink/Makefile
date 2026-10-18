# Host tests for the firmware safety rules. Needs a C++17 compiler and Python 3.
#   make test     build and run with AddressSanitizer + UBSan
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

.PHONY: test clean

$(BUILD)/vectors.inc: $(VECTORS) tools/gen_vectors.py
	mkdir -p $(BUILD)
	$(PYTHON) tools/gen_vectors.py $(VECTORS) $@

$(BUILD)/host_tests: lib/glucose_rules/glucose_rules.cpp lib/glucose_rules/glucose_rules.h test/host/test_glucose_rules.cpp $(BUILD)/vectors.inc
	$(CXX) $(CXXFLAGS) lib/glucose_rules/glucose_rules.cpp test/host/test_glucose_rules.cpp -o $@

test: $(BUILD)/host_tests
	./$(BUILD)/host_tests

clean:
	rm -rf $(BUILD)
