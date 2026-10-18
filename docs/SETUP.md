# Setup

Everything needed to reproduce the Lightkeeper stack from scratch, in the order to do it. Part 1 is the developer workstation. Part 2 is the therapy half (Nightscout, Trio), which belongs to the person with diabetes and their care team; we link to the community docs for those steps because they change often, and note only our own choices. Part 3 is each Lightkeeper display. Part 4 is the iOS app.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.

## Part 1: Developer workstation

### IDE Setup

This project follows Eric's Engineering Constitution. Open the repository in VS Code, Visual Studio, a JetBrains IDE, or Claude Code from the project folder; the committed instruction files (`AGENTS.md`, `CLAUDE.md`) apply the constitution automatically. After cloning, run `git submodule update --init --recursive` so `constitution/` is present. See `docs/HELP.md` and `constitution/INTEGRATION.md`.

### Supported Platforms

- Windows: Windows 11, PowerShell 7
- macOS: macOS 14+ (optional; Trio and the iOS app build in the cloud, so no Mac is needed)
- Linux: Ubuntu 22.04+ and Raspberry Pi OS Bookworm (display builds)
- CI runs on Ubuntu (Python, firmware, governance) and macOS (iOS).

### Prerequisites

Python 3.11 or newer, Git, and for the firmware host tests a C++17 compiler and make.

<details>
<summary>Windows (PowerShell)</summary>

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
# Firmware host tests need g++ and make: install MSYS2 or use WSL (Ubuntu) for that part.
winget install --id MSYS2.MSYS2 -e
```

</details>

<details>
<summary>macOS (zsh)</summary>

```bash
brew install python@3.12 git
xcode-select --install   # provides clang++ and make
```

</details>

<details>
<summary>Linux / Raspberry Pi (bash)</summary>

```bash
sudo apt update && sudo apt install -y python3 python3-venv git g++ make clang-format
```

</details>

### Verify Prerequisites

```bash
python tools/doctor.py   # use python3 on macOS/Linux
```

It checks Python 3.11+, the constitution submodule, the test and lint tools, and the C++ toolchain, and names exactly what's missing. Run it again after installing (next step) to confirm the dev tools.

### Installation

```bash
git clone --recurse-submodules https://github.com/esanacore/lightkeeper
cd lightkeeper
```

<details>
<summary>Windows (PowerShell)</summary>

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]" pre-commit
pre-commit install; pre-commit install --hook-type pre-push
```

</details>

<details>
<summary>macOS / Linux (bash or zsh)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" pre-commit
pre-commit install && pre-commit install --hook-type pre-push
```

</details>

### First Run

```bash
python -m lightkeeper --demo                 # IN RANGE with canned data
python -m lightkeeper --demo --demo-minutes-ago 40   # the STALE screen
python -m pytest --cov                       # 139 tests
make -C firmware/xteink test                 # firmware rules under sanitizers
```

### Environment Variables

There is no `.env` loader; set variables in your shell or service definition. `.env.example` lists them all with safe defaults, and `docs/ENV_VARS.md` describes each one.

<details>
<summary>Windows (PowerShell)</summary>

```powershell
$env:NIGHTSCOUT_URL = "https://ns.example.com"
$env:NIGHTSCOUT_TOKEN = Read-Host "Readable token"
python -m lightkeeper
```

</details>

<details>
<summary>macOS / Linux (bash or zsh)</summary>

```bash
export NIGHTSCOUT_URL="https://ns.example.com"
read -rs NIGHTSCOUT_TOKEN && export NIGHTSCOUT_TOKEN
python -m lightkeeper
```

</details>

## Part 2: The therapy half (Nightscout and Trio)

These steps are the person with diabetes's decisions, made with their care team. Phases and exit criteria are in `docs/ROADMAP.md`.

### Phase 1: Nightscout

Nightscout is the data hub every Lightkeeper display reads from. Host it somewhere the phone can reach from anywhere, which means a cloud VPS or a managed Nightscout host, not a machine at home.

1. Pick hosting. Options the community uses: a small VPS (any provider, 1 vCPU and 1 GB is enough) running the official Docker image behind a TLS proxy, or a managed host. Record the choice in a new ADR (`docs/adr/`).
2. Follow the official install guide at nightscout.github.io for the host you chose. Use the Docker Compose method on a VPS: it gives you Nightscout, MongoDB, and automatic HTTPS via a reverse proxy.
3. Security settings that are not optional for us: a long random `API_SECRET` (at least 24 characters, generated, never reused), `AUTH_DEFAULT_ROLES=denied` so nothing is public, and HTTPS only.
4. Create the read-only token: in Nightscout, open the hamburger menu, Admin Tools, Subjects, add a subject named `lightkeeper-displays` with the role `readable`. The token Nightscout shows is what every display uses as `NIGHTSCOUT_TOKEN`. Never put the `API_SECRET` on a display.
5. Backups: schedule a nightly `mongodump` to object storage and restore it once to a scratch instance to prove it works. Record the retention period in `docs/OPERATIONS.md`.
6. Verify from a workstation: `NIGHTSCOUT_URL=https://your-site NIGHTSCOUT_TOKEN=... python -m lightkeeper` should print NO DATA until an uploader exists, not a configuration error.

### Phase 2 and 3: Trio

Trio is the open source automated insulin delivery app that runs on the iPhone and talks to the pump. It is not Lightkeeper code. Read triodocs.org end to end first, and talk with the endocrinologist before starting.

