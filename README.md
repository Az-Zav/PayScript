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

## The language at a glance

Programs are plain text. Keywords are UPPERCASE, names are lowercase, and `//`
starts a comment.

- **Declare** the company and its employees with `COMPANY` and `EMPLOYEE` blocks.
- **Pay commands**: `ADD`, `EXEMPT`, `CONTRIBUTE` and `LESS` apply a labelled
  amount to an employee, for example `ADD maria "Bonus" 500`.
- **Computed fields** such as `maria.gross`, `maria.tax` and `maria.net` are
  calculated for you.
- **Tax tables** map income brackets to rates with a `TAX` block.
- **Logic**: `IF` / `ELSE IF` / `ELSE`, `WHILE`, `FOR EACH`, arrays,
  `FUNCTION` / `RETURN`, and `INPUT()` for values typed at run time.
- **Output** with `PRINT` and `PAYSLIP`.

A taste of it, with a tax table and a condition:

```
TAX
    BELOW 20833       = 0%
    20833 -> 33333    = 15%
    ABOVE 33333       = 1875 + 20%
END

EMPLOYEE john
    name "John Garcia"
    salary 28000
END

IF john.salary < 20000 THEN
    CONTRIBUTE john "SSS" 900
ELSE
    CONTRIBUTE john "SSS" 1350
END

PRINT john.name, john.tax, john.net
```

To learn the language step by step, read the
[language guide](https://github.com/Az-Zav/PayScript/blob/main/docs/language-guide.md).
The formal grammar and every rule are in the
[language reference](https://github.com/Az-Zav/PayScript/blob/main/docs/reference.md).

## Documentation

**Using PayScript**

- [Language guide](https://github.com/Az-Zav/PayScript/blob/main/docs/language-guide.md): a tutorial, from a first payslip to tax tables and functions
- [Language reference](https://github.com/Az-Zav/PayScript/blob/main/docs/reference.md): grammar and rules
- [Sample programs](https://github.com/Az-Zav/PayScript/tree/main/samples): valid and invalid examples

**Working on PayScript**

- [Contributing](https://github.com/Az-Zav/PayScript/blob/main/docs/contributing.md): setup, test layout and workflow
- [Architecture](https://github.com/Az-Zav/PayScript/blob/main/docs/architecture.md): lexer, parser, validator and interpreter, file by file
- [AST contract](https://github.com/Az-Zav/PayScript/blob/main/docs/ast_contract.md): the syntax-tree interface between stages
- [How the command works](https://github.com/Az-Zav/PayScript/blob/main/docs/how-the-command-works.md): how pip creates `payscript` and how it ships

## Contributing

```console
git clone https://github.com/Az-Zav/PayScript.git
cd PayScript
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"   # editable install + pytest and ruff
python -m pytest                    # run the tests
python -m ruff check .              # lint
```

The same lint and test checks run on every push through GitHub Actions.

## Authors

Victor Jazz Condicion, Rhian Jannah Lacar, EJ Bagayan, Jahzara Samantha San Pablo
and Vinea Lei De Leon.

## License

[MIT](https://github.com/Az-Zav/PayScript/blob/main/LICENSE)