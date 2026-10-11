# PayScript

[![tests](https://github.com/Az-Zav/PayScript/actions/workflows/tests.yml/badge.svg)](https://github.com/Az-Zav/PayScript/actions/workflows/tests.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A small language for describing payroll and turning it into payslips.

## What is PayScript?

PayScript is a domain-specific language for payroll. You write a short
program that says who the employees are, what they earn, and what gets added
or deducted. PayScript checks the program, does the arithmetic, and writes one
plain-text payslip per employee.

Amounts are exact decimals rounded to centavos, so the rows on a payslip
always add up to the gross and net totals.

## What it looks like

```
COMPANY
    working_days 22
    hours_per_day 8
END

EMPLOYEE maria
    name "Maria Santos"
    salary 22000
    absences 2
END

ADD maria "Bonus" 500
CONTRIBUTE maria "SSS" 900
PRINT maria.name, maria.gross, maria.net
PAYSLIP maria
```

Running it prints:

```
Maria Santos 20500.00 19600.00
```

and writes `payslips/maria.txt`:

```
Maria Santos
Basic Pay            22000.00
Absences              2000.00
Bonus                  500.00
SSS                    900.00
Withholding Tax          0.00
Gross                20500.00
Net Pay              19600.00
```

## Install

You need Python 3.10 or newer and Git.

```console
pip install git+https://github.com/Az-Zav/PayScript.git
payscript --version
```

If `payscript` isn't found afterwards, try `python -m pip install ...`, or use
[pipx](https://pipx.pypa.io), which puts command-line tools on your PATH for you:

```console
pipx install git+https://github.com/Az-Zav/PayScript.git
```
## Quick start

1. Save the example above as `maria.ps`.
2. Run it:

   ```console
   payscript run maria.ps
   ```

3. Open `payslips/maria.txt` to see the payslip.

More examples are in [`samples/valid`](https://github.com/Az-Zav/PayScript/tree/main/samples/valid).
Programs that ask for input use `INPUT()`, which reads from the keyboard, so you
can also pipe values in: `echo 500 | payscript run samples/valid/02_attendance_input.ps`.

## Command-line reference

| Command | What it does |
|---|---|
| `payscript run FILE` | Check a program, run it, and write one payslip per employee |
| `payscript tokens FILE` | Print the token stream (for debugging the language itself) |
| `payscript --version` | Print the installed version |
| `payscript --help` | Show usage (also works after `run` and `tokens`) |

Options for `run`:

| Option | Meaning |
|---|---|
| `--out DIR` | Write payslips to `DIR` instead of `payslips/` |
| `--strict` | Treat validator warnings as errors |

Errors are printed to standard error in the form `Line 9, col 7: message`.
Warnings go to standard error too and don't stop the run unless you pass
`--strict`.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | A language, file or input error |
| `130` | Interrupted with Ctrl+C |

## Pipeline

`source -> Lexer -> parser -> validator -> interpreter`

- `payscript/lexer.py`, `tokens.py` — tokens with line/column
- `payscript/parser.py`, `ast_nodes.py` — syntax tree
- `payscript/validator.py` — semantic checks (errors and warnings)
- `payscript/interpreter.py` — runs the program, writes payslips
- `payscript/constants.py` — rules shared by the stages (reserved names and
  labels, COMPANY/EMPLOYEE field tables, pay kinds)
- `payscript/main.py` — command-line interface
- `payscript/errors.py` — `PayScriptError` (message shown as `Line N, col M: ...`)

## How money works

- Whole numbers are ints; fractions (`1.25`, `20%`) are exact decimals, so
  `0.1 + 0.2 = 0.3`.
- Every payslip amount (absences, tardiness, overtime, tax, and each
  `ADD`/`EXEMPT`/`CONTRIBUTE`/`LESS`) is rounded to centavos, halves up, when it
  is computed. The rows on a payslip therefore always add up to Gross and Net.
- `overtime_hours` is paid automatically at 125% of the hourly rate and shown
  as an `Overtime` row; do not `ADD` overtime by hand.

## Project layout

- `samples/valid/`, `samples/invalid/` — example programs with expectations in `//` comments
- `tests/` — automated tests (pytest)
- `payslips/` — generated output (ignored by Git)

## Setup and usage

Python 3.10 or newer is required. Work inside a virtual environment so the
project's dependencies stay separate from your system Python. From this folder
(the one containing `pyproject.toml`):

```console
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
python -m pip install -e ".[dev]"   # the payscript command, pytest and ruff
payscript run samples/valid/02_attendance_input.ps
```

Options for `run`:

- `--out DIR` — write payslips to `DIR` instead of `payslips/`
- `--strict` — treat validator warnings as errors

`payscript tokens <file.ps>` prints the token stream for debugging. The exit
code is 0 on success and 1 on any language, file or input error.

## Testing

```console
python -m pytest                       # lexer, parser, validator, interpreter, CLI, samples
python -m pytest -k 02_attendance      # one sample by name
python -m ruff check .                 # lint (unused imports, undefined names)
python scripts/bench.py                # pipeline timing
```

The lint and test checks run on every push through
[.github/workflows/tests.yml](.github/workflows/tests.yml).
