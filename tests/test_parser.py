"""Parser: one test per grammar construct, plus syntax errors."""

from decimal import Decimal

import pytest

from payscript import ast_nodes as ast
from payscript.errors import PayScriptError

from conftest import parse_source


def stmts(source):
    return parse_source(source).statements


def first_expr(text):
    """Parse `SET x TO <text>` and return the expression node."""
    return stmts(f"SET x TO {text}")[0].value


def syntax_error(source):
    with pytest.raises(PayScriptError) as info:
        parse_source(source)
    return info.value


# ---------- declarations ----------

def test_empty_program():
    assert stmts("") == []
    assert stmts("// only a comment\n\n") == []


def test_company_declaration():
    company = stmts("COMPANY\n working_days 22\n hours_per_day 8\nEND")[0]
    assert isinstance(company, ast.CompanyDecl)
    assert [(f.name, f.value.value) for f in company.fields] == [
        ("working_days", 22), ("hours_per_day", 8)]


def test_employee_declaration_with_text_and_number_fields():
    emp = stmts('EMPLOYEE juan\n name "Juan"\n salary 25000\nEND')[0]
    assert isinstance(emp, ast.EmployeeDecl)
    assert emp.handle == "juan"
    assert [(f.name, f.value.value) for f in emp.fields] == [
        ("name", "Juan"), ("salary", 25000)]


def test_blank_lines_inside_a_declaration_are_allowed():
    emp = stmts('EMPLOYEE a\n\n name "A"\n\n salary 1\nEND')[0]
    assert len(emp.fields) == 2


def test_tax_table_all_bracket_kinds_and_rates():
    table = stmts("TAX\n BELOW 100 = 0%\n 100 -> 200 = 15%\n"
                  " ABOVE 200 = 50 + 20%\n ABOVE 900 = 7\nEND")[0]
    assert isinstance(table, ast.TaxTable)
    assert [row.bracket.kind for row in table.rows] == [
        "BELOW", "RANGE", "ABOVE", "ABOVE"]
    _, rng, above, fixed = table.rows
    assert (rng.bracket.lower.value, rng.bracket.upper.value) == (100, 200)
    assert rng.rate.fraction.value == Decimal("0.15")
    assert above.rate.fixed_amount.value == 50
    assert above.rate.fraction.value == Decimal("0.20")
    assert fixed.rate.fixed_amount.value == 7 and fixed.rate.fraction is None


def test_function_declaration():
    fn = stmts("FUNCTION bonus(a, b)\n RETURN a + b\nEND")[0]
    assert isinstance(fn, ast.FunctionDecl)
    assert fn.name == "bonus"
    assert [p.name for p in fn.params] == ["a", "b"]
    assert isinstance(fn.body[0], ast.ReturnStmt)


def test_function_without_parameters():
    assert stmts("FUNCTION five()\n RETURN 5\nEND")[0].params == []


# ---------- pay commands and output ----------

@pytest.mark.parametrize("kind", ["ADD", "EXEMPT", "CONTRIBUTE", "LESS"])
def test_pay_commands(kind):
    node = stmts(f'{kind} maria "Label" 100')[0]
    assert isinstance(node, ast.PayStmt)
    assert node.kind == kind
    assert node.target.name == "maria"
    assert node.label.value == "Label"
    assert node.amount.value == 100


def test_pay_command_with_indexed_target():
    node = stmts('ADD employees[2] "Bonus" 5')[0]
    assert isinstance(node.target, ast.IndexAccess)
    assert node.target.index.value == 2


def test_payslip_statement():
    node = stmts("PAYSLIP maria")[0]
    assert isinstance(node, ast.PayslipStmt) and node.target.name == "maria"


def test_print_with_several_items():
    node = stmts('PRINT "a", 1, x')[0]
    assert isinstance(node, ast.PrintStmt) and len(node.items) == 3


def test_set_to_variable_and_to_indexed_target():
    assert isinstance(stmts("SET x TO 1")[0].target, ast.Name)
    assert isinstance(stmts("SET xs[1] TO 1")[0].target, ast.IndexAccess)


# ---------- control flow ----------

def test_if_else_if_else():
    node = stmts("IF a THEN\n PRINT 1\nELSE IF b THEN\n PRINT 2\n"
                 "ELSE\n PRINT 3\nEND")[0]
    assert isinstance(node, ast.IfStmt)
    assert len(node.branches) == 2
    assert len(node.else_body) == 1


def test_if_without_else_has_no_else_body():
    assert stmts("IF a THEN\n PRINT 1\nEND")[0].else_body is None


