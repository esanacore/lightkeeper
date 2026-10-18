# Setup

This guide covers two things: setting up a workstation to develop `glucose_watch`, and the order for standing up the rest of the stack (Nightscout, Trio). The stack steps link to the upstream docs on purpose, because those projects change quickly and their docs are the source of truth.

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
python --version        # 3.11 or newer (use python3 on macOS/Linux)
git --version
git submodule status    # constitution should not start with "-"
```

## Installation

```bash
git clone --recurse-submodules <repository-url> t1d-open-stack
cd t1d-open-stack
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
python -m glucose_watch --demo
python -m pytest --cov
```

## Environment Variables

There is no `.env` loader; set variables in your shell or service definition. See `docs/ENV_VARS.md`.

<details>
<summary>Windows (PowerShell)</summary>

```powershell
$env:NIGHTSCOUT_URL = "https://ns.example.com"
$env:NIGHTSCOUT_TOKEN = Read-Host "Readable token"
python -m glucose_watch
```

</details>

<details>
<summary>macOS / Linux (bash or zsh)</summary>

```bash
export NIGHTSCOUT_URL="https://ns.example.com"
read -rs NIGHTSCOUT_TOKEN && export NIGHTSCOUT_TOKEN
python -m glucose_watch
```

</details>

## Standing Up the Stack

Follow the phases in `docs/MVP_BACKLOG.md`. In short:

1. **Nightscout (Phase 1).** Deploy following the Nightscout documentation (nightscout.github.io). Use HTTPS, a long random API_SECRET, and set authentication to deny by default. In the admin tools, create a subject with the `readable` role and use its token for `glucose_watch`. Record the hosting choice in a new ADR.
2. **Trio (Phase 2).** Read the Trio docs (triodocs.org) end to end first. Kaitlin talks to her endocrinologist before starting. Build with Trio's browser build method (GitHub Actions to TestFlight, no Mac needed) using a paid Apple Developer account, set the Dexcom G7 app as the CGM source, turn off iOS automatic updates, and point Trio at Nightscout. Omnipod 5 pod support is in open beta; follow the instructions at nightscout.github.io/omnipod-five and keep the official Omnipod 5 app or Controller as a fallback.
3. **Open loop, then closed loop (Phases 2 and 3).** Promotion criteria are in `docs/adr/0002-trio-on-iphone-as-dosing-controller.md`.
4. **Displays (Phase 4).** Run `glucose_watch` on the target device and compare it with the primary app for a full sensor session before relying on it.
