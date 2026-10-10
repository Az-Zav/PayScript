"""Tests for the shared AST structure and source locations."""

from decimal import Decimal

import pytest

from payscript.ast_nodes import (
    FieldAccess,
    ForEachStmt,
    ForRangeStmt,
    FunctionDecl,
    IfBranch,
    IfStmt,
    IndexAccess,
    Literal,
    Name,
    PayStmt,
    PrintStmt,
    Program,
    ReturnStmt,
    TaxBracket,
    TaxRate,
    TaxRow,
    WhileStmt,
)


def test_locations_are_required():
    # Locations must be supplied instead of silently defaulting.
    with pytest.raises(TypeError):
        Name(name="maria")


def test_pay_statement_locations():
    # A command and its children keep their own source locations.
    statement = PayStmt(
        kind="ADD",
        target=Name(name="maria", line=9, col=5),
        label=Literal(value="Bonus", line=9, col=11),
        amount=Literal(value=500, line=9, col=19),
        line=9,
        col=1,
    )

    assert (statement.line, statement.col) == (9, 1)
    assert (statement.target.line, statement.target.col) == (9, 5)
    assert statement.label.value == "Bonus"
    assert statement.label.col == 11
    assert statement.amount.value == 500
    assert statement.amount.col == 19

    first = Program(statements=[statement], line=1, col=1)
    second = Program(line=1, col=1)

    # Different programs must not share a statement list.
    assert first.statements == [statement]
    assert second.statements == []


def test_indexed_employee_field():
    # Nested expressions can represent employees[1].net.
    expression = FieldAccess(
        base=IndexAccess(
            base=Name(name="employees", line=10, col=7),
            index=Literal(value=1, line=10, col=17),
            line=10,
            col=7,
        ),
        field_name="net",
        line=10,
        col=7,
    )

    assert expression.field_name == "net"
    assert expression.base.base.name == "employees"
    assert expression.base.index.value == 1
    assert expression.base.index.col == 17


def test_tax_row_structure():
    # A tax row preserves its bounds and normalized percentage.
    row = TaxRow(
        bracket=TaxBracket(
            kind="RANGE",
            lower=Literal(value=20833, line=8, col=5),
            upper=Literal(value=33333, line=8, col=14),
            line=8,
            col=5,
        ),
        rate=TaxRate(
            fraction=Literal(value=Decimal("0.15"), line=8, col=22),
            line=8,
            col=22,
        ),
        line=8,
        col=5,
    )

    assert row.bracket.lower.value == 20833
    assert row.bracket.upper.value == 33333
    assert row.rate.fixed_amount is None
    assert row.rate.fraction.value == Decimal("0.15")
    assert row.rate.fraction.col == 22


def test_function_with_condition_and_return():
    # A function can contain IF branches and a RETURN statement.
    result = ReturnStmt(value=Literal(value=500, line=8, col=16), line=8, col=9)
    branch = IfBranch(
        condition=Literal(value=True, line=7, col=8),
        body=[result],
        line=7,
        col=5,
    )
    conditional = IfStmt(branches=[branch], else_body=[], line=7, col=5)
    function = FunctionDecl(
        name="bonus",
        params=[Name(name="salary", line=6, col=16)],
        body=[conditional],
        line=6,
        col=1,
    )

    assert function.params[0].name == "salary"
    assert function.params[0].col == 16
    assert function.body[0].branches[0].body[0] is result
    assert conditional.else_body == []
    assert IfStmt(line=1, col=1).else_body is None


def test_loop_structures():
    # Both FOR forms and WHILE preserve their bodies.
    output = PrintStmt(items=[Name(name="i", line=11, col=11)], line=11, col=5)
    numeric_loop = ForRangeStmt(
        variable=Name(name="i", line=10, col=10),
        start=Literal(value=1, line=10, col=15),
        end=Literal(value=3, line=10, col=20),
        body=[output],
        line=10,
        col=1,
    )
    array_loop = ForEachStmt(
        variable=Name(name="e", line=15, col=10),
        iterable=Name(name="employees", line=15, col=15),
        line=15,
        col=1,
    )
    while_loop = WhileStmt(
        condition=Literal(value=False, line=20, col=7),
        body=[numeric_loop],
        line=20,
        col=1,
    )

    assert numeric_loop.start.value == 1
    assert numeric_loop.end.value == 3
    assert numeric_loop.body[0] is output
    assert array_loop.iterable.name == "employees"
    assert array_loop.body == []
    assert while_loop.body[0] is numeric_loop
