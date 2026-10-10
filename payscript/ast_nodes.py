"""Shared AST (Abstract Syntax Tree) classes for PayScript.

The AST is the "clean in-memory form" of a PayScript program. Each stage of
the pipeline uses it differently:

    Parser       builds these nodes from tokens.
    Validator    reads them and raises PayScriptError for rule violations.
    Interpreter  reads them and runs the program.

Building nodes (parser):
    Always use keyword arguments, and always give a 1-based ``line`` and
    ``col`` taken from the original PayScript source (not the Python file).

    >>> name = Name(name="bonus", line=1, col=5)
    >>> program = Program(statements=[], line=1, col=1)

    Put all top-level commands inside ``Program(statements=[...])``, then pass
    that Program to ``validate(program)``.

Note:
    Nodes are frozen dataclasses, so you cannot reassign an attribute after
    creation. The lists inside them can still be changed, so treat a finished
    tree as read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


# --- 1. Base classes -------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class Node:
    """Base class of every AST node; remembers where it starts in the source.

    Attributes:
        line: 1-based line number in the PayScript source.
        col: 1-based column number in the PayScript source.
    """

    line: int
    col: int


@dataclass(frozen=True, kw_only=True)
class Expr(Node):
    """Base class for expressions, which produce a value (e.g. ``salary + 5``)."""


@dataclass(frozen=True, kw_only=True)
class Stmt(Node):
    """Base class for statements, which do something (e.g. ``PRINT``, ``IF``)."""


@dataclass(frozen=True, kw_only=True)
class Program(Node):
    """The whole program: top-level statements in the order they were written.

    Attributes:
        statements: Top-level statements, in source order.
    """

    statements: list[Stmt] = field(default_factory=list)


# --- 2. Expressions and value access ---------------------------------------

@dataclass(frozen=True, kw_only=True)
class Literal(Expr):
    """A fixed value written directly in the program.

    Percentages are already converted by the lexer, so ``20%`` is ``0.20``.
    ``TRUE`` and ``FALSE`` are the Python values ``True`` and ``False``.

    Attributes:
        value: The number, text (without quotes), or boolean.
    """

    value: int | Decimal | str | bool


@dataclass(frozen=True, kw_only=True)
class Name(Expr):
    """A reference to a variable, employee handle, or loop variable.

    Stores only the spelling (e.g. ``"maria"``), not the value it refers to.

    Attributes:
        name: The identifier as written.
    """

    name: str


@dataclass(frozen=True, kw_only=True)
class FieldAccess(Expr):
    """Reading a field with a dot, e.g. ``maria.salary``.

    Attributes:
        base: The expression before the dot (e.g. ``Name("maria")``).
        field_name: The field after the dot (e.g. ``"salary"``).
    """

    base: Expr
    field_name: str


@dataclass(frozen=True, kw_only=True)
class IndexAccess(Expr):
    """Reading an array item with brackets, e.g. ``perks[1]``.

    PayScript counts from 1; the interpreter handles that.

    Attributes:
        base: The array expression (e.g. ``Name("perks")``).
        index: The position expression (e.g. ``Literal(1)``).
    """

    base: Expr
    index: Expr


@dataclass(frozen=True, kw_only=True)
class ArrayLiteral(Expr):
    """An array written in the program, e.g. ``[500, 300, 200]``.

    Attributes:
        items: The item expressions, in source order.
    """

    items: list[Expr] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class UnaryExpr(Expr):
    """An operator with one operand, e.g. ``-500`` or ``NOT ready``.

    Attributes:
        operator: The operator exactly as written (``"-"`` or ``"NOT"``).
        operand: The expression the operator applies to.
    """

    operator: str
    operand: Expr


@dataclass(frozen=True, kw_only=True)
class BinaryExpr(Expr):
    """An operator with two operands, e.g. ``salary + bonus``.

    Attributes:
        left: The expression on the left.
        operator: The operator exactly as written (``"+"``, ``"="``, ``"AND"``...).
        right: The expression on the right.
    """

    left: Expr
    operator: str
    right: Expr


@dataclass(frozen=True, kw_only=True)
class CallExpr(Expr):
    """A function call, including the built-ins ``INPUT(...)`` and ``LENGTH(...)``.

    Attributes:
        name: The function name as written.
        arguments: The argument expressions, in source order.
    """

    name: str
    arguments: list[Expr] = field(default_factory=list)


# --- 3. Declarations and simple commands -----------------------------------

@dataclass(frozen=True, kw_only=True)
class FieldEntry(Node):
    """One line inside a COMPANY or EMPLOYEE block, e.g. ``salary 22000``.

    Its line/col point at the field name.

    Attributes:
        name: The field name (e.g. ``"salary"``).
        value: The number or text written after the name.
    """

    name: str
    value: Literal


@dataclass(frozen=True, kw_only=True)
class CompanyDecl(Stmt):
    """The ``COMPANY ... END`` block.

    Attributes:
        fields: The field lines, in source order. The validator checks that the
            required ones (``working_days``, ``hours_per_day``) are present.
    """

    fields: list[FieldEntry] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class EmployeeDecl(Stmt):
    """An ``EMPLOYEE handle ... END`` block (before defaults or computed values).

    Attributes:
        handle: The short name used in code (e.g. ``"maria"``).
        fields: The field lines, in source order.
    """

    handle: str
    fields: list[FieldEntry] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class SetStmt(Stmt):
    """``SET target TO value``.

    Attributes:
        target: The variable (or array item) being assigned.
        value: The expression whose result is stored.
    """

    target: Name | IndexAccess
    value: Expr


@dataclass(frozen=True, kw_only=True)
class PayStmt(Stmt):
    """A pay command, e.g. ``ADD maria "Bonus" 500``.

    Attributes:
        kind: ``"ADD"``, ``"EXEMPT"``, ``"CONTRIBUTE"``, or ``"LESS"``.
        target: The employee (a handle, or a FOR EACH variable).
        label: The quoted label, as a Literal without the quotes.
        amount: The expression for the amount.
    """

    kind: str
    target: Name | IndexAccess
    label: Literal
    amount: Expr


@dataclass(frozen=True, kw_only=True)
class PayslipStmt(Stmt):
    """``PAYSLIP target``: write one employee's payslip file.

    Attributes:
        target: The employee to write the payslip for.
    """

    target: Name | IndexAccess


@dataclass(frozen=True, kw_only=True)
class PrintStmt(Stmt):
    """``PRINT a, b, ...``: show values on screen.

    Attributes:
        items: The expressions to print, in source order. The interpreter
            formats them and joins them with a single space.
    """

    items: list[Expr] = field(default_factory=list)


# --- 4. Conditions, loops, and functions -----------------------------------

@dataclass(frozen=True, kw_only=True)
class IfBranch(Node):
    """One ``IF`` or ``ELSE IF`` condition together with its body.

    Attributes:
        condition: The expression that must be true for this branch to run.
        body: The statements inside the branch.
    """

    condition: Expr
    body: list[Stmt] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class IfStmt(Stmt):
    """An ``IF`` statement with optional ``ELSE IF`` and ``ELSE`` parts.

    Attributes:
        branches: The IF branch first, then any ELSE IF branches.
        else_body: Statements of the ELSE part. ``None`` means no ELSE was
            written; ``[]`` means an ELSE with an empty body.
    """

    branches: list[IfBranch] = field(default_factory=list)
    else_body: list[Stmt] | None = None


@dataclass(frozen=True, kw_only=True)
class WhileStmt(Stmt):
    """``WHILE condition ... END``.

    Attributes:
        condition: Checked before each repeat.
        body: The statements to repeat while the condition is true.
    """

    condition: Expr
    body: list[Stmt] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ForEachStmt(Stmt):
    """``FOR EACH x IN array ... END``: loop over the items of an array.

    Attributes:
        variable: The loop variable, available inside the body.
        iterable: The array expression (e.g. ``Name("employees")``).
        body: The statements to repeat.
    """

    variable: Name
    iterable: Expr
    body: list[Stmt] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ForRangeStmt(Stmt):
    """``FOR EACH x IN a -> b ... END``: count from a to b, both included.

    Attributes:
        variable: The loop variable, available inside the body.
        start: The first number.
        end: The last number (included).
        body: The statements to repeat.
    """

    variable: Name
    start: Expr
    end: Expr
    body: list[Stmt] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class FunctionDecl(Stmt):
    """A ``FUNCTION name(params) ... END`` definition (not executed here).

    Attributes:
        name: The function name.
        params: The parameters, as Name nodes.
        body: The statements inside the function.
    """

    name: str
    params: list[Name] = field(default_factory=list)
    body: list[Stmt] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ReturnStmt(Stmt):
    """``RETURN value``: give a value back from the current function.

    Attributes:
        value: The expression to return.
    """

    value: Expr


# --- 5. Tax table ----------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class TaxBracket(Node):
    """The left side of a TAX row, e.g. ``BELOW 20833`` or ``20833 -> 33333``.

    Attributes:
        kind: ``"BELOW"``, ``"ABOVE"``, or ``"RANGE"``.
        lower: Lower limit (``ABOVE`` and ``RANGE`` only; otherwise ``None``).
        upper: Upper limit (``BELOW`` and ``RANGE`` only; otherwise ``None``).

    BELOW and ABOVE do not include their limit; RANGE includes both ends.
    """

    kind: str
    lower: Literal | None = None
    upper: Literal | None = None


@dataclass(frozen=True, kw_only=True)
class TaxRate(Node):
    """The right side of a TAX row, e.g. ``15%`` or ``1875 + 20%``.

    ``None`` counts as zero. ``15%`` has ``fraction=0.15`` and no fixed amount;
    ``1875 + 20%`` has ``fixed_amount=1875`` and ``fraction=0.20``.

    Attributes:
        fixed_amount: A fixed peso amount added first.
        fraction: The percentage as a fraction (already divided by 100).
    """

    fixed_amount: Literal | None = None
    fraction: Literal | None = None


@dataclass(frozen=True, kw_only=True)
class TaxRow(Node):
    """One line of the TAX table: a bracket and the rate that applies in it.

    Attributes:
        bracket: Which incomes this row covers.
        rate: The tax rate for that bracket.
    """

    bracket: TaxBracket
    rate: TaxRate


@dataclass(frozen=True, kw_only=True)
class TaxTable(Stmt):
    """The ``TAX ... END`` block.

    Attributes:
        rows: The rows in source order. The validator checks for overlaps.
    """

    rows: list[TaxRow] = field(default_factory=list)