"""The prerequisite check reports problems instead of passing silently."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("doctor", ROOT / "tools" / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


def test_doctor_passes_on_a_ready_machine(capsys):
    assert doctor.main() == 0
    assert "Ready." in capsys.readouterr().out


def test_doctor_names_missing_tools(monkeypatch, capsys):
    monkeypatch.setattr(doctor.shutil, "which", lambda tool: None)
    assert doctor.main() == 1
    out = capsys.readouterr().out
    assert "MISSING  g++" in out
    assert "MISSING  make" in out


def test_doctor_flags_old_python(monkeypatch):
    monkeypatch.setattr(doctor.sys, "version_info", (3, 9, 0))
    names = {name: ok for name, ok, _ in doctor.checks()}
    assert names["Python 3.11+"] is False


def test_doctor_accepts_firmware_tools_in_wsl_on_windows(monkeypatch):
    """MinGW lacks AddressSanitizer, so a Windows machine runs the firmware tests in WSL."""
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor.shutil, "which", lambda tool: "wsl.exe" if tool == "wsl" else None)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # This WSL has make and g++ but the probe for g++ alone is made to fail,
        # so only the make row can turn OK, and only because it checked g++ too.
        return doctor.subprocess.CompletedProcess(cmd, 0 if "make" in cmd[-1] else 1)

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    results = {name: ok for name, ok, _ in doctor.checks()}
    assert results["make (in WSL: wsl -- make -C firmware/xteink test)"] is True
    assert results["g++"] is False
    assert calls[-1][-1] == "command -v make && command -v g++"


def test_doctor_ignores_wsl_off_windows_or_when_it_fails(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda tool: "wsl" if tool == "wsl" else None)
    monkeypatch.setattr(doctor.sys, "platform", "linux")
    assert doctor._in_wsl("make") is False

    def broken(cmd, **kwargs):
        raise doctor.subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor.subprocess, "run", broken)
    assert doctor._in_wsl("make") is False
