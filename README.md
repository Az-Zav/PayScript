# PayScript

PayScript is a small domain-specific language project for generating payslips.
This repository is initialized with the package and development layout; the
language syntax and runtime are not implemented yet.

## Project layout

- `payscript/` — lexer, parser, validator, interpreter, and CLI package
- `tests/` — automated tests
- `samples/valid/` and `samples/invalid/` — example programs
- `docs/` — language and implementation documentation
- `payslips/` — generated output (ignored by Git)

## Development

Python 3.10 or newer is required. From the repository root, install the package
in editable mode:

```console
python -m pip install -e .
```

The CLI entry point is `payscript run <file.ps>`. The command currently reports
that execution is not implemented; it will become usable as the language
components are developed.

Run the tests with:

```console
python -m unittest discover -s tests
```
