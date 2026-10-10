"""Tests for the sample runner (run_samples.py): annotation parsing and checking."""

import run_samples


def test_reads_input_out_and_payslip_block():
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
    assert exp["input"] == ["500"]
    assert exp["out"] == ["Maria 100.00"]
    assert exp["payslips"]["maria"] == ["Maria Santos", "Net Pay    100.00"]
    assert exp["error"] == "Line 1, col 1: oops"


def test_output_matches_ignoring_extra_spaces():
    exp = {"input": [], "out": ["Juan  25000.00"], "payslips": {}, "error": None}
    assert run_samples.check(exp, 0, "Juan 25000.00\n", "", ".") == []


def test_output_mismatch_is_reported():
    exp = {"input": [], "out": ["Juan 25000.00"], "payslips": {}, "error": None}
    assert run_samples.check(exp, 0, "Juan 1.00\n", "", ".")


def test_expected_error_must_appear_on_stderr():
    exp = {"input": [], "out": [], "payslips": {},
           "error": "Line 9, col 9: unknown character '@'"}
    good = run_samples.check(
        exp, 1, "", "[note: fake]\nLine 9, col 9: unknown character '@'\n", ".")
    assert good == []
    assert run_samples.check(exp, 0, "", "", ".")


def test_unexpected_failure_is_reported():
    exp = {"input": [], "out": [], "payslips": {}, "error": None}
    assert run_samples.check(exp, 1, "", "Line 1, col 1: x", ".")
