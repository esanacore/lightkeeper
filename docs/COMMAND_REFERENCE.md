# Command Reference

Common commands for this repository. Commands are the same on every platform once the virtual environment is active (`docs/SETUP.md`).

## Development

- `pip install -e ".[dev]"`: install the package in editable mode with test tools.
- `python -m glucose_watch --demo`: run with canned data, no network.
- `python -m glucose_watch --demo --demo-mgdl 62 --demo-minutes-ago 2`: try a specific simulated reading.
- `python -m glucose_watch`: read once from Nightscout (needs `NIGHTSCOUT_URL`), exit 0 if fresh and in range, 1 if someone should look, 2 on a configuration error.
- `python -m glucose_watch --watch --interval 60`: refresh until Ctrl+C (minimum 15 seconds).

## Testing

- `python -m pytest --cov`: full suite with the 90% coverage floor.
- `python -m pytest --cov --cov-report=term-missing`: show uncovered lines.
- `python -m pytest -k fr003`: everything verifying one requirement.

## Linting & Formatting

- `pre-commit install` once, then `pre-commit run --all-files`: whitespace, YAML/JSON syntax, merge markers, large files, and private-key detection.

## Operations

- `bash constitution/scripts/check_compliance.sh --product .`: constitution document check.
- `bash constitution/scripts/run_declared_tests.sh .`: run the suite exactly as CI does.
- `bash constitution/scripts/check_secrets.sh .`: scan for committed secrets.
- `git submodule update --remote constitution`: pull the latest constitution, then follow `constitution/INTEGRATION.md`.
