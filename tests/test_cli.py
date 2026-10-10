"""End to end: every sample file through the real CLI, plus the CLI options."""

import subprocess
import sys

import pytest

import run_samples
from conftest import BASE, ROOT

SAMPLES = sorted((ROOT / "samples" / "valid").glob("*.ps")) + \
    sorted((ROOT / "samples" / "invalid").glob("*.ps"))


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_sample_matches_its_annotations(path):
    assert run_samples.run_sample(path) == []


def test_every_invalid_sample_declares_the_error_it_expects():
    for path in (ROOT / "samples" / "invalid").glob("*.ps"):
        exp = run_samples.parse_expectations(path.read_text(encoding="utf-8"))
        assert exp["error"], f"{path.name} has no // expect-error line"


def cli(tmp_path, source, *args, stdin=""):
    program = tmp_path / "prog.ps"
    program.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "payscript.main", "run", str(program), *args],
        input=stdin, capture_output=True, text=True, cwd=tmp_path,
    )


def test_exit_code_zero_and_output_on_success(tmp_path):
    result = cli(tmp_path, BASE + "PRINT maria.net")
    assert result.returncode == 0
    assert result.stdout.strip() == "22000.00"


def test_exit_code_one_and_message_on_language_error(tmp_path):
    result = cli(tmp_path, BASE + "PRINT ghost")
    assert result.returncode == 1
    assert result.stderr.startswith("Line 9, col 7:")


def test_out_option_writes_payslips_to_the_chosen_folder(tmp_path):
    result = cli(tmp_path, BASE + "PAYSLIP maria", "--out", "slips")
    assert result.returncode == 0
    assert (tmp_path / "slips" / "maria.txt").is_file()
    assert not (tmp_path / "payslips").exists()


def test_default_payslip_folder(tmp_path):
    cli(tmp_path, BASE + "PAYSLIP maria")
    assert (tmp_path / "payslips" / "maria.txt").is_file()


WARNING_SOURCE = BASE + 'ADD maria "Bonus" 1\nADD maria "bonus" 1\nPRINT 1'


def test_warnings_go_to_stderr_but_do_not_stop_the_run(tmp_path):
    result = cli(tmp_path, WARNING_SOURCE)
    assert result.returncode == 0
    assert "warning:" in result.stderr
    assert result.stdout.strip() == "1"


def test_strict_turns_warnings_into_a_failure(tmp_path):
    result = cli(tmp_path, WARNING_SOURCE, "--strict")
    assert result.returncode == 1
    assert "--strict" in result.stderr
    assert result.stdout == ""


def test_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "payscript.main", "run", str(tmp_path / "nope.ps")],
        capture_output=True, text=True)
    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_input_is_read_from_stdin(tmp_path):
    result = cli(tmp_path, BASE + 'PRINT INPUT("n? ") + 1', stdin="41\n")
    assert result.returncode == 0
    assert result.stdout.strip().endswith("42")


def test_missing_input_fails_cleanly(tmp_path):
    result = cli(tmp_path, BASE + "PRINT INPUT()", stdin="")
    assert result.returncode == 1


def test_tokens_command_lists_tokens(tmp_path):
    program = tmp_path / "t.ps"
    program.write_text("SET x TO 1", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "payscript.main", "tokens", str(program)],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0
    assert result.stdout.split()[0] == "SET"


def test_deeply_nested_program_gives_a_clean_error_not_a_traceback(tmp_path):
    source = BASE + "PRINT " + "(" * 400 + "1" + ")" * 400 + "\n"
    result = cli(tmp_path, source)
    assert result.returncode == 1
    assert "nested too deeply" in result.stderr
    assert "Traceback" not in result.stderr
