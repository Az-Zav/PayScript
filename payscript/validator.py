"""Semantic checks for a PayScript program (the validator).

The parser only checks grammar. This module catches problems the grammar
cannot: undefined names, reserved names, missing fields, bad tax tables, and
so on. It runs between the parser and the interpreter:

    source -> lexer -> parser -> **validator** -> interpreter

Usage:
    >>> from payscript.validator import validate
    >>> validate(program)   # returns None if the program is fine

    On the first problem, ``validate`` raises ``PayScriptError`` whose message
    looks like ``Line 4, col 7: message``. Case-only label differences are not
    errors; they emit a ``PayScriptWarning`` and validation continues.

What is checked here (and what is not):
    * Duplicate pay labels on one employee are NOT checked here. They are a
      run-time error, so the same label may appear in different IF branches.
    * Whether ``maria.foo`` is a real field, or whether ``e`` in
      ``EXEMPT e ...`` really holds an employee, is left to the interpreter.

The file is organised top to bottom as:
    1. Constants and the scope record
    2. validate() and the structure pass
    3. The statement pass (one small function per statement type)
    4. Expressions and targets
    5. Labels
    6. Tax table
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from payscript.ast_nodes import (
    ArrayLiteral, BinaryExpr, CallExpr, CompanyDecl, EmployeeDecl, FieldAccess,
    ForEachStmt, ForRangeStmt, FunctionDecl, IfStmt, IndexAccess, Literal, Name,
    PayStmt, PayslipStmt, PrintStmt, Program, ReturnStmt, SetStmt, TaxTable,
    UnaryExpr, WhileStmt,
)
from payscript.errors import PayScriptError


# --- 1. Constants and the scope record -------------------------------------

# Names the user may not use for their own variables, employees or functions.
RESERVED_NAMES = {
    "company", "employees", "daily_rate", "hourly_rate", "minute_rate",
    "absence_deduction", "tardiness_deduction", "basic_pay", "total_add",
    "total_exempt", "total_contribute", "total_less", "gross", "taxable",
    "tax", "net",
}

# Labels PayScript adds to the payslip by itself.
RESERVED_LABELS = {"Basic Pay", "Absences", "Tardiness", "Withholding Tax"}

PAY_COMMANDS = {"ADD", "EXEMPT", "CONTRIBUTE", "LESS"}

# Declarations that are only allowed at the top level of a program.
DECLARATIONS = {
    CompanyDecl: "COMPANY", EmployeeDecl: "EMPLOYEE",
    TaxTable: "TAX", FunctionDecl: "FUNCTION",
}

# Allowed fields in COMPANY / EMPLOYEE blocks: name -> (kind, minimum rule).
#   kind "text"   = must be a string
#   kind "number" = must be an int/float
# The last item says what the number must satisfy: "positive" (> 0) or
# "non-negative" (>= 0). It is ignored for text.
COMPANY_FIELDS = {
    "working_days": ("number", "positive"),
    "hours_per_day": ("number", "positive"),
}
EMPLOYEE_FIELDS = {
    "name": ("text", None),
    "position": ("text", None),
    "salary": ("number", "non-negative"),
    "absences": ("number", "non-negative"),
    "late_minutes": ("number", "non-negative"),
    "overtime_hours": ("number", "non-negative"),
}
COMPANY_REQUIRED = ("working_days", "hours_per_day")
EMPLOYEE_REQUIRED = ("name", "salary")


class PayScriptWarning(UserWarning):
    """A non-fatal problem; validation continues after it is raised.

    Capture it in tests with ``warnings.catch_warnings(record=True)``.
    """


@dataclass
class _Scope:
    """What the program has declared so far at one point in the code.

    Attributes:
        names: Variables, employee handles, loop variables, and parameters
            that may be read here.
        functions: Known function name -> number of parameters. ``None``
            means any number of arguments (used by ``INPUT``).
        employees: Declared employee handles (valid pay targets).
        loop_targets: FOR EACH variables (also valid pay targets).
        in_function: True while checking the body of a function.
    """

    names: set[str] = field(default_factory=lambda: {"employees"})
    functions: dict[str, int | None] = field(
        default_factory=lambda: {"INPUT": None, "LENGTH": 1})
    employees: set[str] = field(default_factory=set)
    loop_targets: set[str] = field(default_factory=set)
    in_function: bool = False

    def copy(self) -> _Scope:
        """Return an independent copy, so a branch or loop cannot leak names."""
        return _Scope(
            names=self.names.copy(), functions=self.functions.copy(),
            employees=self.employees.copy(),
            loop_targets=self.loop_targets.copy(),
            in_function=self.in_function,
        )


# --- 2. validate() and the structure pass ----------------------------------

def validate(program: Program) -> None:
    """Check a program for semantic errors.

    Call this after parsing and before running the interpreter. It also
    accepts hand-built ASTs, so it can be tested without the lexer or parser.

    Args:
        program: The Program AST produced by the parser.

    Returns:
        None if the program is valid.

    Raises:
        PayScriptError: On the first rule violation, with its line and column.

    Warns:
        PayScriptWarning: When two pay labels differ only in upper/lower case.
    """
    companies = [s for s in program.statements if isinstance(s, CompanyDecl)]
    taxes = [s for s in program.statements if isinstance(s, TaxTable)]

    if not companies:
        _error(program, "PROGRAM: Exactly one COMPANY declaration is required.")
    if len(companies) > 1:
        _error(companies[1], "COMPANY: Only one declaration is allowed.")
    if len(taxes) > 1:
        _error(taxes[1], "TAX: Only one declaration is allowed.")

    _check_structure(program.statements, top_level=True)
    _check_statements(program.statements, _Scope(), labels={})


def _error(node, message: str):
    """Raise PayScriptError at the line and column of ``node``."""
    raise PayScriptError(message, node.line, node.col)


def _reserved(node, name: str) -> None:
    """Raise an error if ``name`` is a reserved built-in name."""
    if name in RESERVED_NAMES:
        _error(node, f"NAME: Cannot redefine reserved name '{name}'.")


def _bodies(statement) -> list[list]:
    """Return the nested statement lists inside IF, loops, or a function."""
    if isinstance(statement, IfStmt):
        return [b.body for b in statement.branches] + [statement.else_body or []]
    if isinstance(statement, (WhileStmt, ForEachStmt, ForRangeStmt, FunctionDecl)):
        return [statement.body]
    return []


def _check_structure(statements, top_level: bool = False) -> None:
    """Check placement and naming rules, including inside nested blocks.

    Covers: declarations only at top level, field rules for COMPANY and
    EMPLOYEE, and reserved names. Name *usage* is checked later.

    Args:
        statements: The statement list to check.
        top_level: True only for the program's own statement list.
    """
    for statement in statements:
        keyword = DECLARATIONS.get(type(statement))
        if keyword and not top_level:
            _error(statement,
                   f"{keyword}: Declaration is allowed only at the top level.")

        if isinstance(statement, (CompanyDecl, EmployeeDecl)):
            if isinstance(statement, EmployeeDecl):
                _reserved(statement, statement.handle)
            _check_fields(statement)
        elif isinstance(statement, SetStmt) and isinstance(statement.target, Name):
            _reserved(statement.target, statement.target.name)
        elif isinstance(statement, FunctionDecl):
            _reserved(statement, statement.name)
            for parameter in statement.params:
                _reserved(parameter, parameter.name)
        elif isinstance(statement, (ForEachStmt, ForRangeStmt)):
            _reserved(statement.variable, statement.variable.name)

        for body in _bodies(statement):
            _check_structure(body)


def _check_fields(statement) -> None:
    """Check the fields of a COMPANY or EMPLOYEE block.

    Rules: no unknown fields, no repeated fields, the required fields are
    present, text fields hold text, and number fields hold sensible numbers.

    Args:
        statement: A CompanyDecl or EmployeeDecl.
    """
    if isinstance(statement, CompanyDecl):
        title, allowed, required = "COMPANY", COMPANY_FIELDS, COMPANY_REQUIRED
    else:
        title = f"EMPLOYEE '{statement.handle}'"
        allowed, required = EMPLOYEE_FIELDS, EMPLOYEE_REQUIRED

    seen = set()
    for entry in statement.fields:
        if entry.name not in allowed:
            _error(entry, f"{title}: Unknown field '{entry.name}'.")
        if entry.name in seen:
            _error(entry, f"{title}: Duplicate field '{entry.name}'.")
        seen.add(entry.name)
        _check_field_value(entry, allowed[entry.name], title)

    for name in required:
        if name not in seen:
            _error(statement, f"{title}: Missing required field '{name}'.")


def _check_field_value(entry, rule, title: str) -> None:
    """Check that one field holds text or a number as its rule demands."""
    kind, minimum = rule
    value = entry.value.value
    is_number = type(value) in (int, float)  # bool is not a number here

    if kind == "text" and not isinstance(value, str):
        _error(entry.value, f"{title}: Field '{entry.name}' must be text.")
    if kind == "number":
        if not is_number:
            _error(entry.value, f"{title}: Field '{entry.name}' must be a number.")
        if minimum == "positive" and value <= 0:
            _error(entry.value,
                   f"{title}: Field '{entry.name}' must be greater than 0.")
        if minimum == "non-negative" and value < 0:
            _error(entry.value,
                   f"{title}: Field '{entry.name}' must not be negative.")


# --- 3. The statement pass -------------------------------------------------

def _check_statements(statements, scope: _Scope, labels: dict) -> None:
    """Check each statement in order, updating ``scope`` as names appear.

    Args:
        statements: The statement list to check.
        scope: Names declared so far (modified in place).
        labels: Pay labels seen so far, per target (modified in place).
    """
    for statement in statements:
        check = _STATEMENT_CHECKS.get(type(statement))
        if check is None:
            _error(statement,
                   f"VALIDATOR: Unsupported statement '{type(statement).__name__}'.")
        check(statement, scope, labels)


def _check_company(statement, scope, labels) -> None:
    """COMPANY: makes the built-in name ``company`` available."""
    scope.names.add("company")


def _check_employee(statement, scope, labels) -> None:
    """EMPLOYEE: declares a new handle (no duplicates)."""
    _new_name(statement, statement.handle, scope)
    scope.names.add(statement.handle)
    scope.employees.add(statement.handle)


def _check_tax_table(statement, scope, labels) -> None:
    """TAX: checks the table's brackets."""
    _check_tax(statement)


