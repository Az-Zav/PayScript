"""Interpreter: expressions, statements, pay maths, tax, payslips, run-time errors."""

import pytest

from payscript.errors import PayScriptError

from conftest import BASE, COMPANY, MARIA, parse_source
from payscript.interpreter import interpret


def value(out, expr):
    """Evaluate one expression through PRINT and return the printed text."""
    return out(f"PRINT {expr}")[0]


def runtime_error(run, source, fragment, inputs=()):
    with pytest.raises(PayScriptError) as info:
        run(source, inputs)
    assert fragment in info.value.message
    return info.value


# ---------- arithmetic, text, logic ----------

@pytest.mark.parametrize("expr,expected", [
    ("1 + 2", "3"),
    ("7 - 10", "-3"),
    ("6 * 7", "42"),
    ("7 / 2", "3.50"),
    ("2 + 3 * 4", "14"),
    ("(2 + 3) * 4", "20"),
    ("-5 + 2", "-3"),
    ("1.5 + 1.5", "3.00"),
    ("10%", "0.10"),
    ("200 * 10%", "20.00"),
])
def test_arithmetic(out, expr, expected):
    assert value(out, expr) == expected


def test_text_concatenation_and_printing(out):
    assert value(out, '"a" + "b"') == "ab"
    assert out('PRINT "x", 1, TRUE, 2.5') == ["x 1 TRUE 2.50"]


@pytest.mark.parametrize("expr,expected", [
    ("1 < 2", "TRUE"), ("2 < 1", "FALSE"), ("2 <= 2", "TRUE"),
    ("3 > 2", "TRUE"), ("2 >= 3", "FALSE"), ("2 = 2", "TRUE"),
    ("2 != 2", "FALSE"), ('"a" = "a"', "TRUE"), ('"a" < "b"', "TRUE"),
    ("TRUE AND FALSE", "FALSE"), ("TRUE OR FALSE", "TRUE"),
    ("NOT TRUE", "FALSE"), ("NOT FALSE AND TRUE", "TRUE"),
    ("TRUE = TRUE", "TRUE"),
])
def test_comparison_and_logic(out, expr, expected):
    assert value(out, expr) == expected


def test_arrays_are_one_based_and_support_length(out):
    assert out("SET a TO [10, 20, 30]\nPRINT a[1], a[3], LENGTH(a)") == ["10 30 3"]
    assert value(out, "LENGTH(employees)") == "1"
    assert value(out, 'LENGTH("hello")') == "5"
    assert value(out, "[1, 2]") == "[1, 2]"


def test_set_updates_array_element(out):
    assert out("SET a TO [1, 2]\nSET a[2] TO 9\nPRINT a") == ["[1, 9]"]


def test_employees_array_gives_access_to_declared_employees(out):
    assert value(out, "employees[1].name") == "Maria"


# ---------- control flow ----------

def test_if_else_if_else(out):
    program = ("SET n TO {n}\nIF n < 10 THEN\n PRINT \"small\"\n"
               "ELSE IF n < 100 THEN\n PRINT \"medium\"\nELSE\n PRINT \"large\"\nEND")
    assert out(program.format(n=5)) == ["small"]
    assert out(program.format(n=50)) == ["medium"]
    assert out(program.format(n=500)) == ["large"]


def test_if_without_else_does_nothing_when_false(out):
    assert out('IF FALSE THEN\n PRINT "no"\nEND') == []


def test_while_loop(out):
    assert out("SET i TO 0\nWHILE i < 3\n SET i TO i + 1\n PRINT i\nEND") == [
        "1", "2", "3"]


def test_while_with_false_condition_never_runs(out):
    assert out('WHILE FALSE\n PRINT "x"\nEND') == []


def test_for_range_is_inclusive(out):
    assert out("FOR EACH i IN 1 -> 4\n PRINT i\nEND") == ["1", "2", "3", "4"]


