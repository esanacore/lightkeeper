# Help

This file provides help for humans and AI agents working on this project.

## For Humans

- **Primary Maintainers**: Eric (@esanacore), building Lightkeeper with and for Kaitlin.
- **Getting Started**: Read `README.md` and `docs/SETUP.md`.
- **The iOS app**: in Settings, enter just your Nightscout site (`https://your-site.example`, nothing after the name) and a readable token made in Nightscout's Admin Tools, Subjects. Check connection says in plain words whether it worked, including "This Nightscout needs a token to be read" when the site requires a token and the field is empty. Details: `docs/SETUP.md`, Part 4.
- **The desktop window**: `python -m lightkeeper.desktop --demo` shows the panel in a window (`r` refresh, `t` pixels or text, `q` quit). It needs Tk: `sudo apt install python3-tk` on Debian, Ubuntu and Raspberry Pi OS; the python.org installers include it. `--theme auto` follows the system only on Windows; the window does not say why Nightscout is unreachable; and on Windows `lightkeeper-window` exits silently on a configuration error, so run `python -m lightkeeper.desktop` in a terminal to see it. The other known limits are in `docs/SAFETY.md` (desktop window residual risks). Details: `docs/SETUP.md`, Part 3.
- **The Android app**: build and sideload the debug APK as `apps/android/README.md` says (on Windows, from a checkout path of about 60 characters or fewer), then enter just your Nightscout site and a readable token in Settings. There is no Check connection yet: a failed fetch shows as `Nightscout unreachable`. Details: `docs/SETUP.md`, Part 5.
- **Asking for Help**: open an issue at https://github.com/esanacore/lightkeeper/issues. For security problems, follow `.github/SECURITY.md` instead. For questions about Trio, Nightscout, or the sensor and pump themselves, the community docs and support channels linked in `docs/SETUP.md` are the right place.
- **Medical questions**: Lightkeeper is not a medical device and its maintainers can't give medical advice. Talk to your care team.

## Using This Project in Your IDE

This project follows Eric's Engineering Constitution. You do **not** install
anything "for the constitution." Open the repository in your IDE with an AI
coding assistant installed, and the assistant automatically reads the
instruction files committed here — chiefly `AGENTS.md`, plus any tool-specific
file this repo carries — which point it at the read-only `constitution/`
submodule and its reading order.

| Tool | File it reads automatically |
|---|---|
| Claude Code | `CLAUDE.md`, `.claude/settings.json` |
| GitHub Copilot in Visual Studio, VS Code, or JetBrains (+ **Solon** custom agent) | `AGENTS.md`, `.github/agents/solon.agent.md` |
| Most other assistants (Cursor, Continue, Codex, and others) | `AGENTS.md` |

This repository was bootstrapped with Claude Code instructions only. `AGENTS.md`
is the cross-vendor file and is read by most modern assistants directly. To add
another tool's own instruction file, re-run the constitution bootstrap with
`--agents=<tool>` (see `constitution/INTEGRATION.md`). Run `git submodule update --init --recursive` after
cloning so the `constitution/` files the instructions point at exist.

To confirm the constitution is loaded, ask your assistant:
`Which engineering constitution files are you following, and what is the reading order?`
It should name `AGENTS.md` and describe the order starting from
`constitution/CONSTITUTION.md`.

Full per-IDE setup steps and Visual Studio / Solon details live in
`constitution/INTEGRATION.md`, "Using the Constitution in Your IDE."

## For AI Agents

- **Entry Point**: Read `AGENTS.md` and `constitution/CONSTITUTION.md`.
- **Workflow**: Follow `constitution/AI_WORKFLOW.md`.
- **Session Planning**: Check `docs/SESSION_PLAN.md` for a previous interrupted session; write your own plan there before implementing.
- **Next Steps**: End every push with a Next Steps procedure (`constitution/AI_WORKFLOW.md`, "Next Steps Procedure"): a numbered checklist of what happens next, each step tagged **HUMAN**, **AGENT**, or **AUTOMATED**, with every step only a person can do (hardware, credentials, approvals) called out and described; put it in the pull request and `docs/AGENT_HANDOFF.md`.
- **Demo Page**: Keep the demo page current — when a change alters user-facing behavior and the repository has a `demo.html`, update it in the same change; a demo still showing the old behavior is an incomplete change (`constitution/DOCUMENTATION.md`, "Demo Page").
- **Project Memory**: Read `docs/MEMORY.md` to load project context, codebase learnings, and user preferences. Propose new codebase learnings, user preferences, or major decisions to the user and (upon approval) record them in `docs/MEMORY.md` before completing work.
- **Command Help**: See `docs/COMMAND_REFERENCE.md`.
- **Troubleshooting**: See `docs/TROUBLESHOOTING.md`.
- **Handoffs**: If you are finishing a session, see `docs/AGENT_HANDOFF.md` and clear or archive `docs/SESSION_PLAN.md`.

## Escalation Policy

If an agent is stuck or encounters an ambiguous situation:
1. Search `docs/TROUBLESHOOTING.md`.
2. Check `TODO.md` for related tasks or blockers.
3. Stop and ask the human user for clarification.