def _check_function(statement, scope, labels) -> None:
    """FUNCTION: checks the body in its own scope, then registers the name.

    A function sees only its parameters, its own locals, employee handles and
    the built-ins ``employees`` and ``company`` (``company`` only once COMPANY
    has been declared). Other global variables are not visible. The name is
    registered *after* the body, so recursion and calls to functions declared
    later are rejected.
    """
    _new_name(statement, statement.name, scope)

    parameters = set()
    for parameter in statement.params:
        if parameter.name in parameters:
            _error(parameter, f"FUNCTION: Duplicate parameter '{parameter.name}'.")
        parameters.add(parameter.name)

    builtins = scope.names & {"employees", "company"}
    local = _Scope(
        names=scope.employees | parameters | builtins,
        functions=scope.functions.copy(),
        employees=scope.employees.copy(),
        in_function=True,
    )
    _check_statements(statement.body, local, labels)
    if not _has_return(statement.body):
        _error(statement, f"FUNCTION '{statement.name}': RETURN is required.")

    scope.functions[statement.name] = len(parameters)


def _check_return(statement, scope, labels) -> None:
    """RETURN: only allowed inside a function."""
    if not scope.in_function:
        _error(statement, "RETURN: Allowed only inside a function.")
    _check_expression(statement.value, scope)