def test_for_each_over_array_and_employees(out):
    assert out("FOR EACH x IN [5, 6]\n PRINT x\nEND") == ["5", "6"]
    assert out("FOR EACH e IN employees\n PRINT e.name\nEND") == ["Maria"]


def test_nested_loops(out):
    body = ("FOR EACH i IN 1 -> 2\n FOR EACH j IN 1 -> 2\n  PRINT i * 10 + j\n"
            " END\nEND")
    assert out(body) == ["11", "12", "21", "22"]


# ---------- functions ----------

def test_function_call_and_return(out):
    assert out("FUNCTION twice(n)\n RETURN n * 2\nEND\nPRINT twice(4)") == ["8"]


def test_function_with_condition_and_early_return(out):
    src = ("FUNCTION sign(n)\n IF n < 0 THEN\n  RETURN \"neg\"\n END\n"
           " RETURN \"pos\"\nEND\nPRINT sign(-1), sign(1)")
    assert out(src) == ["neg pos"]


def test_function_can_call_an_earlier_function(out):
    src = ("FUNCTION twice(n)\n RETURN n * 2\nEND\n"
           "FUNCTION quad(n)\n RETURN twice(twice(n))\nEND\nPRINT quad(3)")
    assert out(src) == ["12"]


def test_function_can_read_employee_fields(out):
    assert out("FUNCTION pay(e)\n RETURN e.salary\nEND\nPRINT pay(maria)") == [
        "22000"]


def test_function_variables_do_not_leak(run):
    runtime_error(run, BASE + "FUNCTION f()\n SET inner TO 1\n RETURN 1\nEND\n"
                  "SET a TO f()\nPRINT inner", "inner")


# ---------- INPUT ----------

def test_input_converts_numbers_and_keeps_text(run):
    result = run(BASE + 'SET a TO INPUT("A? ")\nSET b TO INPUT()\nSET c TO INPUT()\n'
                 'PRINT a + 1, b, c', inputs=["41", "2.5", "hello"])
    assert result.lines[-1] == "42 2.50 hello"
    assert result.lines[0] == "A? "


def test_input_exhausted_is_an_error(run):
    runtime_error(run, BASE + "SET a TO INPUT()", "INPUT reached end of input")


# ---------- pay maths ----------

def test_computed_rates(out):
    rows = out("PRINT maria.daily_rate, maria.hourly_rate, maria.minute_rate")
    assert rows == ["1000.00 125.00 2.08"]


def test_basic_gross_net_without_adjustments(out):
    assert out("PRINT maria.basic_pay, maria.gross, maria.tax, maria.net") == [
        "22000.00 22000.00 0.00 22000.00"]


def test_absences_and_lateness_reduce_basic_pay(run):
    src = (COMPANY + 'EMPLOYEE a\n name "A"\n salary 22000\n absences 2\n'
           ' late_minutes 30\nEND\nPRINT a.absence_deduction, a.tardiness_deduction,'
           ' a.basic_pay')
    assert run(src).lines == ["2000.00 62.50 19937.50"]


def test_each_pay_command_affects_the_right_totals(out):
    src = ('ADD maria "A" 1000\nEXEMPT maria "E" 500\n'
           'CONTRIBUTE maria "C" 200\nLESS maria "L" 100\n'
           "PRINT maria.total_add, maria.total_exempt, maria.total_contribute,"
           " maria.total_less\n"
           "PRINT maria.gross, maria.taxable, maria.net")
    assert out(src) == ["1000.00 500.00 200.00 100.00",
                        "23500.00 22800.00 23200.00"]


def test_pay_command_amount_can_be_an_expression(out):
    assert out('ADD maria "B" 10% * 1000\nPRINT maria.total_add') == ["100.00"]


def test_pay_command_in_a_loop_over_employees(run):
    src = (COMPANY + 'EMPLOYEE a\n name "A"\n salary 1000\nEND\n'
           'EMPLOYEE b\n name "B"\n salary 2000\nEND\n'
           'FOR EACH e IN employees\n ADD e "Bonus" 100\nEND\n'
           "PRINT a.net, b.net")
    assert run(src).lines == ["1100.00 2100.00"]


