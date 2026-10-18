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
