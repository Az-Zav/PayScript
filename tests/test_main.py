"""Tests for the command-line pipeline (payscript/main.py)."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from payscript.errors import PayScriptError
from payscript.main import main, run_source

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class PipelineTests(unittest.TestCase):
    def run_sample(self, path, typed=()):
        source = (SAMPLES / path).read_text(encoding="utf-8")
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as scratch:
            old = os.getcwd()
            os.chdir(scratch)  # payslips/ is created in the current folder
            try:
                with redirect_stdout(out), mock.patch("builtins.input", side_effect=list(typed)):
                    run_source(source)
                payslips = {p.stem: p.read_text(encoding="utf-8")
                            for p in Path("payslips").glob("*.txt")}
            finally:
                os.chdir(old)
        return out.getvalue(), payslips

    def test_basic_salary_prints_name_and_net(self):
        out, _ = self.run_sample("valid/01_basic_salary.ps")
        self.assertEqual(out.split(), ["Juan", "Dela", "Cruz", "25000.00"])

    def test_payslip_file_uses_agreed_layout(self):
        _, payslips = self.run_sample("valid/02_attendance_input.ps", typed=["500"])
        lines = payslips["maria"].splitlines()
        self.assertEqual(lines[0], "Maria Santos")
        self.assertEqual(lines[1].split(), ["Basic", "Pay", "22000.00"])
        self.assertEqual(lines[-1].split(), ["Net", "Pay", "21018.75"])
        self.assertEqual(lines[-2].split(), ["Gross", "22218.75"])

    def test_lexical_error_carries_line_and_column(self):
        with self.assertRaises(PayScriptError) as ctx:
            self.run_sample("invalid/bad_char.ps")
        self.assertEqual(str(ctx.exception).split(":")[0], "Line 9, col 9")

    def test_missing_file_exits_with_1(self):
        with mock.patch("sys.argv", ["payscript", "run", "no_such_file.ps"]):
            self.assertEqual(main(), 1)

    def test_out_option_chooses_payslip_folder(self):
        source = (SAMPLES / "valid/06_arrays_for.ps").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as scratch:
            run_source(source, payslip_dir=str(Path(scratch) / "slips"))
            self.assertTrue((Path(scratch) / "slips" / "john.txt").is_file())


if __name__ == "__main__":
    unittest.main()