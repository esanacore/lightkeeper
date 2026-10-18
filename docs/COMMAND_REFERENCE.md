# Command Reference

Common commands for this repository. Commands are the same on every platform once the virtual environment is active (`docs/SETUP.md`).

## Development

- `python tools/doctor.py`: check every prerequisite and name what's missing.
- `pip install -e ".[dev]"`: install the package in editable mode with test tools.
- `python -m lightkeeper --demo`: run with canned data, no network.
- `python -m lightkeeper --demo --demo-mgdl 62 --demo-minutes-ago 2`: try a specific simulated reading.
- `python -m lightkeeper`: read once from Nightscout (needs `NIGHTSCOUT_URL`), exit 0 if fresh and in range, 1 if someone should look, 2 on a configuration error.
- `python -m lightkeeper --watch --interval 60`: refresh until Ctrl+C (minimum 15 seconds).

## Testing

- `python -m pytest --cov`: full suite with the 90% coverage floor.
- `python -m pytest --cov --cov-report=term-missing`: show uncovered lines.
- `python -m pytest -k fr003`: everything verifying one requirement.
- `make -C firmware/xteink test`: firmware host tests under AddressSanitizer and UBSan.
- `python tools/gen_display_gallery.py`: regenerate `docs/DISPLAY_STATES.md`, its images, and the demo's state table after changing `spec/display_vectors.json`.

## Linting & Formatting

- `python -m ruff check .` and `python -m ruff format .`: lint and format Python.
- `python -m mypy`: strict type checking of `src/`.
- `make -C firmware/xteink format-check`: confirm the C++ matches `.clang-format`.
- `pre-commit install && pre-commit install --hook-type pre-push` once, then `pre-commit run --all-files`: all of the above plus whitespace, YAML/JSON syntax, merge markers, large files, private-key detection, and the secrets sweep before push.

## Operations

- `bash constitution/scripts/check_compliance.sh --product .`: constitution document check.
- `bash constitution/scripts/run_declared_tests.sh .`: run the suite exactly as CI does.
- `bash constitution/scripts/check_secrets.sh .`: scan for committed secrets.
- `git submodule update --remote constitution`: pull the latest constitution, then follow `constitution/INTEGRATION.md`.