def _check_set(statement, scope, labels) -> None:
    """SET: checks the target and value, then declares a new variable."""
    _check_assignment(statement.target, scope)
    # Read the value BEFORE adding the target, so ``SET x TO x + 1`` fails
    # when x does not exist yet.
    _check_expression(statement.value, scope)
    if isinstance(statement.target, Name):
        scope.names.add(statement.target.name)
        scope.loop_targets.discard(statement.target.name)


def _check_print(statement, scope, labels) -> None:
    """PRINT: every item must be a valid expression."""
    for item in statement.items:
        _check_expression(item, scope)


def _check_pay(statement, scope, labels) -> None:
    """ADD / EXEMPT / CONTRIBUTE / LESS: target, label, and amount."""
    if scope.in_function:
        _error(statement, "FUNCTION: Pay commands are not allowed inside a function.")
    if statement.kind not in PAY_COMMANDS:
        _error(statement, f"PAY: Unknown command '{statement.kind}'.")
    _check_target(statement.target, scope)
    _check_label(statement.label, statement.target, labels)
    _check_expression(statement.amount, scope)


def _check_payslip(statement, scope, labels) -> None:
    """PAYSLIP: the target must be an employee."""
    _check_target(statement.target, scope)


def _check_if(statement, scope, labels) -> None:
    """IF / ELSE IF / ELSE: each branch is checked in its own copy of scope.

    A variable first set inside the IF only counts as declared afterwards if
    EVERY branch (including ELSE) sets it.
    """
    paths = []
    for branch in statement.branches:
        _check_expression(branch.condition, scope)
        local = scope.copy()
        _check_statements(branch.body, local, labels)
        paths.append(local)

    else_scope = scope.copy()
    _check_statements(statement.else_body or [], else_scope, labels)
    paths.append(else_scope)

    scope.names.update(set.intersection(*(p.names for p in paths)))
    scope.loop_targets.intersection_update(
        set.intersection(*(p.loop_targets for p in paths)))


