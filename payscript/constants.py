"""Language rules shared by more than one stage of the pipeline.

The parser, validator and interpreter all need to agree on these, so they are
defined once here. Behaviour that belongs to a single stage (loop limits, the
overtime multiplier, ...) stays in that stage.

Adding a computed employee field means: add its name to COMPUTED_FIELDS and a
method plus a COMPUTED entry in interpreter.Employee. A test checks they match.
"""

# The four pay commands, in the order their payslip rows are grouped.
PAY_KINDS = ("ADD", "EXEMPT", "CONTRIBUTE", "LESS")

# Labels PayScript adds to the payslip by itself; users may not reuse them.
RESERVED_LABELS = frozenset({
    "Basic Pay", "Absences", "Tardiness", "Overtime", "Withholding Tax",
})

# Numbers an employee exposes that PayScript computes (read-only).
COMPUTED_FIELDS = (
    "daily_rate", "hourly_rate", "minute_rate", "absence_deduction",
    "tardiness_deduction", "basic_pay", "overtime_pay", "total_add",
    "total_exempt", "total_contribute", "total_less", "gross", "taxable",
    "tax", "net",
)

# Names the user may not use for their own variables, employees or functions.
RESERVED_NAMES = frozenset({"company", "employees", *COMPUTED_FIELDS})

# Allowed fields in COMPANY / EMPLOYEE blocks: name -> (kind, minimum rule).
#   kind "text"   = must be a string
#   kind "number" = must be an int/Decimal
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

# Optional employee fields and the value they get when left out.
EMPLOYEE_DEFAULTS = {
    "position": "",
    "absences": 0,
    "late_minutes": 0,
    "overtime_hours": 0,
}

# Employee fields that must hold a number (derived from EMPLOYEE_FIELDS).
EMPLOYEE_NUMBER_FIELDS = tuple(
    name for name, (kind, _) in EMPLOYEE_FIELDS.items() if kind == "number"
)
