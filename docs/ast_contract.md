# PayScript AST Contract

Status: Implemented and in use by the parser, validator and interpreter.

## Import and construction

Import the shared classes from `payscript.ast_nodes`.
Use keyword arguments when constructing nodes:

```python
from payscript.ast_nodes import Literal, Name, PayStmt

statement = PayStmt(
    kind="ADD",
    target=Name(name="maria", line=9, col=5),
    label=Literal(value="Bonus", line=9, col=11),
    amount=Literal(value=500, line=9, col=19),
    line=9,
    col=1,
)
```

The parser creates these nodes, the validator checks them and the
interpreter reads them to execute the program.
Do not create separate copies of these classes.

## Source locations

Every node requires `line` and `col`, starting at 1.
Use locations from the original PayScript source, not Python files.

- Statements and declarations: opening keyword.
- Names and literals: their token's start.
- FieldEntry: field-name token.
- Compound expressions: first token of the expression.
- IfBranch: IF or ELSE keyword beginning that branch.
- TaxRow and TaxBracket: first bracket token.
- TaxRate: first rate token after `=`.
- Program: first statement's location, or (1, 1) when empty.
- Each child node retains its own location.

The location attribute is `col`, not `column`.

## Class fields

All classes also inherit `line` and `col`.

| Class | Additional fields |
|---|---|
| Program | statements |
| Literal | value |
| Name | name |
| FieldAccess | base, field_name |
| IndexAccess | base, index |
| ArrayLiteral | items |
| UnaryExpr | operator, operand |
| BinaryExpr | left, operator, right |
| CallExpr | name, arguments |
| FieldEntry | name, value |
| CompanyDecl | fields |
| EmployeeDecl | handle, fields |
| SetStmt | target, value |
| PayStmt | kind, target, label, amount |
| PayslipStmt | target |
| PrintStmt | items |
| IfBranch | condition, body |
| IfStmt | branches, else_body |
| WhileStmt | condition, body |
| ForEachStmt | variable, iterable, body |
| ForRangeStmt | variable, start, end, body |
| FunctionDecl | name, params, body |
| ReturnStmt | value |
| TaxBracket | kind, lower, upper |
| TaxRate | fixed_amount, fraction |
| TaxRow | bracket, rate |
| TaxTable | rows |

Node, Expr, and Stmt are base classes.

## Representation conventions

- Keep statements, fields, arguments, and tax rows in source order.
- Declaration fields are lists of FieldEntry nodes, not dictionaries.
- Function parameters and loop variables are Name nodes.
- Operators use source text: "+", "=", "AND", "NOT", etc.
- PayStmt.kind is "ADD", "EXEMPT", "CONTRIBUTE", or "LESS".
- PayStmt.label is a Literal containing text without surrounding quotes.
- Numbers are `int` (whole numbers) or `decimal.Decimal` (fractions), matching
  the token contract. The interpreter also accepts a hand-built `float` and
  converts it to `Decimal`.
- Percentages are already normalized: 20% is 0.20.
  Do not divide by 100 again.
- TRUE and FALSE become Python True and False.
- IfStmt.branches stores IF first, then ELSE IF branches.
- else_body=None means no ELSE; [] means an empty ELSE.
- FOR over an array uses ForEachStmt.
- FOR over a numeric range uses ForRangeStmt.
- Array indices retain PayScript's 1-based values.
- SET and payroll targets use Name or IndexAccess, matching the EBNF.
  The validator accepts an indexed payroll target (employees[1]); the
  interpreter confirms at run time that the item really is an employee.

## Tax representation

TaxBracket.kind is "BELOW", "ABOVE", or "RANGE".

- BELOW: lower=None, upper=limit; upper is exclusive.
- ABOVE: lower=limit, upper=None; lower is exclusive.
- RANGE: lower=start, upper=end; both ends are inclusive.

Bounds are Literal nodes.

TaxRate parts are Literal nodes, with None meaning zero:

- 15%: fixed_amount=None, fraction=Decimal("0.15").
- 1875 + 20%: fixed_amount=1875, fraction=Decimal("0.20").
- 500: fixed_amount=500, fraction=None.

The numbers above describe Literal.value.

## Responsibilities and limits

AST classes store structure; they do not validate or calculate payroll.
Type annotations do not enforce PayScript's semantic rules at runtime.

Nodes use frozen dataclasses, preventing attribute reassignment.
Their lists remain mutable; consumers should treat completed trees as read-only.

Use the shared PayScriptError(message, line, col) from payscript.errors.

## Tests

Install the dev extras in the project environment (`pip install -e ".[dev]"`),
then run:

```text
python -m pytest tests/test_ast_nodes.py -v
```

These tests cover construction and structure, not full pipeline execution.
The full suite is `python -m pytest`.