def _check_while(statement, scope, labels) -> None:
    """WHILE: the body may run zero times, so its new names do not escape."""
    _check_expression(statement.condition, scope)
    local = scope.copy()
    _check_statements(statement.body, local, labels)
    scope.loop_targets.intersection_update(local.loop_targets)


def _check_for(statement, scope, labels) -> None:
    """FOR EACH (array or range): checks the loop variable, range, and body."""
    variable = statement.variable
    if variable.name in scope.employees:
        _error(variable,
               f"FOR: Loop variable '{variable.name}' cannot reuse an employee handle.")
    if variable.name in scope.functions:
        _error(variable,
               f"FOR: Loop variable '{variable.name}' cannot reuse a function name.")

    is_array_loop = isinstance(statement, ForEachStmt)
    if is_array_loop:
        _check_expression(statement.iterable, scope)
    else:
        _check_expression(statement.start, scope)
        _check_expression(statement.end, scope)
        start, end = _number(statement.start), _number(statement.end)
        if start is not None and end is not None and start > end:
            _error(statement, "FOR: Range start must not be greater than end.")

    local = scope.copy()
    local.names.add(variable.name)
    local.loop_targets.discard(variable.name)
    if is_array_loop:  # only array loop variables can hold an employee
        local.loop_targets.add(variable.name)
    _check_statements(statement.body, local, labels)
    scope.loop_targets.intersection_update(local.loop_targets | {variable.name})


# Which function checks which kind of statement.
_STATEMENT_CHECKS = {
    CompanyDecl: _check_company,
    EmployeeDecl: _check_employee,
    TaxTable: _check_tax_table,
    FunctionDecl: _check_function,
    ReturnStmt: _check_return,
    SetStmt: _check_set,
    PrintStmt: _check_print,
    PayStmt: _check_pay,
    PayslipStmt: _check_payslip,
    IfStmt: _check_if,
    WhileStmt: _check_while,
    ForEachStmt: _check_for,
    ForRangeStmt: _check_for,
}


