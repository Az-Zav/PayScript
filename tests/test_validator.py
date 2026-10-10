"""Validator: every semantic rule, one accepted and one rejected case each."""

import pytest

from payscript.errors import PayScriptError
from payscript.validator import PayScriptWarning

from conftest import BASE, COMPANY, MARIA, check


def rejects(source, fragment):
    with pytest.raises(PayScriptError) as info:
        check(source)
    assert fragment in info.value.message
    assert info.value.line >= 1 and info.value.col >= 1
    return info.value


# ---------- program structure ----------

def test_minimal_valid_program():
    assert check(BASE) == []


def test_company_is_required():
    rejects(MARIA, "Exactly one COMPANY")


def test_duplicate_company():
    err = rejects(COMPANY + COMPANY, "Only one declaration is allowed")
    assert err.line == 5


def test_duplicate_tax_block():
    tax = "TAX\n BELOW 100 = 0%\nEND\n"
    rejects(BASE + tax + tax, "TAX: Only one declaration")


@pytest.mark.parametrize("body", [
    "IF TRUE THEN\n COMPANY\n  working_days 1\n  hours_per_day 1\n END\nEND",
    'IF TRUE THEN\n EMPLOYEE bob\n  name "B"\n  salary 1\n END\nEND',
    "WHILE FALSE\n TAX\n  BELOW 1 = 0%\n END\nEND",
    "IF TRUE THEN\n FUNCTION f()\n  RETURN 1\n END\nEND",
])
def test_declarations_must_be_top_level(body):
    with pytest.raises(PayScriptError):
        check(BASE + body)


# ---------- COMPANY / EMPLOYEE fields ----------

@pytest.mark.parametrize("field", ["working_days", "hours_per_day"])
def test_company_required_fields(field):
    other = "hours_per_day 8" if field == "working_days" else "working_days 22"
    rejects(f"COMPANY\n {other}\nEND\n", f"Missing required field '{field}'")


@pytest.mark.parametrize("field", ["name", "salary"])
def test_employee_required_fields(field):
    body = 'salary 1' if field == "name" else 'name "A"'
    rejects(COMPANY + f"EMPLOYEE a\n {body}\nEND\n",
            f"Missing required field '{field}'")


def test_unknown_employee_field():
    rejects(COMPANY + 'EMPLOYEE a\n name "A"\n salary 1\n nickname "x"\nEND',
            "Unknown field 'nickname'")


def test_duplicate_field():
    rejects(COMPANY + 'EMPLOYEE a\n name "A"\n salary 1\n salary 2\nEND',
            "Duplicate field 'salary'")


def test_text_field_given_a_number_and_number_field_given_text():
    rejects(COMPANY + 'EMPLOYEE a\n name 5\n salary 1\nEND', "must be text")
    rejects(COMPANY + 'EMPLOYEE a\n name "A"\n salary "lots"\nEND',
            "must be a number")


@pytest.mark.parametrize("field", ["working_days", "hours_per_day"])
def test_company_numbers_must_be_positive(field):
    days, hours = (0, 8) if field == "working_days" else (22, 0)
    with pytest.raises(PayScriptError):
        check(f"COMPANY\n working_days {days}\n hours_per_day {hours}\nEND\n")


@pytest.mark.parametrize("field", ["absences", "late_minutes", "overtime_hours"])
def test_optional_employee_numbers_accept_zero(field):
    check(COMPANY + f'EMPLOYEE a\n name "A"\n salary 1\n {field} 0\nEND')


def test_all_employee_fields_are_accepted():
    check(COMPANY + 'EMPLOYEE a\n name "A"\n position "P"\n salary 1\n'
          ' absences 1\n late_minutes 1\n overtime_hours 1\nEND')


# ---------- names ----------

@pytest.mark.parametrize("name", [
    "company", "employees", "daily_rate", "hourly_rate", "minute_rate",
    "absence_deduction", "tardiness_deduction", "basic_pay", "overtime_pay",
    "total_add",
    "total_exempt", "total_contribute", "total_less", "gross", "taxable",
    "tax", "net",
])
def test_reserved_names_cannot_be_used(name):
    rejects(BASE + f"SET {name} TO 1", "reserved name")


def test_reserved_name_as_employee_handle_and_function():
    with pytest.raises(PayScriptError):
        check(COMPANY + 'EMPLOYEE net\n name "N"\n salary 1\nEND')
    with pytest.raises(PayScriptError):
        check(BASE + "FUNCTION tax()\n RETURN 1\nEND")


def test_undefined_variable():
    rejects(BASE + "PRINT ghost", "ghost")


def test_variable_is_defined_after_set():
    check(BASE + "SET x TO 1\nPRINT x")


def test_variable_used_before_set_is_rejected():
    rejects(BASE + "PRINT x\nSET x TO 1", "'x'")


def test_loop_variable_cannot_shadow_an_employee():
    rejects(BASE + "FOR EACH maria IN employees\n PRINT 1\nEND", "maria")


def test_loop_variable_is_scoped_to_the_loop():
    with pytest.raises(PayScriptError):
        check(BASE + "FOR EACH e IN employees\n PRINT 1\nEND\nPRINT e")


def test_name_declared_twice_by_employee_and_set():
    rejects(BASE + "SET maria TO 1", "maria")


# ---------- read-only fields ----------

def test_parser_already_refuses_to_assign_to_a_field():
    with pytest.raises(PayScriptError, match="Expected TO"):
        check(BASE + "SET maria.net TO 5")