# ---------- tax table ----------

TAX = "TAX\n BELOW 20833 = 0%\n 20833 -> 33333 = 15%\n ABOVE 33333 = 1875 + 20%\nEND\n"


def tax_of(run, salary):
    src = (COMPANY + TAX + f'EMPLOYEE a\n name "A"\n salary {salary}\nEND\n'
           "PRINT a.tax")
    return run(src).lines[0]


def test_no_tax_table_means_no_tax(out):
    assert value(out, "maria.tax") == "0.00"


# Hand-checked: RANGE pays 15% of (taxable - 20833); ABOVE pays 1875 + 20% of
# (taxable - 33333). BELOW is strictly less than its limit, RANGE includes both ends.
@pytest.mark.parametrize("salary,expected", [
    (10000, "0.00"),
    (20000, "0.00"),
    (20833, "0.00"),
    (28000, "1075.05"),
    (33333, "1875.00"),
    (40000, "3208.40"),
])
def test_tax_brackets(run, salary, expected):
    assert tax_of(run, salary) == expected


def test_tax_reduces_net(run):
    src = (COMPANY + TAX + 'EMPLOYEE a\n name "A"\n salary 28000\nEND\n'
           "PRINT a.gross, a.tax, a.net")
    gross, tax, net = (float(x) for x in run(src).lines[0].split())
    assert gross == 28000
    assert net == pytest.approx(gross - tax, abs=0.01)
    assert 0 < tax < gross


def test_contributions_lower_taxable_income(run):
    base = (COMPANY + TAX + 'EMPLOYEE a\n name "A"\n salary 28000\nEND\n')
    plain = float(run(base + "PRINT a.tax").lines[0])
    reduced = float(run(base + 'CONTRIBUTE a "SSS" 5000\nPRINT a.tax').lines[0])
    assert reduced < plain


# ---------- payslips ----------

def test_payslip_file_layout(run):
    src = (BASE + 'ADD maria "Bonus" 500\nLESS maria "Uniform" 300\nPAYSLIP maria')
    lines = run(src).payslip("maria").splitlines()
    assert lines[0] == "Maria"
    assert lines[1].split() == ["Basic", "Pay", "22000.00"]
    assert [l.split()[0] for l in lines[2:]] == [
        "Bonus", "Withholding", "Uniform", "Gross", "Net"]
    assert lines[-1].split() == ["Net", "Pay", "22200.00"]
    assert len({len(l) for l in lines[1:]}) == 1  # amounts are right-aligned


def test_payslip_shows_position_when_given(run):
    src = (COMPANY + 'EMPLOYEE a\n name "A"\n position "Boss"\n salary 1\nEND\n'
           "PAYSLIP a")
    assert run(src).payslip("a").splitlines()[1] == "Boss"


def test_absences_and_tardiness_rows_only_when_non_zero(run):
    plain = run(BASE + "PAYSLIP maria").payslip("maria")
    assert "Absences" not in plain and "Tardiness" not in plain
    src = (COMPANY + 'EMPLOYEE a\n name "A"\n salary 22000\n absences 1\n'
           " late_minutes 10\nEND\nPAYSLIP a")
    text = run(src).payslip("a")
    assert "Absences" in text and "Tardiness" in text


def test_payslip_for_every_employee_in_a_loop(run):
    src = (COMPANY + 'EMPLOYEE a\n name "A"\n salary 1\nEND\n'
           'EMPLOYEE b\n name "B"\n salary 2\nEND\n'
           "FOR EACH e IN employees\n PAYSLIP e\nEND")
    result = run(src)
    assert (result.payslip_dir / "a.txt").is_file()
    assert (result.payslip_dir / "b.txt").is_file()


