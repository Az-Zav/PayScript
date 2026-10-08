import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_samples  # noqa: E402


class AnnotationParsingTests(unittest.TestCase):
    def test_reads_input_out_and_payslip_block(self):
        source = (
            "PRINT x\n"
            "// input: 500\n"
            "// expect-out: Maria 100.00\n"
            "// expect-payslip maria:\n"
            "//   Maria Santos\n"
            "//   Net Pay    100.00\n"
            "// expect-error: Line 1, col 1: oops\n"
        )
        exp = run_samples.parse_expectations(source)
        self.assertEqual(exp["input"], ["500"])
        self.assertEqual(exp["out"], ["Maria 100.00"])
        self.assertEqual(exp["payslips"]["maria"],
                         ["Maria Santos", "Net Pay    100.00"])
        self.assertEqual(exp["error"], "Line 1, col 1: oops")


class CheckTests(unittest.TestCase):
    def test_output_matches_ignoring_extra_spaces(self):
        exp = {"input": [], "out": ["Juan  25000.00"], "payslips": {}, "error": None}
        self.assertEqual(run_samples.check(exp, 0, "Juan 25000.00\n", "", "."), [])

    def test_output_mismatch_is_reported(self):
        exp = {"input": [], "out": ["Juan 25000.00"], "payslips": {}, "error": None}
        self.assertTrue(run_samples.check(exp, 0, "Juan 1.00\n", "", "."))

    def test_expected_error_must_appear_on_stderr(self):
        exp = {"input": [], "out": [], "payslips": {},
               "error": "Line 9, col 9: unknown character '@'"}
        good = run_samples.check(
            exp, 1, "", "[note: fake]\nLine 9, col 9: unknown character '@'\n", ".")
        self.assertEqual(good, [])
        self.assertTrue(run_samples.check(exp, 0, "", "", "."))

    def test_unexpected_failure_is_reported(self):
        exp = {"input": [], "out": [], "payslips": {}, "error": None}
        self.assertTrue(run_samples.check(exp, 1, "", "Line 1, col 1: x", "."))


if __name__ == "__main__":
    unittest.main()