def test_validator_rejects_field_assignment_in_a_hand_built_ast():
    from payscript import ast_nodes as ast
    from payscript.validator import validate

    def at(cls, **kw):
        return cls(line=1, col=1, **kw)

    target = at(ast.FieldAccess, base=at(ast.Name, name="maria"), field_name="net")
    program = at(ast.Program, statements=[
        at(ast.CompanyDecl, fields=[
            at(ast.FieldEntry, name="working_days", value=at(ast.Literal, value=22)),
            at(ast.FieldEntry, name="hours_per_day", value=at(ast.Literal, value=8))]),
        at(ast.EmployeeDecl, handle="maria", fields=[
            at(ast.FieldEntry, name="name", value=at(ast.Literal, value="M")),
            at(ast.FieldEntry, name="salary", value=at(ast.Literal, value=1))]),
        at(ast.SetStmt, target=target, value=at(ast.Literal, value=5)),
    ])
    with pytest.raises(PayScriptError, match="read-only"):
        validate(program)


# ---------- pay commands ----------

@pytest.mark.parametrize("kind", ["ADD", "EXEMPT", "CONTRIBUTE", "LESS"])
def test_pay_command_on_declared_employee_is_valid(kind):
    check(BASE + f'{kind} maria "Thing" 1')


def test_pay_target_must_be_declared():
    rejects(BASE + 'ADD ghost "Bonus" 1', "ghost")


def test_pay_target_may_be_a_loop_variable():
    check(BASE + 'FOR EACH e IN employees\n ADD e "Bonus" 1\nEND')


def test_pay_target_may_be_indexed():
    check(BASE + 'ADD employees[1] "Bonus" 1')


@pytest.mark.parametrize("label", ["Basic Pay", "Absences", "Tardiness",
                                   "Overtime", "Withholding Tax"])
def test_reserved_labels(label):
    rejects(BASE + f'ADD maria "{label}" 1', "reserved")


def test_label_must_be_text():
    with pytest.raises(PayScriptError):
        check(BASE + "ADD maria 5 1")


def test_labels_differing_only_in_case_warn():
    caught = check(BASE + 'ADD maria "Bonus" 1\nADD maria "bonus" 1')
    assert any(issubclass(w.category, PayScriptWarning) for w in caught)


def test_same_label_in_separate_if_branches_is_allowed():
    caught = check(BASE + 'IF TRUE THEN\n ADD maria "Bonus" 1\n'
                   'ELSE\n ADD maria "Bonus" 2\nEND')
    assert caught == []


def test_payslip_target_must_be_declared():
    rejects(BASE + "PAYSLIP ghost", "ghost")


# ---------- functions ----------

def test_valid_function_and_call():
    check(BASE + "FUNCTION double(n)\n RETURN n * 2\nEND\nPRINT double(2)")


def test_function_missing_return():
    rejects(BASE + "FUNCTION f()\n SET a TO 1\nEND", "RETURN is required")


def test_return_outside_function():
    rejects(BASE + "RETURN 1", "inside a function")


def test_pay_commands_not_allowed_inside_function():
    rejects(BASE + 'FUNCTION f()\n ADD maria "X" 1\n RETURN 1\nEND',
            "not allowed inside a function")


def test_function_can_read_company_and_employees():
    check(BASE + "FUNCTION f()\n RETURN company.working_days\nEND")
    check(BASE + "FUNCTION n()\n RETURN LENGTH(employees)\nEND")


def test_function_cannot_read_global_variables():
    rejects(BASE + "SET x TO 5\nFUNCTION f()\n RETURN x\nEND", "must be declared")


def test_function_cannot_read_company_before_it_is_declared():
    rejects(MARIA + "FUNCTION f()\n RETURN company.working_days\nEND\n" + COMPANY,
            "must be declared")


def test_duplicate_parameter():
    rejects(BASE + "FUNCTION f(a, a)\n RETURN a\nEND", "Duplicate parameter")


def test_undefined_function():
    rejects(BASE + "PRINT nope(1)", "must be declared before use")


def test_function_must_be_declared_before_use():
    with pytest.raises(PayScriptError):
        check(BASE + "PRINT f()\nFUNCTION f()\n RETURN 1\nEND")


def test_wrong_argument_count():
    rejects(BASE + "FUNCTION f(a)\n RETURN a\nEND\nPRINT f(1, 2)", "Expected")


def test_length_requires_one_argument_and_input_takes_any():
    check(BASE + 'SET a TO LENGTH(employees)\nSET b TO INPUT()\nSET c TO INPUT("p")')
    with pytest.raises(PayScriptError):
        check(BASE + "SET a TO LENGTH()")


# ---------- loops ----------

def test_reversed_for_range():
    rejects(BASE + "FOR EACH i IN 3 -> 1\n PRINT i\nEND", "must not be greater")


def test_equal_for_range_is_valid():
    check(BASE + "FOR EACH i IN 2 -> 2\n PRINT i\nEND")


# ---------- tax table ----------

def test_valid_tax_table():
    check(BASE + "TAX\n BELOW 100 = 0%\n 100 -> 200 = 15%\n"
          " ABOVE 200 = 20 + 20%\nEND")


def test_overlapping_tax_ranges():
    rejects(BASE + "TAX\n 0 -> 100 = 0%\n 50 -> 200 = 10%\nEND", "must not overlap")


def test_tax_range_lower_above_upper():
    rejects(BASE + "TAX\n 200 -> 100 = 10%\nEND", "lower bound must not exceed")


def test_below_and_above_overlap():
    with pytest.raises(PayScriptError):
        check(BASE + "TAX\n BELOW 500 = 0%\n ABOVE 100 = 10%\nEND")


# ---------- the validator reports the first problem, with a location ----------

def test_error_location_is_the_offending_node():
    err = rejects(BASE + "SET x TO 1\nPRINT ghost", "ghost")
    assert err.line == 10
