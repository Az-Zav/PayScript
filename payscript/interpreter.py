"""Execution and payslip generation for PayScript programs.

The interpreter walks the AST from payscript.ast_nodes and runs it top to
bottom. Payroll fields (basic_pay, gross, tax, net, ...) are computed every
time they are read, so PRINT before and after an ADD can show different values.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from payscript.ast_nodes import (
    ArrayLiteral,
    BinaryExpr,
    CallExpr,
    CompanyDecl,
    EmployeeDecl,
    FieldAccess,
    ForEachStmt,
    ForRangeStmt,
    FunctionDecl,
    IfStmt,
    IndexAccess,
    Literal,
    Name,
    PayslipStmt,
    PayStmt,
    PrintStmt,
    Program,
    ReturnStmt,
    SetStmt,
    TaxTable,
    UnaryExpr,
    WhileStmt,
)
from payscript.errors import PayScriptError


PAY_KINDS = ("ADD", "EXEMPT", "CONTRIBUTE", "LESS")
RESERVED_LABELS = {"Basic Pay", "Absences", "Tardiness", "Overtime",
                   "Withholding Tax"}

# Optional employee fields and their defaults.
EMPLOYEE_DEFAULTS = {
    "position": "",
    "absences": 0,
    "late_minutes": 0,
    "overtime_hours": 0,
}

MAX_CALL_DEPTH = 100

# Overtime is paid at 125% of the hourly rate (ordinary-day overtime).
OVERTIME_MULTIPLIER = Decimal("1.25")

CENTAVO = Decimal("0.01")


# ===================== RUNTIME OBJECTS =====================

class Company:
    def __init__(self, fields):
        self.fields = {name: normalize(value) for name, value in fields.items()}

    def get(self, field_name, node):
        if field_name not in self.fields:
            raise PayScriptError(f"company has no field '{field_name}'", node.line, node.col)
        return self.fields[field_name]


class Employee:
    def __init__(self, handle, fields, interpreter):
        self.handle = handle
        self.fields = {
            name: normalize(value)
            for name, value in {**EMPLOYEE_DEFAULTS, **fields}.items()
        }
        self.interpreter = interpreter
        # Pay lines in the order they were added: kind -> [(label, amount)].
        self.items = {kind: [] for kind in PAY_KINDS}

    # ---------- pay commands ----------

    def add_item(self, kind, label, amount, node):
        if label in RESERVED_LABELS:
            raise PayScriptError(
                f'"{label}" is a reserved label and cannot be used', node.line, node.col
            )
        for lines in self.items.values():
            if any(existing == label for existing, _ in lines):
                raise PayScriptError(
                    f'Duplicate label "{label}" for employee {self.handle}',
                    node.line, node.col,
                )
        self.items[kind].append((label, amount))

    def total(self, kind):
        return sum((amount for _, amount in self.items[kind]), Decimal(0))

    # ---------- computed fields ----------

    def _company(self, node):
        company = self.interpreter.company
        if company is None:
            raise PayScriptError("COMPANY must be declared before computing pay", node.line, node.col)
        return company

    def daily_rate(self, node):
        working_days = self._company(node).get("working_days", node)
        if working_days == 0:
            raise PayScriptError("Division by zero: company.working_days is 0", node.line, node.col)
        return Decimal(self.fields["salary"]) / Decimal(working_days)

    def hourly_rate(self, node):
        hours_per_day = self._company(node).get("hours_per_day", node)
        if hours_per_day == 0:
            raise PayScriptError("Division by zero: company.hours_per_day is 0", node.line, node.col)
        return self.daily_rate(node) / Decimal(hours_per_day)

    def minute_rate(self, node):
        return self.hourly_rate(node) / 60

    def absence_deduction(self, node):
        return money(self.fields["absences"] * self.daily_rate(node))

    def tardiness_deduction(self, node):
        return money(self.fields["late_minutes"] * self.minute_rate(node))

    def overtime_pay(self, node):
        return money(
            self.fields["overtime_hours"] * self.hourly_rate(node) * OVERTIME_MULTIPLIER
        )

    def basic_pay(self, node):
        return (
            money(self.fields["salary"])
            - self.absence_deduction(node)
            - self.tardiness_deduction(node)
        )

    def taxable(self, node):
        value = (
            self.basic_pay(node) + self.overtime_pay(node)
            + self.total("ADD") - self.total("CONTRIBUTE")
        )
        return max(Decimal(0), value)

    def tax(self, node):
        return self.interpreter.compute_tax(self.taxable(node))

    def gross(self, node):
        return (
            self.basic_pay(node) + self.overtime_pay(node)
            + self.total("ADD") + self.total("EXEMPT")
        )

    def net(self, node):
        return (
            self.gross(node)
            - self.total("CONTRIBUTE")
            - self.tax(node)
            - self.total("LESS")
        )

    COMPUTED = {
        "daily_rate": daily_rate,
        "hourly_rate": hourly_rate,
        "minute_rate": minute_rate,
        "absence_deduction": absence_deduction,
        "tardiness_deduction": tardiness_deduction,
        "basic_pay": basic_pay,
        "overtime_pay": overtime_pay,
        "total_add": lambda self, node: self.total("ADD"),
        "total_exempt": lambda self, node: self.total("EXEMPT"),
        "total_contribute": lambda self, node: self.total("CONTRIBUTE"),
        "total_less": lambda self, node: self.total("LESS"),
        "gross": gross,
        "taxable": taxable,
        "tax": tax,
        "net": net,
    }

    def get(self, field_name, node):
        if field_name in self.COMPUTED:
            return self.COMPUTED[field_name](self, node)
        if field_name in self.fields:
            return self.fields[field_name]
        raise PayScriptError(
            f"Employee {self.handle} has no field '{field_name}'", node.line, node.col
        )

    def summary(self, node):
        """All computed numbers for this employee, as of now."""
        return {name: self.get(name, node) for name in self.COMPUTED}


class Function:
    def __init__(self, decl):
        self.decl = decl
        self.params = [param.name for param in decl.params]


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


# ===================== VALUE HELPERS =====================

def is_number(value):
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def normalize(value):
    """Numbers are ints or Decimals; a float (hand-built AST) becomes a Decimal."""
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def money(value):
    """Round an amount to whole centavos, halves going up."""
    return Decimal(normalize(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def type_name(value):
    if isinstance(value, bool):
        return "TRUE/FALSE"
    if is_number(value):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "array"
    if isinstance(value, Employee):
        return "employee"
    if isinstance(value, Company):
        return "company"
    return "value"


def format_value(value):
    """How a value looks on screen. Money is rounded only when shown."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (float, Decimal)):
        return format(money(value), "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(format_value(item) for item in value) + "]"
    if isinstance(value, Employee):
        return str(value.fields.get("name", value.handle))
    if isinstance(value, Company):
        return "company"
    return str(value)