def test_while():
    node = stmts("WHILE a < 3\n SET a TO a + 1\nEND")[0]
    assert isinstance(node, ast.WhileStmt) and len(node.body) == 1


def test_for_each_and_for_range():
    each = stmts("FOR EACH e IN employees\n PRINT e.name\nEND")[0]
    rng = stmts("FOR EACH i IN 1 -> 3\n PRINT i\nEND")[0]
    assert isinstance(each, ast.ForEachStmt) and each.variable.name == "e"
    assert isinstance(rng, ast.ForRangeStmt)
    assert (rng.start.value, rng.end.value) == (1, 3)


def test_nested_blocks():
    node = stmts("WHILE a\n IF b THEN\n  PRINT 1\n END\nEND")[0]
    assert isinstance(node.body[0], ast.IfStmt)


# ---------- expressions ----------

def test_literals():
    assert first_expr("5").value == 5
    assert first_expr("1.5").value == 1.5
    assert first_expr("10%").value == Decimal("0.1")
    assert first_expr('"hi"').value == "hi"
    assert first_expr("TRUE").value is True
    assert first_expr("FALSE").value is False


def test_precedence_multiplication_over_addition():
    e = first_expr("1 + 2 * 3")
    assert e.operator == "+" and e.right.operator == "*"


def test_parentheses_override_precedence():
    e = first_expr("(1 + 2) * 3")
    assert e.operator == "*" and e.left.operator == "+"


def test_subtraction_is_left_associative():
    e = first_expr("10 - 3 - 2")
    assert e.operator == "-" and e.left.operator == "-"


def test_logic_precedence_not_and_or():
    e = first_expr("NOT a AND b OR c")
    assert e.operator == "OR"
    assert e.left.operator == "AND"
    assert isinstance(e.left.left, ast.UnaryExpr)


@pytest.mark.parametrize("op", ["=", "!=", "<", "<=", ">", ">="])
def test_comparison_operators(op):
    assert first_expr(f"a {op} b").operator == op


def test_unary_minus():
    e = first_expr("-5")
    assert isinstance(e, ast.UnaryExpr) and e.operator == "-"


def test_postfix_field_and_index_chain():
    e = first_expr("employees[1].net")
    assert isinstance(e, ast.FieldAccess) and e.field_name == "net"
    assert isinstance(e.base, ast.IndexAccess)


def test_array_literal_including_empty_and_multiline():
    assert len(first_expr("[1, 2, 3]").items) == 3
    assert first_expr("[]").items == []
    assert len(first_expr("[1,\n 2]").items) == 2


def test_calls_user_input_and_length():
    user = first_expr("bonus(1, 2)")
    assert isinstance(user, ast.CallExpr) and len(user.arguments) == 2
    assert first_expr('INPUT("x")').name == "INPUT"
    assert first_expr("LENGTH(employees)").name == "LENGTH"


def test_source_locations_are_recorded():
    node = stmts("\n\n  SET x TO 1")[0]
    assert (node.line, node.col) == (3, 3)


# ---------- syntax errors ----------

@pytest.mark.parametrize("source", [
    "IF a\n PRINT 1\nEND",                 # missing THEN
    "IF a THEN\n PRINT 1",                 # missing END
    "WHILE a\n PRINT 1",                   # missing END
    "COMPANY\n working_days 22",           # unterminated declaration
    "SET x 1",                             # missing TO
    "SET TO 1",                            # missing target
    "ADD maria 500",                       # missing label
    'ADD maria "L"',                       # missing amount
    "PAYSLIP",                             # missing target
    "PRINT",                               # nothing to print
    "SET x TO 1 +",                        # dangling operator
    "SET x TO (1 + 2",                     # unclosed paren
    "SET x TO [1, 2",                      # unclosed bracket
    "SET x TO 1 2",                        # two values
    "FUNCTION f(\n RETURN 1\nEND",         # broken parameter list
    "FOR EACH IN employees\nEND",          # missing loop variable
    "END",                                 # stray END
    "ELSE",                                # stray ELSE
    "RETURN",                              # RETURN without value
    'EMPLOYEE\n name "x"\nEND',            # missing handle
    "TAX\n BELOW = 0%\nEND",               # missing bound
    "x",                                   # bare identifier is not a statement
    "5",                                   # bare number
])
def test_syntax_errors_are_reported_with_a_location(source):
    err = syntax_error(source)
    assert err.line >= 1 and err.col >= 1
    assert str(err).startswith(f"Line {err.line}, col {err.col}: ")


def test_syntax_error_points_at_the_offending_line():
    assert syntax_error("IF a\n PRINT 1\nEND").line == 1