def test_payslip_reflects_adjustments_made_before_it_is_written(run):
    src = BASE + "PAYSLIP maria\nADD maria \"Late\" 100\nPAYSLIP maria"
    assert "Late" in run(src).payslip("maria")


def test_interpret_returns_computed_numbers(tmp_path):
    program = parse_source(BASE + 'ADD maria "B" 100')
    result = interpret(program, output=lambda _: None, input_fn=input,
                       payslip_dir=str(tmp_path))
    assert result is not None


# ---------- run-time errors ----------

def test_division_by_zero(run):
    runtime_error(run, BASE + "PRINT 1 / 0", "Division by zero")


def test_text_plus_number(run):
    runtime_error(run, BASE + 'PRINT "a" + 1', "Cannot use '+'")


@pytest.mark.parametrize("expr", ['"a" * 2', '"a" - "b"', "TRUE + 1", "[1] + [2]"])
def test_arithmetic_on_wrong_types(run, expr):
    runtime_error(run, BASE + f"PRINT {expr}", "Cannot use")


@pytest.mark.parametrize("expr", ['1 < "a"', "TRUE < FALSE", '1 = "1"'])
def test_comparing_incompatible_types(run, expr):
    runtime_error(run, BASE + f"PRINT {expr}", "Cannot compare")


def test_condition_must_be_true_or_false(run):
    runtime_error(run, BASE + "IF 1 THEN\n PRINT 1\nEND", "TRUE or FALSE")
    runtime_error(run, BASE + "WHILE 1\n PRINT 1\nEND", "TRUE or FALSE")


def test_array_index_out_of_range(run):
    runtime_error(run, BASE + "SET a TO [1]\nPRINT a[2]", "out of range")
    runtime_error(run, BASE + "SET a TO [1]\nPRINT a[0]", "out of range")


def test_array_index_must_be_a_whole_number(run):
    runtime_error(run, BASE + "SET a TO [1, 2]\nPRINT a[1.5]", "whole number")


def test_cannot_index_a_non_array(run):
    runtime_error(run, BASE + "SET a TO 5\nPRINT a[1]", "Cannot index")


def test_unknown_employee_field(run):
    runtime_error(run, BASE + "PRINT maria.shoe_size", "no field 'shoe_size'")


def test_field_of_non_employee(run):
    runtime_error(run, BASE + "SET a TO 5\nPRINT a.x", "Cannot read field")


def test_for_each_needs_an_array(run):
    runtime_error(run, BASE + "FOR EACH x IN 5\n PRINT x\nEND", "needs an array")


def test_duplicate_label_is_a_run_time_error(run):
    runtime_error(run, BASE + 'ADD maria "Bonus" 1\nADD maria "Bonus" 2',
                  "Bonus")


def test_pay_amount_must_be_a_number(run):
    runtime_error(run, BASE + 'ADD maria "Bonus" "lots"', "amount must be a number")


def test_pay_target_must_be_an_employee(run):
    runtime_error(run, BASE + 'SET a TO 5\nADD a "Bonus" 1', "must be an employee")


def test_length_of_a_number(run):
    runtime_error(run, BASE + "PRINT LENGTH(5)", "LENGTH needs")


def test_recursion_is_rejected_by_the_validator(run):
    with pytest.raises(PayScriptError, match="must be declared before use"):
        run(BASE + "FUNCTION f(n)\n RETURN f(n + 1)\nEND\nPRINT f(1)")


def test_runaway_recursion_is_stopped_if_validation_is_skipped(tmp_path):
    program = parse_source(
        BASE + "FUNCTION f(n)\n RETURN f(n + 1)\nEND\nPRINT f(1)")
    with pytest.raises(PayScriptError, match="Too many nested calls"):
        interpret(program, output=lambda _: None, input_fn=input,
                  payslip_dir=str(tmp_path))


def test_run_time_error_has_the_line_of_the_problem(run):
    err = runtime_error(run, BASE + "PRINT 1\nPRINT 1 / 0", "Division by zero")
    assert err.line == 10
