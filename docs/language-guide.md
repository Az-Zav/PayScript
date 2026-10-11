# PayScript language guide

A tutorial for writing PayScript programs. It starts with a one-employee
payslip and builds up to tax tables, loops and functions.

Every example here was run with the real `payscript` command, and the output
shown is what it printed. If you haven't installed PayScript yet, see the
[README](../README.md#install). When you need the exact rules rather than a
walkthrough, use the [language reference](reference.md).

**Contents**

- Part 1: The basics: [first program](#1-your-first-program) ·
  [fields](#2-employees-and-fields) · [pay commands](#3-pay-commands) ·
  [attendance and overtime](#4-attendance-and-overtime) ·
  [payslips and output](#5-payslips-and-output)
- Part 2: Programming in PayScript: [expressions](#6-values-and-expressions) ·
  [variables and input](#7-variables-and-input) · [decisions](#8-making-decisions) ·
  [tax tables](#9-tax-tables) · [loops](#10-repeating-things) ·
  [arrays](#11-arrays) · [functions](#12-functions)
- Part 3: Understanding the results: [money](#13-how-money-works) ·
  [pay calculation](#14-how-pay-is-calculated) · [errors](#15-errors-and-warnings)

---

# Part 1: The basics

## 1. Your first program

A PayScript program is a plain text file, conventionally ending in `.ps`.
Save this as `maria.ps`:

```
COMPANY
    working_days 22
    hours_per_day 8
END

EMPLOYEE maria
    name "Maria Santos"
    salary 22000
END

PRINT maria.name, maria.net
```

Run it:

```console
payscript run maria.ps
```

```
Maria Santos 22000.00
```

What each part does:

- `COMPANY ... END` describes the workplace. Every program needs exactly one,
  with `working_days` and `hours_per_day`. They are used to turn a monthly
  salary into daily and hourly rates.
- `EMPLOYEE maria ... END` declares one employee. `maria` is the employee's
  *handle*, the short lowercase name you use to refer to them. The quoted
  `name` is what appears on the payslip.
- `PRINT` writes values to the terminal, separated by spaces.
- `maria.net` reads the employee's computed *net pay*.

A few ground rules you'll see everywhere:

- **Keywords are UPPERCASE** (`COMPANY`, `PRINT`) and **names are lowercase**
  (`maria`, `total_perks`). Writing `Maria` or `print` is an error.
- Text goes in double quotes. Numbers are written plainly (`22000`, `1.25`).
- `//` starts a comment that runs to the end of the line.
- A program runs from top to bottom, so declare things before you use them.

**Try it:** change `salary` to `30000` and run it again.

## 2. Employees and fields

Inside an `EMPLOYEE` block, each line is a field name followed by its value:

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `name` | text | yes | | Name shown on the payslip |
| `salary` | number | yes | | Monthly salary |
| `position` | text | no | empty | Job title, shown on the payslip if set |
| `absences` | number | no | 0 | Days absent |
| `late_minutes` | number | no | 0 | Total minutes late |
| `overtime_hours` | number | no | 0 | Overtime hours worked |

An unknown field name is an error, as is a missing required field.

You read a field with a dot: `maria.salary`, `maria.position`. Besides the
fields you set, every employee has **computed fields** that PayScript works
out for you:

```
EMPLOYEE maria
    name "Maria Santos"
    position "Accountant"
    salary 22000
    absences 2
END

PRINT maria.daily_rate, maria.absence_deduction, maria.basic_pay, maria.net
```

```
1000.00 2000.00 20000.00 20000.00
```

The daily rate is `22000 / 22 = 1000`. Two absences cost `2000`, leaving a
basic pay of `20000`.

The computed fields are `daily_rate`, `hourly_rate`, `minute_rate`,
`absence_deduction`, `tardiness_deduction`, `basic_pay`, `overtime_pay`,
`total_add`, `total_exempt`, `total_contribute`, `total_less`, `gross`,
`taxable`, `tax` and `net`. They are read-only: you can't assign to them.

Computed fields are recalculated whenever you read them, so printing
`maria.net` before and after a pay command shows different numbers.

**Try it:** add `late_minutes 45` and print `maria.tardiness_deduction`.

## 3. Pay commands

Four commands adjust an employee's pay. Each takes the employee, a text
**label** and an amount:

```
ADD maria "Bonus" 500
```

| Command | Use it for | Adds to gross | Taxable | Deducted from net |
|---|---|---|---|---|
| `ADD` | Taxable earnings: bonuses, allowances that count as income | yes | counts | no |
| `EXEMPT` | Tax-free earnings, such as a meal allowance | yes | no | no |
| `CONTRIBUTE` | Contributions such as SSS, taken before tax | no | reduces it | yes |
| `LESS` | Other deductions, taken after tax | no | no | yes |

A complete example:

```
EMPLOYEE maria
    name "Maria Santos"
    salary 22000
END

ADD maria "Bonus" 500
EXEMPT maria "Meal Allowance" 1000
CONTRIBUTE maria "SSS" 900
LESS maria "Uniform" 300

PRINT maria.gross, maria.taxable, maria.net
```

```
23500.00 21600.00 22300.00
```

Working it out:

- Gross: `22000 + 500 + 1000 = 23500`
- Taxable: `22000 + 500 - 900 = 21600` (the exempt allowance doesn't count, and
  the contribution lowers it)
- Net: `23500 - 900 - 0 tax - 300 = 22300`

Things to know about labels:

- A label appears as a row on the payslip, so choose readable ones.
- Labels are case-sensitive, and each can be used **once per employee**. Using
  the same label twice is an error when the program runs.
- Two labels that differ only in case (`"Bonus"` and `"bonus"`) produce a
  warning, because that is usually a typo.
- Five labels are reserved because PayScript adds those rows itself:
  `"Basic Pay"`, `"Absences"`, `"Tardiness"`, `"Overtime"` and
  `"Withholding Tax"`.
- The amount can be any expression: a number, a variable, a computed field or a
  function call.
- Pay commands can't be used inside a function.

**Try it:** change `ADD` to `EXEMPT` for the bonus and watch `taxable` change.

## 4. Attendance and overtime

Three employee fields feed automatic adjustments:

```
EMPLOYEE maria
    name "Maria Santos"
    salary 22000
    absences 2
    late_minutes 30
    overtime_hours 5
END

PRINT maria.absence_deduction, maria.tardiness_deduction, maria.overtime_pay
```

```
2000.00 62.50 781.25
```

| Adjustment | How it is worked out |
|---|---|
| Absences | `absences` times the daily rate (`salary / working_days`) |
| Tardiness | `late_minutes` times the minute rate (`hourly rate / 60`) |
| Overtime | `overtime_hours` times the hourly rate times 1.25 |

Overtime is paid automatically at 125% of the hourly rate and counts toward
both gross and taxable income. **Don't add overtime yourself** with `ADD`,
or it will be paid twice.

## 5. Payslips and output

`PRINT` writes to the terminal, and `PAYSLIP` writes a file. Add
`PAYSLIP maria` to the program above and run it:

```
Maria Santos
Basic Pay            22000.00
Absences              2000.00
Tardiness               62.50
Overtime               781.25
Withholding Tax          0.00
Gross                20718.75
Net Pay              20718.75
```

This is written to `payslips/maria.txt`. Use `--out DIR` to write to a
different folder.

The layout is always the same:

1. The employee's name, then their position if one is set.
2. `Basic Pay`, which is the full salary.
3. `Absences`, `Tardiness` and `Overtime`, each shown only if it is above zero.
4. Your `ADD`, `EXEMPT` and `CONTRIBUTE` rows, in the order you wrote them.
5. `Withholding Tax`, then your `LESS` rows.
6. `Gross` and `Net Pay`.

Deductions are shown as positive amounts. The label tells you whether it is
added or taken away.

How `PRINT` formats values:

- Several values are separated by spaces: `PRINT maria.name, maria.net`.
- Whole numbers print as they are (`22000`) and fractions print with two
  decimal places (`2.50`).
- Money fields such as `net` always print with two decimals.
- True and false print as `TRUE` and `FALSE`.

---

# Part 2: Programming in PayScript

## 6. Values and expressions

PayScript has numbers, text and true/false values. A few examples (these need
only a `COMPANY` block):

```
PRINT 2 + 3 * 4
PRINT (2 + 3) * 4
PRINT 10 / 4
PRINT 0.1 + 0.2
PRINT 20%
PRINT "Net pay: " + "ready"
PRINT 5 > 3, 5 = 3, 5 != 3
PRINT TRUE AND NOT FALSE
```

```
14
20
2.50
0.30
0.20
Net pay: ready
TRUE FALSE TRUE
TRUE
```

| Kind | Operators | Notes |
|---|---|---|
| Arithmetic | `+ - * /` | `*` and `/` bind tighter than `+` and `-`. Use parentheses to change that |
| Comparison | `= != < <= > >=` | Equality is a single `=` |
| Logic | `AND OR NOT` | Comparisons are worked out first, then `NOT`, then `AND`, then `OR` |
| Text | `+` | Joins text with text |
| Percent | `20%` | Means `0.20` |

Two mistakes to avoid:

- `"Total: " + 5` is an error. You can't join text and a number with `+`.
- Dividing by zero is an error when the program runs.

## 7. Variables and input

`SET` stores a value under a name:

```
SET days TO 22
SET rate TO 1000
SET total TO days * rate
PRINT total
SET label TO "Total"
PRINT label, total
```

```
22000
Total 22000
```

Variable names follow the same rules as employee handles: lowercase letters,
digits and `_`, starting with a letter. You can't use `company`, `employees` or
any computed field name (`net`, `gross`, ...) as a variable.

`INPUT()` asks the person running the program to type a value. An optional
text argument is shown as the prompt:

```
SET extra TO INPUT("Bonus for " + maria.name + ": ")
ADD maria "Bonus" extra
```

If what's typed looks like a number, it becomes a number, otherwise it stays
text. To supply the answer without typing, pipe it in:

```console
echo 500 | payscript run samples/valid/02_attendance_input.ps
```

```
Bonus for Maria Santos: Maria Santos 22218.75 21018.75
```

If the program asks for more input than it was given, it stops with an error.

## 8. Making decisions

`IF` runs lines only when a condition holds:

```
EMPLOYEE carlo
    name "Carlo Cruz"
    salary 28000
    position "Supervisor"
END

IF carlo.position = "Supervisor" THEN
    ADD carlo "Supervisory Allowance" 2000
ELSE
    EXEMPT carlo "Meal Allowance" 1000
END

PRINT carlo.name, carlo.net
```

```
Carlo Cruz 30000.00
```

Chain several tests with `ELSE IF`. The first condition that holds wins, and
`ELSE` is optional:

```
IF john.salary < 10000 THEN
    CONTRIBUTE john "SSS" 500
ELSE IF john.salary < 20000 THEN
    CONTRIBUTE john "SSS" 900
ELSE
    CONTRIBUTE john "SSS" 1350
END
```

Every `IF` ends with `END`, and `THEN` is required after each condition.

Because duplicate labels are only detected when the program runs, you can use
the same label in different branches, as long as only one of them executes.

## 9. Tax tables

A `TAX` block maps taxable income to tax. A program may have at most one:

```
TAX
    BELOW 20833       = 0%
    20833 -> 33333    = 15%
    ABOVE 33333       = 1875 + 20%
END
```

**Brackets** say which incomes a row covers:

| Form | Matches |
|---|---|
| `BELOW 20833` | income less than 20833 |
| `20833 -> 33333` | income from 20833 to 33333, both ends included |
| `ABOVE 33333` | income greater than 33333 |

**Rates** say how much tax a matching row charges:

| Form | Meaning |
|---|---|
| `15%` | 15% of the income above the row's lower bound |
| `1875 + 20%` | a fixed 1875, plus 20% of the income above the row's lower bound |

A `BELOW` row counts from 0. Rows are checked in order and the first match is
used.

**A worked example.** Take John, with a salary of 28000 and an SSS
contribution of 1350:

```
EMPLOYEE john
    name "John Garcia"
    salary 28000
END

CONTRIBUTE john "SSS" 1350

PRINT john.name, john.tax, john.net
```

```
John Garcia 872.55 25777.45
```

1. Taxable income is `28000 - 1350 = 26650`.
2. That falls in the row `20833 -> 33333 = 15%`.
3. Tax is `15% x (26650 - 20833) = 15% x 5817 = 872.55`.
4. Net pay is `28000 - 1350 - 872.55 = 25777.45`.

Tax table rules:

- Ranges must not overlap, and there must be no gap between rows. A gap
  such as 20833 to 20900 is an error, because income there would otherwise
  be taxed at 0.
- A table with no `ABOVE` row gives a warning.
- Income below the first row is untaxed, and with no `TAX` block there is no
  tax at all.

## 10. Repeating things

**`FOR EACH` over a list of values:**

```
SET perks TO [500, 300, 200]
SET total_perks TO 0
FOR EACH p IN perks
    SET total_perks TO total_perks + p
END
```

**`FOR EACH` over a range**, written `start -> end` and including both ends:

```
FOR EACH i IN 1 -> 3
    PRINT "Day", i
END
```

```
Day 1
Day 2
Day 3
```

A range that runs backwards (`3 -> 1`) is an error.

**`WHILE` repeats as long as a condition holds:**

```
SET n TO 3
WHILE n > 0
    PRINT n
    SET n TO n - 1
END
```

```
3
2
1
```

**Looping over every employee.** The built-in `employees` is an array of all
declared employees, so you can apply the same pay commands to everyone and
write a payslip for each:

```
FOR EACH e IN employees
    EXEMPT e "De Minimis Benefits" total_perks
    CONTRIBUTE e "SSS" 1350
    PAYSLIP e
END
```

A loop variable such as `e` is allowed as a pay target, but it can't reuse an
employee's handle. `LENGTH(employees)` gives the number of employees, which is
handy with `WHILE`:

```
SET i TO 1
SET total TO 0
WHILE i <= LENGTH(employees)
    SET total TO total + employees[i].net
    SET i TO i + 1
END
PRINT "Total payroll:", total
```

```
Total payroll: 58000.00
```

A single loop may run at most 1,000,000 times. After that the program stops
with an error, which protects you from an accidental infinite loop.

## 11. Arrays

An array is an ordered list in square brackets:

```
SET perks TO [500, 300, 200]
PRINT perks[1], LENGTH(perks)
```

```
500 3
```

- Positions start at **1**, not 0.
- `LENGTH(perks)` is the number of items.
- You can change one item with `SET perks[2] TO 350`.

Arrays are **copied**, not shared. A copy is made when you `SET` one array
from another, when you pass an array to a function, and into a `FOR EACH`
variable. Changing a copy never changes the original:

```
SET perks TO [500, 300, 200]
SET copy TO perks
SET copy[1] TO 0
PRINT perks[1], copy[1]
```

```
500 0
```

## 12. Functions

A function packages a calculation you want to reuse:

```
FUNCTION perfect_bonus(absences, late)
    SET amount TO 0
    IF absences = 0 AND late = 0 THEN
        SET amount TO 500
    END
    RETURN amount
END

EMPLOYEE ana
    name "Ana Reyes"
    salary 30000
END

ADD ana "Perfect Attendance Bonus" perfect_bonus(ana.absences, ana.late_minutes)
PRINT ana.name, ana.net
```

```
Ana Reyes 30500.00
```

The rules:

- Declare a function **before** you call it, at the top level of the program.
- Every function must `RETURN` a value.
- A call must pass the right number of arguments.
- Inside a function you can use its parameters, its own variables, the
  employee handles, `employees` and `company`. **Global variables are not
  visible**, so pass what you need as arguments (as `ana.absences` is above).
- Pay commands (`ADD`, `EXEMPT`, ...) are not allowed inside a function.
  Return the amount and apply it outside, as the example does.
- Calls can nest at most 100 deep.

---

# Part 3: Understanding the results

## 13. How money works

- **Exact decimals.** Whole numbers are integers, and fractions (`1.25`,
  `20%`) are exact decimals, not binary floating point. So `0.1 + 0.2` is
  exactly `0.3`, which prints as `0.30`.
- **Rounded to centavos.** Absences, tardiness, overtime, tax and each
  `ADD`, `EXEMPT`, `CONTRIBUTE` and `LESS` amount are rounded to two decimal
  places, halves up, at the moment they are computed.
- **Rows add up.** Because every row is rounded when it is produced, the
  rows on a payslip always add up to the Gross and Net totals shown.

## 14. How pay is calculated

For one employee, in order:

| Value | How it is worked out |
|---|---|
| `daily_rate` | `salary / working_days` |
| `hourly_rate` | `daily_rate / hours_per_day` |
| `minute_rate` | `hourly_rate / 60` |
| `absence_deduction` | `absences x daily_rate` |
| `tardiness_deduction` | `late_minutes x minute_rate` |
| `overtime_pay` | `overtime_hours x hourly_rate x 1.25` |
| `basic_pay` | `salary - absence_deduction - tardiness_deduction` |
| `total_add`, `total_exempt`, `total_contribute`, `total_less` | the sum of that command's amounts |
| `taxable` | `basic_pay + overtime_pay + total_add - total_contribute` (never below 0) |
| `tax` | looked up in the tax table using `taxable` |
| `gross` | `basic_pay + overtime_pay + total_add + total_exempt` |
| `net` | `gross - total_contribute - tax - total_less` |

The company's `working_days` and `hours_per_day` come from the `COMPANY`
block.

## 15. Errors and warnings

PayScript checks a whole program before it runs anything, so you don't get a
half-finished set of payslips followed by a crash. Errors look like this:

```
Line 9, col 7: NAME: Name 'x' must be declared before use.
```

The line and column point at the problem. Errors go to standard error and the
command exits with status 1.

There are three kinds of problem:

| Kind | When it's found | Effect |
|---|---|---|
| Error | Before the program runs | Nothing runs |
| Run-time error | While the program runs | The run stops at that point |
| Warning | Before the program runs | Printed, and the run continues |

A warning looks like this:

```
warning: Line 11, col 11: LABEL: 'bonus' differs only in case from 'Bonus'.
```

Add `--strict` to treat warnings as errors:

```console
payscript run program.ps --strict
```

```
payscript: error: 1 warning(s) reported (--strict)
```

### Common mistakes

| Message | What it means | Fix |
|---|---|---|
| `NAME: Name 'x' must be declared before use.` | You used a variable or employee before defining it | `SET` it, or declare the employee, earlier in the file |
| `Expected THEN after the IF condition, but found the end of the line` | An `IF` line is missing `THEN` | End the condition with `THEN` |
| `EMPLOYEE 'maria': Unknown field 'nickname'.` | A field that doesn't exist | Use one of the fields in section 2 |
| `EMPLOYEE 'maria': Missing required field 'salary'.` | `name` or `salary` is missing | Add the field |
| `COMPANY: Missing required field 'hours_per_day'.` | `COMPANY` needs both fields | Add the field |
| `LABEL: 'Basic Pay' is reserved for automatic payslip entries.` | You used a reserved label | Choose another label |
| `Duplicate label "Bonus" for employee maria` | Two pay commands used the same label for one employee | Give each a different label |
| `Cannot use '+' on text and number` | You tried to join text with a number | Keep the types the same |
| `TAX: Gap between 20833 and 20900; income there would be taxed at 0.` | Two tax rows don't meet | Make the ranges touch |
| `unknown character '@'` | A character that isn't part of the language | Remove it, or put it inside quotes if it's text |
| `unterminated string` | A `"` was never closed | Add the closing quote |
| `unclosed '(' (it is never closed with ')')` | A bracket was never closed | Close it |
| `Division by zero` | You divided by 0 | Check the divisor |

For the complete list of rules, see the [language reference](reference.md).

---

## Where next

- [Language reference](reference.md): the grammar and every rule
- [`samples/valid`](../samples/valid): runnable example programs
- [`samples/invalid`](../samples/invalid): programs that fail on purpose, each
  with the error it expects
- [Architecture](architecture.md): how the interpreter works inside
- [Contributing](contributing.md): changing PayScript itself