def _new_name(node, name: str, scope: _Scope) -> None:
    """Raise an error if ``name`` is already used as a name or function."""
    if name in scope.names or name in scope.functions:
        _error(node, f"NAME: Name '{name}' is already declared.")


def _has_return(statements) -> bool:
    """Return True if a RETURN appears anywhere, including nested blocks.

    This does not prove every execution path returns, only that one exists.
    """
    for statement in statements:
        if isinstance(statement, ReturnStmt):
            return True
        if any(_has_return(body) for body in _bodies(statement)):
            return True
    return False


# --- 4. Expressions and targets --------------------------------------------

def _check_expression(expression, scope: _Scope) -> None:
    """Check that every name and function call in an expression is valid.

    The expression is only inspected, never evaluated.

    Args:
        expression: Any Expr node.
        scope: Names and functions available at this point.
    """
    children = []

    if isinstance(expression, Literal):
        return
    if isinstance(expression, Name):
        if expression.name not in scope.names:
            _error(expression,
                   f"NAME: Name '{expression.name}' must be declared before use.")
    elif isinstance(expression, BinaryExpr):
        children = [expression.left, expression.right]
    elif isinstance(expression, UnaryExpr):
        children = [expression.operand]
    elif isinstance(expression, FieldAccess):
        children = [expression.base]
    elif isinstance(expression, IndexAccess):
        children = [expression.base, expression.index]
    elif isinstance(expression, ArrayLiteral):
        children = expression.items
    elif isinstance(expression, CallExpr):
        children = expression.arguments
        _check_call(expression, scope)
    else:
        _error(expression,
               f"VALIDATOR: Unsupported expression '{type(expression).__name__}'.")

    for child in children:
        _check_expression(child, scope)


def _check_call(call: CallExpr, scope: _Scope) -> None:
    """Check that a called function exists and gets the right argument count."""
    if call.name not in scope.functions:
        _error(call, f"FUNCTION: Function '{call.name}' must be declared before use.")
    expected = scope.functions[call.name]
    if expected is not None and len(call.arguments) != expected:
        _error(call, f"FUNCTION '{call.name}': Expected {expected} "
                     f"argument(s), got {len(call.arguments)}.")


def _check_assignment(target, scope: _Scope) -> None:
    """Check the target of a SET.

    Allowed: a plain variable, or an item of a variable (``list[2]``).
    Not allowed: reserved names, employee handles, function names, and
    computed fields (``maria.net``).
    """
    root = target
    while isinstance(root, IndexAccess):
        root = root.base

    if isinstance(root, Name):
        _reserved(root, root.name)
        if root.name in scope.employees or root.name in scope.functions:
            _error(root,
                   f"SET: Cannot replace declared employee or function '{root.name}'.")
        if isinstance(target, IndexAccess):
            _check_expression(target, scope)  # the array and index must exist
    elif isinstance(target, FieldAccess):
        _error(target, f"SET: Field '{target.field_name}' is read-only.")
    elif isinstance(target, IndexAccess):
        _check_expression(target, scope)
    else:
        _error(target, "SET: Target must be a variable or indexed variable.")


def _check_target(target, scope: _Scope) -> None:
    """Check the target of a pay command or PAYSLIP.

    It must be a declared employee handle or a FOR EACH variable. Indexed
    targets such as ``employees[1]`` are accepted here; the interpreter
    confirms at run time that the item really is an employee.
    """
    _check_expression(target, scope)
    if isinstance(target, Name):
        if target.name not in scope.employees | scope.loop_targets:
            _error(target, f"PAY: Target '{target.name}' must be an employee "
                           f"handle or FOR EACH variable.")
    elif not isinstance(target, IndexAccess):
        _error(target, "PAY: Target must be an employee handle or indexed employee item.")


# --- 5. Labels -------------------------------------------------------------

