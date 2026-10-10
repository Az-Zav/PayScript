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
- `payscript/main.py` — command-line interface
- `payscript/errors.py` — `PayScriptError` (message shown as `Line N, col M: ...`)

## Project layout

- `samples/valid/`, `samples/invalid/` — example programs with expectations in `//` comments
- `tests/` — automated tests
- `payslips/` — generated output (ignored by Git)

## Usage

Python 3.10 or newer is required. From the repository root:

```console
python -m pip install -e .
payscript run samples/valid/02_attendance_input.ps
```

Options for `run`:

- `--out DIR` — write payslips to `DIR` instead of `payslips/`
- `--strict` — treat validator warnings as errors

`payscript tokens <file.ps>` prints the token stream for debugging. The exit
code is 0 on success and 1 on any language, file or input error.

## Testing

```console
python -m pip install -e ".[dev]"      # once: installs pytest
python -m pytest                       # lexer, parser, validator, interpreter, CLI, samples
python run_samples.py                  # every sample, valid and invalid
python bench.py                        # pipeline timing
```
