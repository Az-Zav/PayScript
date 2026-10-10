"""Tests for the command-line pipeline (payscript/main.py)."""

import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import pytest

from payscript.errors import PayScriptError
from payscript.main import main, run_source

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def run_sample(path, tmp_path, monkeypatch, typed=()):
    """Run a sample in a scratch folder; return (stdout text, {handle: payslip})."""
    source = (SAMPLES / path).read_text(encoding="utf-8")
    out = io.StringIO()
    monkeypatch.chdir(tmp_path)  # payslips/ is created in the current folder
    with redirect_stdout(out), mock.patch("builtins.input", side_effect=list(typed)):
        run_source(source)
    payslips = {p.stem: p.read_text(encoding="utf-8")
                for p in Path("payslips").glob("*.txt")}
    return out.getvalue(), payslips


def test_basic_salary_prints_name_and_net(tmp_path, monkeypatch):
    out, _ = run_sample("valid/01_basic_salary.ps", tmp_path, monkeypatch)
    assert out.split() == ["Juan", "Dela", "Cruz", "25000.00"]


def test_payslip_file_uses_agreed_layout(tmp_path, monkeypatch):
    _, payslips = run_sample("valid/02_attendance_input.ps", tmp_path, monkeypatch,
                             typed=["500"])
    lines = payslips["maria"].splitlines()
    assert lines[0] == "Maria Santos"
    assert lines[1].split() == ["Basic", "Pay", "22000.00"]
    assert lines[-1].split() == ["Net", "Pay", "21018.75"]
    assert lines[-2].split() == ["Gross", "22218.75"]


def test_lexical_error_carries_line_and_column(tmp_path, monkeypatch):
    with pytest.raises(PayScriptError) as info:
        run_sample("invalid/bad_char.ps", tmp_path, monkeypatch)
    assert str(info.value).split(":")[0] == "Line 9, col 9"


def test_missing_file_exits_with_1():
    with mock.patch("sys.argv", ["payscript", "run", "no_such_file.ps"]):
        assert main() == 1


def test_out_option_chooses_payslip_folder(tmp_path):
    source = (SAMPLES / "valid/06_arrays_for.ps").read_text(encoding="utf-8")
    run_source(source, payslip_dir=str(tmp_path / "slips"))
    assert (tmp_path / "slips" / "john.txt").is_file()
