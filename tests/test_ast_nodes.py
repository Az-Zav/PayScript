"""Tests for the shared AST structure and source locations."""

import unittest

from payscript.ast_nodes import (
    FieldAccess,
    IndexAccess,
    Literal,
    Name,
    PayStmt,
    Program,
    TaxBracket,
    TaxRate,
    TaxRow,
)


class AstNodeTests(unittest.TestCase):
    # Locations must be supplied instead of silently defaulting.
    def test_locations_are_required(self):
        with self.assertRaises(TypeError):
            Name(name="maria")


    # A command and its children keep their own source locations.
    def test_pay_statement_locations(self):
        statement = PayStmt(
            kind="ADD",
            target=Name(name="maria", line=9, col=5),
            label=Literal(value="Bonus", line=9, col=11),
            amount=Literal(value=500, line=9, col=19),
            line=9,
            col=1,
        )

        self.assertEqual((statement.line, statement.col), (9, 1))
        self.assertEqual((statement.target.line, statement.target.col), (9, 5))
        self.assertEqual(statement.label.value, "Bonus")
        self.assertEqual(statement.label.col, 11)
        self.assertEqual(statement.amount.value, 500)
        self.assertEqual(statement.amount.col, 19)

        first = Program(statements=[statement], line=1, col=1)
        second = Program(line=1, col=1)

        # Different programs must not share a statement list.
        self.assertEqual(first.statements, [statement])
        self.assertEqual(second.statements, [])


    # Nested expressions can represent employees[1].net.
    def test_indexed_employee_field(self):
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

        self.assertEqual(expression.field_name, "net")
        self.assertEqual(expression.base.base.name, "employees")
        self.assertEqual(expression.base.index.value, 1)
        self.assertEqual(expression.base.index.col, 17)


    # A tax row preserves its bounds and normalized percentage.
    def test_tax_row_structure(self):
        row = TaxRow(
            bracket=TaxBracket(
                kind="RANGE",
                lower=Literal(value=20833, line=8, col=5),
                upper=Literal(value=33333, line=8, col=14),
                line=8,
                col=5,
            ),
            rate=TaxRate(
                fraction=Literal(value=0.15, line=8, col=22),
                line=8,
                col=22,
            ),
            line=8,
            col=5,
        )

        self.assertEqual(row.bracket.lower.value, 20833)
        self.assertEqual(row.bracket.upper.value, 33333)
        self.assertIsNone(row.rate.fixed_amount)
        self.assertAlmostEqual(row.rate.fraction.value, 0.15)
        self.assertEqual(row.rate.fraction.col, 22)

    # A function can contain IF branches and a RETURN statement.
    def test_function_with_condition_and_return(self):
        from payscript.ast_nodes import (
            FunctionDecl, IfBranch, IfStmt, ReturnStmt,
        )

        result = ReturnStmt(
            value=Literal(value=500, line=8, col=16),
            line=8,
            col=9,
        )

        branch = IfBranch(
            condition=Literal(value=True, line=7, col=8),
            body=[result],
            line=7,
            col=5,
        )

        conditional = IfStmt(
            branches=[branch],
            else_body=[],
            line=7,
            col=5,
        )

        function = FunctionDecl(
            name="bonus",
            params=[Name(name="salary", line=6, col=16)],
            body=[conditional],
            line=6,
            col=1,
        )

        self.assertEqual(function.params[0].name, "salary")
        self.assertEqual(function.params[0].col, 16)
        self.assertIs(function.body[0].branches[0].body[0], result)
        self.assertEqual(conditional.else_body, [])
        self.assertIsNone(IfStmt(line=1, col=1).else_body)


    # Both FOR forms and WHILE preserve their bodies.
    def test_loop_structures(self):
        from payscript.ast_nodes import (
            ForEachStmt, ForRangeStmt, PrintStmt, WhileStmt,
        )

        output = PrintStmt(
            items=[Name(name="i", line=11, col=11)],
            line=11,
            col=5,
        )

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

        self.assertEqual(numeric_loop.start.value, 1)
        self.assertEqual(numeric_loop.end.value, 3)
        self.assertIs(numeric_loop.body[0], output)
        self.assertEqual(array_loop.iterable.name, "employees")
        self.assertEqual(array_loop.body, [])
        self.assertIs(while_loop.body[0], numeric_loop)


if __name__ == "__main__":
    unittest.main()