def _check_label(label: Literal, target, labels: dict) -> None:
    """Check a pay label.

    * A non-text label is an error.
    * The four reserved labels (exact spelling) are an error.
    * A label that differs only in case from an earlier label on the SAME
      target gives a PayScriptWarning.
    * Exact duplicates are allowed here; the interpreter rejects them at run time.

    Args:
        label: The Literal holding the label text.
        target: The pay target, used to keep each employee's labels separate.
        labels: Labels seen so far, keyed by target (modified in place).
    """
    value = label.value
    if not isinstance(value, str):
        _error(label, "LABEL: A pay label must be text.")
    if value in RESERVED_LABELS:
        _error(label, f"LABEL: '{value}' is reserved for automatic payslip entries.")

    # Indexed targets (employees[i]) share one bucket because the exact
    # employee is only known at run time.
    key = target.name if isinstance(target, Name) else "<indexed>"
    seen = labels.setdefault(key, set())

    for previous in seen | RESERVED_LABELS:
        if previous != value and previous.casefold() == value.casefold():
            warnings.warn(
                f"Line {label.line}, col {label.col}: LABEL: '{value}' "
                f"differs only in case from '{previous}'.",
                PayScriptWarning, stacklevel=2)
            break
    seen.add(value)


# --- 6. Tax table ----------------------------------------------------------

def _number(expression):
    """Return the number an expression always equals, or None if unknown.

    Handles number literals, unary minus, and ``+ - * /`` between constants.
    Anything that depends on a variable gives None (checked at run time).
    """
    if isinstance(expression, Literal) and type(expression.value) in (int, float):
        return expression.value
    if isinstance(expression, UnaryExpr) and expression.operator == "-":
        value = _number(expression.operand)
        return -value if value is not None else None
    if isinstance(expression, BinaryExpr):
        left, right = _number(expression.left), _number(expression.right)
        if left is None or right is None:
            return None
        if expression.operator == "+":
            return left + right
        if expression.operator == "-":
            return left - right
        if expression.operator == "*":
            return left * right
        if expression.operator == "/" and right != 0:
            return left / right
    return None


def _check_tax(table: TaxTable) -> None:
    """Check every TAX row: sensible bounds and no overlapping brackets.

    Each row becomes an interval ``(low, high, low_included, high_included)``.
    BELOW and ABOVE exclude their limit; RANGE (``a -> b``) includes both ends.

    Raises:
        PayScriptError: For reversed ranges, non-numeric bounds, or overlaps.
    """
    intervals = []
    for row in table.rows:
        bracket = row.bracket
        low, high = _number(bracket.lower), _number(bracket.upper)

        if bracket.kind == "BELOW" and high is not None:
            interval = (float("-inf"), high, False, False)
        elif bracket.kind == "ABOVE" and low is not None:
            interval = (low, float("inf"), False, False)
        elif bracket.kind == "RANGE" and low is not None and high is not None:
            if low > high:
                _error(row, "TAX: Range lower bound must not exceed upper bound.")
            interval = (low, high, True, True)
        else:
            _error(row, "TAX: Bracket bounds must be numeric and match its kind.")

        if any(_overlap(previous, interval) for previous in intervals):
            _error(row, "TAX: Brackets must not overlap.")
        intervals.append(interval)


def _overlap(first: tuple, second: tuple) -> bool:
    """Return True if two intervals share at least one value.

    Args:
        first: ``(low, high, low_included, high_included)``.
        second: Same shape as ``first``.
    """
    low = max(first[0], second[0])
    high = min(first[1], second[1])
    if low != high:
        return low < high  # a real overlap exists only if the gap is positive

    # They touch at exactly one point: overlap only if BOTH include it.
    def includes(interval: tuple) -> bool:
        """Return True if this interval contains the shared point."""
        lower, upper, closed_low, closed_high = interval
        return ((low > lower or (low == lower and closed_low))
                and (low < upper or (low == upper and closed_high)))

    return includes(first) and includes(second)