Our specific choices:

- Build method: Trio's **browser build** (GitHub Actions to TestFlight). No Mac is needed. It requires a paid Apple Developer account (in place) and follows triodocs.org's "Build with Browser" guide exactly, including the GitHub secrets it asks for. Keep the fork's default branch on `main`.
- CGM: Dexcom G7 via the Dexcom G7 app on the same phone. Turn off iOS automatic app updates, and update the Dexcom app only after the Trio community confirms compatibility. The first G7 sensor session must start in the country of the App Store the Dexcom app came from.
- Pump: Omnipod 5 pods, supported on Trio's main branch since v1.0.0 (September 15, 2026). Switching steps are on the Omnipod 5 compatibility page at nightscout.github.io/omnipod-five. Keep a backup DASH pod for the first switch, do not fill a new pod until Trio shows the pairing screen, and have internet for the first pod's certificate step.
- Nightscout: enter the site URL and the `API_SECRET` in Trio so it can upload (Trio writes; displays only read).
- Open loop first. Trio only suggests for at least two weeks while settings are validated with the care team. Closed loop when ADR-0002's promotion criteria are met.
- Keep the official Omnipod 5 app or Controller as a fallback: pairing a fresh pod with it restores the stock algorithm.

## Part 3: Displays

Hardware is in `docs/HARDWARE.md`. Each display reads Nightscout with the readable token and nothing else.

### Bedside e-ink display (Raspberry Pi Zero 2 WH + 2.9" e-paper HAT)

1. Flash Raspberry Pi OS Lite (64-bit, Bookworm) with Raspberry Pi Imager. In the imager's settings set the hostname (`lightkeeper-bedside`), enable SSH, set a user, and enter the Wi-Fi.
2. Boot, SSH in, and enable SPI: `sudo raspi-config` → Interface Options → SPI → Yes. Reboot.
3. Install prerequisites and the project:

   ```bash
   sudo apt update && sudo apt install -y python3-venv git
   git clone --recurse-submodules https://github.com/esanacore/lightkeeper ~/lightkeeper
   cd ~/lightkeeper && python3 -m venv .venv && . .venv/bin/activate && pip install -e .
   ```

4. Put the settings in `/etc/lightkeeper.env` (root-only, since it holds the token):

   ```bash
   sudo install -m 600 /dev/null /etc/lightkeeper.env
   sudo tee /etc/lightkeeper.env >/dev/null <<'EOF'
   NIGHTSCOUT_URL=https://your-site.example
   NIGHTSCOUT_TOKEN=paste-the-readable-token
   LK_STALE_MINUTES=15
   EOF
   ```

5. Run it as a service. Until the e-paper adapter (FR-007) lands, the service writes an SVG every minute; the adapter will draw straight to the panel.

   ```ini
   # /etc/systemd/system/lightkeeper.service
   [Unit]
   Description=Lightkeeper bedside display
   After=network-online.target
   Wants=network-online.target

   [Service]
   User=pi
   EnvironmentFile=/etc/lightkeeper.env
   WorkingDirectory=/home/pi/lightkeeper
   ExecStart=/home/pi/lightkeeper/.venv/bin/python -m lightkeeper --watch --interval 60 --svg /run/lightkeeper/screen.svg
   RuntimeDirectory=lightkeeper
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now lightkeeper
   journalctl -u lightkeeper -f
   ```

6. Validate before anyone relies on it: run it beside the primary app for one full sensor session and log every mismatch, freeze, or missed STALE (the manual validation step in `docs/TEST_PLAN.md`).

### Pocket display (Xteink X4 Pro) and the bench board

The firmware rules are done and tested on a PC (`firmware/xteink`); the device build is the next firmware milestone (FR-010). Until then: install PlatformIO (VS Code extension, works on Windows), buy the bench board from `docs/HARDWARE.md`, and study WaveshareMon for Wi-Fi, TLS, and e-paper refresh patterns. Flashing steps for the Xteink will be written with the device build; read CrossPoint's flashing and recovery guides first and back up the SD card.

### Home Assistant

Planned (FR-008). The exit code and the SVG file are already usable: a `command_line` sensor that runs `python -m lightkeeper` and a `local_file` camera pointing at the SVG give a working card today. The proper integration will publish level, value, and age as entities.

## Part 4: The iOS companion app

Source is in `apps/ios/` (read `apps/ios/README.md`). The read-only layer builds and tests on GitHub's macOS runners on every change, so no Mac is required.

1. Development: edit Swift files in any editor; push; `.github/workflows/ios.yml` runs the shared-vector tests and builds the app.
2. Installing on a phone: TestFlight through the paid Apple Developer account. The signing and upload steps mirror Trio's browser build (App Store Connect API key stored as GitHub secrets); they are added to `ios.yml` when the first TestFlight build is cut, and documented here at that point.
3. In the app: Settings, enter the Nightscout URL and the **readable** token (it goes to the Keychain), then adjust display thresholds with your care team.

## Checking the whole stack

Run through `docs/DISPLAY_STATES.md` with the real system: fresh reading, a sensor warm-up, the phone out of Bluetooth range, the phone offline, and Nightscout stopped. Every display must show STALE or NO DATA within the stale limit, with no number that looks current. Record what you saw in `docs/TEST_PLAN.md`'s coverage table.
