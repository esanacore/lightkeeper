# Troubleshooting

Known issues and fixes. If a display ever shows something that disagrees with the primary CGM app, trust the primary app first, then debug.

## Common Issues

### The display says STALE - DO NOT TRUST

- **Symptom**: The first line is STALE and the age keeps growing.
- **Cause**: Nightscout has not received a reading in more than 15 minutes (or `LK_STALE_MINUTES`). Usually the phone lost Bluetooth to the sensor, Trio is not running in the background, the phone is offline, or the sensor is warming up.
- **Solution**: Check the Dexcom G7 app and Trio on Kaitlin's phone first, then the Nightscout site in a browser. The display is doing its job; it recovers on its own when fresh data arrives.

### The display says "time is in the future"

- **Symptom**: STALE with "time is in the future".
- **Cause**: A clock is wrong on the phone, the Nightscout server, or the display device.
- **Solution**: Turn on automatic network time on every device. On a Raspberry Pi, check `timedatectl`.

### NO DATA with "Nightscout unreachable"

- **Symptom**: The program can't reach Nightscout at all and has no earlier reading.
- **Cause**: Wrong `NIGHTSCOUT_URL`, DNS or network failure, the site is down, or the token is wrong or lacks the `readable` role.
- **Solution**: Open the URL in a browser from the same device. Re-create the token in Nightscout's admin tools if needed. Error messages never print the token, so it is safe to share them.

### Configuration error on startup

- **Symptom**: Exit code 2 with "must use https" or "invalid threshold settings".
- **Cause**: An `http://` URL, or thresholds that are out of order.
- **Solution**: Use the HTTPS URL. Check thresholds against `docs/ENV_VARS.md`.

## Environment Reset

```bash
deactivate 2>/dev/null; rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git submodule update --init --recursive
```

On Windows, remove `.venv` with `Remove-Item -Recurse -Force .venv` and activate with `.\.venv\Scripts\Activate.ps1`.
