# PayScript

PayScript is a small domain-specific language for generating payslips. A
program declares a company, employees and (optionally) a tax table, applies
pay commands, and writes one plain-text payslip per employee.

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

The full grammar and validator rules are in [docs/Documentation.md](docs/Documentation.md);
the AST interface is in [docs/ast_contract.md](docs/ast_contract.md).

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
python -m ruff check .                 # lint (unused imports, undefined names)
python run_samples.py                  # every sample, valid and invalid
python bench.py                        # pipeline timing
```

The same three checks run on every push through
[.github/workflows/tests.yml](.github/workflows/tests.yml).