def format_money(amount):
    return format(money(amount), "f")


def convert_input(text):
    """INPUT gives text, turned into a number when it looks like one."""
    stripped = text.strip()
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        number = Decimal(stripped)
    except ArithmeticError:
        return text
    # Reject things like "nan" or "inf" that Decimal() accepts.
    if not number.is_finite():
        return text
    return number


# ===================== INTERPRETER =====================

class Interpreter:
    """Runs a PayScript Program AST.

    output:      called with each PRINT line (default: print)
    input_fn:    called with the INPUT prompt, returns text (default: input)
    payslip_dir: folder where PAYSLIP writes <handle>.txt
    """

    def __init__(self, output=print, input_fn=input, payslip_dir="payslips"):
        self.output = output
        self.input_fn = input_fn
        self.payslip_dir = Path(payslip_dir)

        self.company = None
        self.tax_rows = None
        self.employees = {}        # handle -> Employee
        self.employee_list = []    # the built-in `employees` array
        self.functions = {}
        self.globals = {}
        # Each function call pushes its own local scope.
        self.scopes = []

    # ---------- entry point ----------

    def run(self, program: Program):
        """Execute the program and return each employee's computed numbers."""
        for stmt in program.statements:
            try:
                self.execute(stmt)
            except ReturnSignal:
                raise PayScriptError("RETURN can only be used inside a FUNCTION", stmt.line, stmt.col)
        return self.results(program)

    def results(self, node=None):
        node = node or Literal(value=0, line=1, col=1)
        if self.company is None:
            return {}
        return {handle: emp.summary(node) for handle, emp in self.employees.items()}

    # ---------- statements ----------

    def execute_block(self, statements):
        for stmt in statements:
            self.execute(stmt)

    def execute(self, stmt):
        method = getattr(self, "exec_" + type(stmt).__name__, None)
        if method is None:
            raise PayScriptError(
                f"Cannot run statement of type {type(stmt).__name__}", stmt.line, stmt.col
            )
        method(stmt)

    def exec_CompanyDecl(self, stmt: CompanyDecl):
        if self.company is not None:
            raise PayScriptError("Only one COMPANY block is allowed", stmt.line, stmt.col)
        fields = {entry.name: normalize(entry.value.value) for entry in stmt.fields}
        for required in ("working_days", "hours_per_day"):
            if required not in fields:
                raise PayScriptError(f"COMPANY is missing required field {required}", stmt.line, stmt.col)
        self.company = Company(fields)

    def exec_EmployeeDecl(self, stmt: EmployeeDecl):
        if stmt.handle in self.employees:
            raise PayScriptError(f"EMPLOYEE {stmt.handle} is already declared", stmt.line, stmt.col)
        fields = {entry.name: normalize(entry.value.value) for entry in stmt.fields}
        for required in ("name", "salary"):
            if required not in fields:
                raise PayScriptError(
                    f"EMPLOYEE {stmt.handle} is missing required field {required}",
                    stmt.line, stmt.col,
                )
        for numeric in ("salary", "absences", "late_minutes", "overtime_hours"):
            if numeric in fields and not is_number(fields[numeric]):
                entry = next(e for e in stmt.fields if e.name == numeric)
                raise PayScriptError(f"Field {numeric} must be a number", entry.line, entry.col)
        employee = Employee(stmt.handle, fields, self)
        self.employees[stmt.handle] = employee
        self.employee_list.append(employee)

    def exec_TaxTable(self, stmt: TaxTable):
        if self.tax_rows is not None:
            raise PayScriptError("Only one TAX block is allowed", stmt.line, stmt.col)
        self.tax_rows = self.prepare_tax_rows(stmt)

    def exec_FunctionDecl(self, stmt: FunctionDecl):
        if stmt.name in self.functions:
            raise PayScriptError(f"FUNCTION {stmt.name} is already declared", stmt.line, stmt.col)
        self.functions[stmt.name] = Function(stmt)

    def exec_SetStmt(self, stmt: SetStmt):
        value = self.evaluate(stmt.value)
        target = stmt.target
        if isinstance(target, Name):
            self.current_scope()[target.name] = value
        elif isinstance(target, IndexAccess):
            array = self.evaluate(target.base)
            index = self.array_index(array, target.index, target)
            array[index] = value
        else:
            raise PayScriptError("Invalid SET target", target.line, target.col)

    def exec_PayStmt(self, stmt: PayStmt):
        if self.scopes:
            raise PayScriptError(f"{stmt.kind} is not allowed inside a FUNCTION", stmt.line, stmt.col)
        if stmt.kind not in PAY_KINDS:
            raise PayScriptError(f"Unknown pay command {stmt.kind}", stmt.line, stmt.col)
        employee = self.resolve_employee(stmt.target, stmt.kind)
        amount = self.evaluate(stmt.amount)
        if not is_number(amount):
            raise PayScriptError(
                f"{stmt.kind} amount must be a number, got {type_name(amount)}",
                stmt.amount.line, stmt.amount.col,
            )
        employee.add_item(stmt.kind, stmt.label.value, money(amount), stmt.label)

    def exec_PayslipStmt(self, stmt: PayslipStmt):
        employee = self.resolve_employee(stmt.target, "PAYSLIP")
        self.write_payslip(employee, stmt)

    def exec_PrintStmt(self, stmt: PrintStmt):
        values = [format_value(self.evaluate(item)) for item in stmt.items]
        self.output(" ".join(values))

    def exec_IfStmt(self, stmt: IfStmt):
        for branch in stmt.branches:
            if self.condition(branch.condition, "IF"):
                self.execute_block(branch.body)
                return
        if stmt.else_body is not None:
            self.execute_block(stmt.else_body)

    def exec_WhileStmt(self, stmt: WhileStmt):
        while self.condition(stmt.condition, "WHILE"):
            self.execute_block(stmt.body)

    def exec_ForEachStmt(self, stmt: ForEachStmt):
        iterable = self.evaluate(stmt.iterable)
        if not isinstance(iterable, list):
            raise PayScriptError(
                f"FOR EACH needs an array, got {type_name(iterable)}",
                stmt.iterable.line, stmt.iterable.col,
            )
        scope = self.current_scope()
        # Iterate over a snapshot so changes inside the loop don't affect it.
        for item in list(iterable):
            scope[stmt.variable.name] = item
            self.execute_block(stmt.body)

    def exec_ForRangeStmt(self, stmt: ForRangeStmt):
        start = self.number(stmt.start, "FOR range start")
        end = self.number(stmt.end, "FOR range end")
        if start > end:
            raise PayScriptError(
                f"FOR range start ({format_value(start)}) is greater than end ({format_value(end)})",
                stmt.line, stmt.col,
            )
        scope = self.current_scope()
        current = start
        while current <= end:
            scope[stmt.variable.name] = current
            self.execute_block(stmt.body)
            current += 1

    def exec_ReturnStmt(self, stmt: ReturnStmt):
        if not self.scopes:
            raise PayScriptError("RETURN can only be used inside a FUNCTION", stmt.line, stmt.col)
        raise ReturnSignal(self.evaluate(stmt.value))

    # ---------- expressions ----------

    def evaluate(self, expr):
        method = getattr(self, "eval_" + type(expr).__name__, None)
        if method is None:
            raise PayScriptError(
                f"Cannot evaluate expression of type {type(expr).__name__}", expr.line, expr.col
            )
        return method(expr)

    def eval_Literal(self, expr: Literal):
        return normalize(expr.value)

    def eval_ArrayLiteral(self, expr: ArrayLiteral):
        return [self.evaluate(item) for item in expr.items]

    def eval_Name(self, expr: Name):
        return self.lookup(expr.name, expr)

    def eval_FieldAccess(self, expr: FieldAccess):
        base = self.evaluate(expr.base)
        if isinstance(base, (Employee, Company)):
            return base.get(expr.field_name, expr)
        raise PayScriptError(
            f"Cannot read field '{expr.field_name}' of {type_name(base)}", expr.line, expr.col
        )

    def eval_IndexAccess(self, expr: IndexAccess):
        base = self.evaluate(expr.base)
        index = self.array_index(base, expr.index, expr)
        return base[index]

    def eval_UnaryExpr(self, expr: UnaryExpr):
        if expr.operator == "-":
            return -self.number(expr.operand, "'-'")
        if expr.operator == "NOT":
            return not self.boolean(expr.operand, "NOT")
        raise PayScriptError(f"Unknown operator {expr.operator}", expr.line, expr.col)

    def eval_BinaryExpr(self, expr: BinaryExpr):
        op = expr.operator

        # AND / OR short-circuit.
        if op == "AND":
            return self.boolean(expr.left, "AND") and self.boolean(expr.right, "AND")
        if op == "OR":
            return self.boolean(expr.left, "OR") or self.boolean(expr.right, "OR")

        left = self.evaluate(expr.left)
        right = self.evaluate(expr.right)

        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            self.require_numbers(left, right, op, expr)
            return left + right
        if op in ("-", "*", "/"):
            self.require_numbers(left, right, op, expr)
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if right == 0:
                raise PayScriptError("Division by zero", expr.line, expr.col)
            return Decimal(left) / Decimal(right)

        if op in ("=", "!="):
            self.require_same_type(left, right, op, expr)
            equal = left is right if isinstance(left, (Employee, Company)) else left == right
            return equal if op == "=" else not equal
        if op in ("<", "<=", ">", ">="):
            if not (
                (is_number(left) and is_number(right))
                or (isinstance(left, str) and isinstance(right, str))
            ):
                raise PayScriptError(
                    f"Cannot compare {type_name(left)} and {type_name(right)} with '{op}'",
                    expr.line, expr.col,
                )
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            return left >= right

        raise PayScriptError(f"Unknown operator {op}", expr.line, expr.col)

    def eval_CallExpr(self, expr: CallExpr):
        if expr.name == "INPUT":
            return self.call_input(expr)
        if expr.name == "LENGTH":
            return self.call_length(expr)
        return self.call_function(expr)

    # ---------- built-ins and functions ----------

    def call_input(self, expr: CallExpr):
        if len(expr.arguments) > 1:
            raise PayScriptError("INPUT takes at most 1 argument", expr.line, expr.col)
        prompt = ""
        if expr.arguments:
            prompt = format_value(self.evaluate(expr.arguments[0]))
        try:
            text = self.input_fn(prompt)
        except EOFError:
            raise PayScriptError("INPUT reached end of input", expr.line, expr.col) from None
        return convert_input(text)

    def call_length(self, expr: CallExpr):
        if len(expr.arguments) != 1:
            raise PayScriptError("LENGTH takes exactly 1 argument", expr.line, expr.col)
        value = self.evaluate(expr.arguments[0])
        if isinstance(value, (list, str)):
            return len(value)
        raise PayScriptError(
            f"LENGTH needs an array or text, got {type_name(value)}", expr.line, expr.col
        )

    def call_function(self, expr: CallExpr):
        function = self.functions.get(expr.name)
        if function is None:
            raise PayScriptError(f"Undefined function '{expr.name}'", expr.line, expr.col)
        if len(expr.arguments) != len(function.params):
            raise PayScriptError(
                f"Function {expr.name} expects {len(function.params)} argument(s), "
                f"got {len(expr.arguments)}",
                expr.line, expr.col,
            )
        if len(self.scopes) >= MAX_CALL_DEPTH:
            raise PayScriptError(f"Too many nested calls to {expr.name}", expr.line, expr.col)

        args = [self.evaluate(arg) for arg in expr.arguments]
        self.scopes.append(dict(zip(function.params, args)))
        try:
            self.execute_block(function.decl.body)
        except ReturnSignal as signal:
            return signal.value
        finally:
            self.scopes.pop()
        decl = function.decl
        raise PayScriptError(f"FUNCTION {decl.name} ended without RETURN", decl.line, decl.col)

    # ---------- names and scopes ----------

    def current_scope(self):
        return self.scopes[-1] if self.scopes else self.globals

    def lookup(self, name, node):
        # Inside a function only its parameters and locals are visible,
        # plus employees and the company. Outside, the globals.
        scope = self.current_scope()
        if name in scope:
            return scope[name]
        if name in self.employees:
            return self.employees[name]
        if name == "employees":
            return self.employee_list
        if name == "company":
            if self.company is None:
                raise PayScriptError("COMPANY has not been declared yet", node.line, node.col)
            return self.company
        raise PayScriptError(f"Undefined variable '{name}'", node.line, node.col)

    def resolve_employee(self, target, command):
        value = self.evaluate(target)
        if not isinstance(value, Employee):
            raise PayScriptError(
                f"{command} target must be an employee, got {type_name(value)}",
                target.line, target.col,
            )
        return value

    # ---------- type checks ----------

    def number(self, expr, what):
        value = self.evaluate(expr)
        if not is_number(value):
            raise PayScriptError(f"{what} needs a number, got {type_name(value)}", expr.line, expr.col)
        return value

    def boolean(self, expr, what):
        value = self.evaluate(expr)
        if not isinstance(value, bool):
            raise PayScriptError(
                f"{what} needs TRUE or FALSE, got {type_name(value)}", expr.line, expr.col
            )
        return value

    def condition(self, expr, what):
        return self.boolean(expr, f"{what} condition")

    def require_numbers(self, left, right, op, expr):
        if not (is_number(left) and is_number(right)):
            raise PayScriptError(
                f"Cannot use '{op}' on {type_name(left)} and {type_name(right)}",
                expr.line, expr.col,
            )

    def require_same_type(self, left, right, op, expr):
        if type_name(left) != type_name(right):
            raise PayScriptError(
                f"Cannot compare {type_name(left)} and {type_name(right)} with '{op}'",
                expr.line, expr.col,
            )

    def array_index(self, array, index_expr, node):
        if not isinstance(array, list):
            raise PayScriptError(f"Cannot index into {type_name(array)}", node.line, node.col)
        index = self.number(index_expr, "Array index")
        if index != int(index):
            raise PayScriptError(
                f"Array index must be a whole number, got {format_value(index)}",
                index_expr.line, index_expr.col,
            )
        index = int(index)
        if index < 1 or index > len(array):
            raise PayScriptError(
                f"Array index {index} is out of range (1 to {len(array)})",
                index_expr.line, index_expr.col,
            )
        return index - 1  # PayScript arrays start at 1

    # ---------- tax ----------

    def prepare_tax_rows(self, table: TaxTable):
        """Turn TAX rows into (kind, lower, upper, fixed, fraction, base).

        base is where the percentage starts counting: the row's own lower
        bound ("tax on the excess over it"), or 0 for a BELOW row.
        """
        prepared = []
        for row in table.rows:
            bracket, rate = row.bracket, row.rate
            lower = normalize(bracket.lower.value) if bracket.lower is not None else None
            upper = normalize(bracket.upper.value) if bracket.upper is not None else None
            fixed = normalize(rate.fixed_amount.value) if rate.fixed_amount is not None else 0
            fraction = normalize(rate.fraction.value) if rate.fraction is not None else 0
            base = lower if lower is not None else 0
            prepared.append((bracket.kind, lower, upper, fixed, fraction, base))
        return prepared

    def compute_tax(self, taxable):
        if not self.tax_rows:
            return money(0)
        taxable = max(Decimal(0), taxable)
        for kind, lower, upper, fixed, fraction, base in self.tax_rows:
            if kind == "BELOW":
                matches = taxable < upper
            elif kind == "ABOVE":
                matches = taxable > lower
            else:  # RANGE, both ends included
                matches = lower <= taxable <= upper
            if matches:
                return money(fixed + fraction * max(Decimal(0), taxable - base))
        return money(0)

    # ---------- payslips ----------

    def payslip_lines(self, employee: Employee, node):
        """Payslip rows as (label, amount text) in the agreed layout."""
        # Deductions are shown as positive amounts; the label says what they are.
        rows = [("Basic Pay", format_money(employee.fields["salary"]))]

        absence = employee.absence_deduction(node)
        tardiness = employee.tardiness_deduction(node)
        overtime = employee.overtime_pay(node)
        if absence > 0:
            rows.append(("Absences", format_money(absence)))
        if tardiness > 0:
            rows.append(("Tardiness", format_money(tardiness)))
        if overtime > 0:
            rows.append(("Overtime", format_money(overtime)))
        for kind in ("ADD", "EXEMPT", "CONTRIBUTE"):
            for label, amount in employee.items[kind]:
                rows.append((label, format_money(amount)))
        rows.append(("Withholding Tax", format_money(employee.tax(node))))
        for label, amount in employee.items["LESS"]:
            rows.append((label, format_money(amount)))
        rows.append(("Gross", format_money(employee.gross(node))))
        rows.append(("Net Pay", format_money(employee.net(node))))
        return rows

    def render_payslip(self, employee: Employee, node):
        rows = self.payslip_lines(employee, node)
        label_width = max(21, max(len(label) for label, _ in rows) + 2)
        amount_width = max(8, max(len(amount) for _, amount in rows))

        lines = [str(employee.fields["name"])]
        position = employee.fields.get("position")
        if position not in ("", 0, None):
            lines.append(format_value(position))
        for label, amount in rows:
            lines.append(f"{label.ljust(label_width)}{amount.rjust(amount_width)}")
        return "\n".join(lines) + "\n"

    def write_payslip(self, employee: Employee, node):
        text = self.render_payslip(employee, node)
        try:
            self.payslip_dir.mkdir(parents=True, exist_ok=True)
            path = self.payslip_dir / f"{employee.handle}.txt"
            path.write_text(text, encoding="utf-8")
        except OSError as error:
            raise PayScriptError(f"Could not write payslip: {error}", node.line, node.col) from None
        return path


def interpret(program: Program, output=print, input_fn=input, payslip_dir="payslips"):
    """Run a program and return each employee's computed numbers."""
    interpreter = Interpreter(output=output, input_fn=input_fn, payslip_dir=payslip_dir)
    return interpreter.run(program)
