# Getting Started

Lightkeeper needs Python 3.11 or newer. Full per-platform steps (Windows, macOS, Linux and Raspberry Pi) are in `docs/SETUP.md` in the repository; this is the short version.

## Try it with no setup

Clone the repository with its submodule, install, and run the demo. Demo mode uses made-up readings and never touches the network.

```bash
git clone --recurse-submodules https://github.com/esanacore/lightkeeper
cd lightkeeper
pip install -e ".[dev]"
python -m lightkeeper --demo
python -m lightkeeper --demo --demo-minutes-ago 40   # see the STALE screen
```

Or open `demo.html` in a browser to click through every screen.

## Point it at Nightscout

Set `NIGHTSCOUT_URL` to your site (HTTPS only) and `NIGHTSCOUT_TOKEN` to a token with the **readable** role. Never use the API_SECRET. Then run `python -m lightkeeper`, or add `--watch` to refresh every minute and `--svg screen.svg` to save each screen as an image. Every setting is listed in `docs/ENV_VARS.md`.

Before relying on any display, run it side by side with the primary app for a full sensor session. See [[Safety]].

Next: [[How It Works]].
