"""Shared AST classes for the parser, validator, and interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field


# Every node records where it starts in the PayScript source file.
# Line and column numbers start at 1.
@dataclass(frozen=True, kw_only=True)
class Node:
    line: int
    col: int


# Expressions represent values, names, and calculations.
@dataclass(frozen=True, kw_only=True)
class Expr(Node):
    pass


# Statements represent commands and declarations.
@dataclass(frozen=True, kw_only=True)
class Stmt(Node):
    pass


# The program holds all statements in their original source order.
@dataclass(frozen=True, kw_only=True)
class Program(Node):
    statements: list[Stmt] = field(default_factory=list)

# A fixed value: number, text, or boolean.
# Percentages are already converted by the lexer: 20% becomes 0.20.
@dataclass(frozen=True, kw_only=True)
class Literal(Expr):
    value: int | float | str | bool


# A name reference, such as maria, bonus, or employees.
@dataclass(frozen=True, kw_only=True)
class Name(Expr):
    name: str


# Reading a field, such as maria.salary or employees[i].net.
@dataclass(frozen=True, kw_only=True)
class FieldAccess(Expr):
    base: Expr
    field_name: str


# Reading an array item, such as perks[1].
# PayScript uses 1-based indexing; the interpreter handles that.
@dataclass(frozen=True, kw_only=True)
class IndexAccess(Expr):
    base: Expr
    index: Expr


# An array written in the program, such as [500, 300, 200].
@dataclass(frozen=True, kw_only=True)
class ArrayLiteral(Expr):
    items: list[Expr] = field(default_factory=list)


# An operator with one operand, such as -500 or NOT ready.
@dataclass(frozen=True, kw_only=True)
class UnaryExpr(Expr):
    operator: str
    operand: Expr


# An operator with two operands, such as salary + bonus.
# Store operators as their source text: "+", "=", "AND", etc.
@dataclass(frozen=True, kw_only=True)
class BinaryExpr(Expr):
    left: Expr
    operator: str
    right: Expr


# A function call, including INPUT(...) and LENGTH(...).
@dataclass(frozen=True, kw_only=True)
class CallExpr(Expr):
    name: str
    arguments: list[Expr] = field(default_factory=list)

# One field inside COMPANY or EMPLOYEE, such as salary 22000.
# A list of entries preserves their order and individual locations.
@dataclass(frozen=True, kw_only=True)
class FieldEntry(Node):
    name: str
    value: Literal


# Company settings, such as working_days and hours_per_day.
@dataclass(frozen=True, kw_only=True)
class CompanyDecl(Stmt):
    fields: list[FieldEntry] = field(default_factory=list)


# An employee declaration and its fields.
# Required fields will be checked by the validator later.
@dataclass(frozen=True, kw_only=True)
class EmployeeDecl(Stmt):
    handle: str
    fields: list[FieldEntry] = field(default_factory=list)


# Assignment, such as SET bonus TO 500.
# The grammar permits a name or an indexed name as the target.
@dataclass(frozen=True, kw_only=True)
class SetStmt(Stmt):
    target: Name | IndexAccess
    value: Expr


# A payroll command: ADD, EXEMPT, CONTRIBUTE, or LESS.
# Store kind as the uppercase keyword, such as "ADD".
@dataclass(frozen=True, kw_only=True)
class PayStmt(Stmt):
    kind: str
    target: Name | IndexAccess
    label: Literal
    amount: Expr


# A request to write an employee's payslip.
@dataclass(frozen=True, kw_only=True)
class PayslipStmt(Stmt):
    target: Name | IndexAccess


# Screen output, such as PRINT maria.name, maria.net.
@dataclass(frozen=True, kw_only=True)
class PrintStmt(Stmt):
    items: list[Expr] = field(default_factory=list)

# One IF or ELSE IF branch, with its condition and statements.
@dataclass(frozen=True, kw_only=True)
class IfBranch(Node):
    condition: Expr
    body: list[Stmt] = field(default_factory=list)


# The complete IF statement.
# branches contains IF first, followed by any ELSE IF branches.
# None means there is no ELSE; an empty list means an empty ELSE.
@dataclass(frozen=True, kw_only=True)
class IfStmt(Stmt):
    branches: list[IfBranch] = field(default_factory=list)
    else_body: list[Stmt] | None = None


# A WHILE loop and the statements inside it.
@dataclass(frozen=True, kw_only=True)
class WhileStmt(Stmt):
    condition: Expr
    body: list[Stmt] = field(default_factory=list)


# Array iteration, such as FOR EACH e IN employees.
# Using a Name node preserves the loop variable's location.
@dataclass(frozen=True, kw_only=True)
class ForEachStmt(Stmt):
    variable: Name
    iterable: Expr
    body: list[Stmt] = field(default_factory=list)


# Numeric iteration, such as FOR EACH i IN 1 -> 3.
# Both endpoints are included when the interpreter runs it.
@dataclass(frozen=True, kw_only=True)
class ForRangeStmt(Stmt):
    variable: Name
    start: Expr
    end: Expr
    body: list[Stmt] = field(default_factory=list)


# A function declaration, its parameters, and its statements.
# Each parameter is a Name node with its own source location.
@dataclass(frozen=True, kw_only=True)
class FunctionDecl(Stmt):
    name: str
    params: list[Name] = field(default_factory=list)
    body: list[Stmt] = field(default_factory=list)


# The value returned by a function.
@dataclass(frozen=True, kw_only=True)
class ReturnStmt(Stmt):
    value: Expr

# A tax bracket: BELOW a limit, ABOVE a limit, or a range.
# BELOW: lower=None, upper=limit (exclusive).
# ABOVE: lower=limit (exclusive), upper=None.
# RANGE: lower=start, upper=end (both inclusive).
@dataclass(frozen=True, kw_only=True)
class TaxBracket(Node):
    kind: str
    lower: Literal | None = None
    upper: Literal | None = None


# The fixed and percentage parts of a tax rate.
# Examples:
# 15%          -> fixed_amount=None, fraction=Literal(value=0.15, ...)
# 1875 + 20%   -> fixed_amount=Literal(value=1875, ...),
#                fraction=Literal(value=0.20, ...)
# 500          -> fixed_amount=Literal(value=500, ...), fraction=None
# None means that part contributes zero.
@dataclass(frozen=True, kw_only=True)
class TaxRate(Node):
    fixed_amount: Literal | None = None
    fraction: Literal | None = None


# One row inside a TAX block.
@dataclass(frozen=True, kw_only=True)
class TaxRow(Node):
    bracket: TaxBracket
    rate: TaxRate


# The complete TAX block, preserving row order.
@dataclass(frozen=True, kw_only=True)
class TaxTable(Stmt):
    rows: list[TaxRow] = field(default_factory=list)