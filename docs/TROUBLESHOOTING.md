# Troubleshooting

Known issues and fixes. If a display ever shows something that disagrees with the primary CGM app, trust the primary app first, then debug.

## Common Issues

### The display says STALE - DO NOT TRUST

- **Symptom**: The first line is STALE and the age keeps growing.
- **Cause**: Nightscout has not received a reading in more than 15 minutes (or `LK_STALE_MINUTES`). Usually the phone lost Bluetooth to the sensor, Trio is not running in the background, the phone is offline, or the sensor is warming up.
- **Solution**: Check the Dexcom G7 app and Trio on the primary phone first, then the Nightscout site in a browser. The display is doing its job; it recovers on its own when fresh data arrives.

### The display says "time is in the future"

- **Symptom**: STALE with "time is in the future".
- **Cause**: A clock is wrong on the phone, the Nightscout server, or the display device.
- **Solution**: Turn on automatic network time on every device. On a Raspberry Pi, check `timedatectl`.

### NO DATA with "Nightscout unreachable"

- **Symptom**: The program can't reach Nightscout at all and has no earlier reading.
- **Cause**: Wrong `NIGHTSCOUT_URL`, DNS or network failure, the site is down, or the token is wrong or lacks the `readable` role.
- **Solution**: Open the URL in a browser from the same device. Re-create the token in Nightscout's admin tools if needed. Error messages never print the token, so it is safe to share them.

### Configuration error on startup

- **Symptom**: Exit code 2 with "must use https", "invalid threshold settings", or an `LK_MQTT_*` message.
- **Cause**: An `http://` URL, thresholds that are out of order, `LK_MQTT_TLS` that is not true or false, plain MQTT to a broker that is not on localhost, or an `LK_MQTT_NODE_ID` with characters other than letters, digits, `_`, and `-`.
- **Solution**: Use the HTTPS URL. Check thresholds and MQTT settings against `docs/ENV_VARS.md`; turn TLS on for a remote broker.

### "Home Assistant publish failed" in the log

- **Symptom**: The display keeps working, and each cycle logs "Home Assistant publish failed: ...".
- **Cause**: The broker is unreachable, refuses the user or password, or does not trust the TLS setup. The password never appears in the message.
- **Solution**: Check `LK_MQTT_HOST`, `LK_MQTT_PORT` (8883 with TLS), the broker user, and its ACL. Lightkeeper reconnects on the next cycle by itself.

### Home Assistant shows the Lightkeeper sensors as unavailable

- **Symptom**: The three sensors read `unavailable`.
- **Cause**: The designed behavior when the publisher stops (HAZ-013): the broker published the Last Will, or no update arrived within `expire_after` (three refresh intervals, capped at the stale limit), or the service was stopped cleanly.
- **Solution**: Check the display device: `systemctl status lightkeeper` and `journalctl -u lightkeeper -f`. The sensors return on the next successful publish.

## Environment Reset

```bash
deactivate 2>/dev/null; rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git submodule update --init --recursive
```

On Windows, remove `.venv` with `Remove-Item -Recurse -Force .venv` and activate with `.\.venv\Scripts\Activate.ps1`.
