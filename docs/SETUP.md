# Setup

This guide covers two things: setting up a workstation to develop `lightkeeper`, and the order for standing up the rest of the stack (Nightscout, Trio). The stack steps link to the upstream docs on purpose, because those projects change quickly and their docs are the source of truth.

## IDE Setup

This project follows Eric's Engineering Constitution. Open the repository in VS Code, Visual Studio, a JetBrains IDE, or Claude Code from the project folder; the committed instruction files (`AGENTS.md`, `CLAUDE.md`) apply the constitution automatically. After cloning, run `git submodule update --init --recursive` so `constitution/` is present. See `docs/HELP.md` and `constitution/INTEGRATION.md`.

## Supported Platforms

- Windows: Windows 11, PowerShell 7
- macOS: macOS 14+ (optional; Trio is built in the browser with GitHub Actions, so no Mac is needed)
- Linux: Ubuntu 22.04+ and Raspberry Pi OS Bookworm (display builds)
- CI runs on Ubuntu.

## Prerequisites

Python 3.11 or newer and Git.

<details>
<summary>Windows (PowerShell)</summary>

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
```

</details>

<details>
<summary>macOS (zsh)</summary>

```bash
brew install python@3.12 git
```

</details>

<details>
<summary>Linux / Raspberry Pi (bash)</summary>

```bash
sudo apt update && sudo apt install -y python3 python3-venv git
```

</details>

## Verify Prerequisites

```bash
python tools/doctor.py   # use python3 on macOS/Linux
```

It checks Python 3.11+, the constitution submodule, the test and lint tools, and the C++ toolchain, and names exactly what's missing. Run it again after installing (next step) to confirm the dev tools.

## Installation

```bash
git clone --recurse-submodules <repository-url> lightkeeper
cd lightkeeper
```

<details>
<summary>Windows (PowerShell)</summary>

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

</details>

<details>
<summary>macOS / Linux (bash or zsh)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

</details>

## First Run

```bash
python -m lightkeeper --demo
python -m pytest --cov
```

## Environment Variables

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

## Standing Up the Stack

Follow the phases in `docs/MVP_BACKLOG.md`. In short:

1. **Nightscout (Phase 1).** Deploy following the Nightscout documentation (nightscout.github.io). Use HTTPS, a long random API_SECRET, and set authentication to deny by default. In the admin tools, create a subject with the `readable` role and use its token for `lightkeeper`. Record the hosting choice in a new ADR.
2. **Trio (Phase 2).** Read the Trio docs (triodocs.org) end to end first. Kaitlin talks to her endocrinologist before starting. Build with Trio's browser build method (GitHub Actions to TestFlight, no Mac needed) using a paid Apple Developer account, set the Dexcom G7 app as the CGM source, turn off iOS automatic updates, and point Trio at Nightscout. Omnipod 5 pods are supported on Trio's main branch since v1.0.0; follow the switching steps at nightscout.github.io/omnipod-five/compatibility.html (keep a backup DASH pod, don't fill the pod until Trio shows the pairing screen) and keep the official Omnipod 5 app or Controller as a fallback. For Dexcom G7, the first sensor session must start in the country of the App Store the Dexcom app came from.
3. **Open loop, then closed loop (Phases 2 and 3).** Promotion criteria are in `docs/adr/0002-trio-on-iphone-as-dosing-controller.md`.
4. **Displays (Phase 4).** Run `lightkeeper` on the target device and compare it with the primary app for a full sensor session before relying on it.
