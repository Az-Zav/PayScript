# Contributing to PayScript

## Set up

You need Python 3.10 or newer and Git.

```console
git clone https://github.com/Az-Zav/PayScript.git
cd PayScript
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"   # editable install, plus pytest and ruff
python -m pytest                    # everything should pass
```

`-e` (editable) links the installed `payscript` command to your clone, so
edits take effect immediately without reinstalling.

## Project layout

```
payscript/      the language: lexer -> parser -> validator -> interpreter
tests/          the pytest suite
  conftest.py       shared fixtures and source snippets
  run_samples.py    helper that runs a sample and checks its // expectations
samples/
  valid/            programs that must run and match their expectations
  invalid/          programs that must fail with the stated error
scripts/bench.py    pipeline timing
docs/               documentation
.github/workflows/  CI (lint + tests on every push)
```

## Everyday commands

```console
python -m pytest                       # everything
python -m pytest tests/test_parser.py  # one stage
python -m pytest -k 02_attendance      # one sample, by name
python -m pytest --lf                  # only what failed last time
python -m pytest -x                    # stop at the first failure
python -m ruff check .                 # lint (unused names, syntax errors)
python scripts/bench.py                # timing
```

CI runs the lint and the full test suite on Python 3.10 and 3.12 for every
push and pull request. Run both locally before pushing.

## How the tests are organized

The rule: **test each behaviour once, at the lowest layer that can see it.**

| Layer | Files | Owns | Runs |
|---|---|---|---|
| Language rules | `test_lexer`, `test_parser`, `test_validator`, `test_interpreter`, `test_ast_nodes`, `test_constants` | every grammar, validation and money rule | in-process, fast |
| Command line | `test_cli.py` | what only exists at the process boundary: exit codes, stdout vs stderr, `--out`, `--strict`, `--version`, stdin | subprocess |
| Samples | `samples/` + `test_cli.py` | end-to-end example programs, each checked against its own `//` comments | subprocess |

### Where does my test go?

| You are adding... | Put the test in... |
|---|---|
| a new language rule or keyword | the file of the stage that owns it (lexer, parser, validator or interpreter) |
| a new error message | the stage that raises it |
| a new CLI flag or exit code | `test_cli.py` only |
| a good user-facing example | a new file in `samples/valid/` with annotations |
| a program that must be rejected | a new file in `samples/invalid/` with `// expect-error:` |

Don't add a sample for every rule. Samples are readable examples and
end-to-end checks; the unit tests carry the detail.

### Shared helpers (`tests/conftest.py`)

- `BASE`, `COMPANY`, `MARIA`: source snippets (a company, an employee `maria`).
- `tokens(source)`, `parse_source(source)`, `check(source)`: run one stage.
- `run(source, inputs=())`: the full pipeline; returns an object with
  `.lines`, `.payslip(handle)` and `.warnings`.
- `out(body, inputs=())`: the `PRINT` lines of `BASE + body`.

### Sample annotations

A sample states what it expects in ordinary `//` comments:

```
// input: 500                  one line typed into INPUT() (repeat for more)
// expect-out: <text>          what the program prints (repeat for more lines)
// expect-payslip maria:       followed by comment lines holding payslips/maria.txt
//   Maria Santos
//   Basic Pay            22000.00
// expect-error: Line 9, col 9: unknown character '@'
```

- A sample with no expectation only has to run without an error.
- Whitespace is compared loosely (runs of spaces count as one).
- Every file in `samples/invalid/` must have an `expect-error` line.

## Adding a language feature

Work through the pipeline in order, with a test at each step:

1. Describe it in `docs/reference.md` (grammar and rules).
2. Add any new tokens or keywords (`tokens.py`, `constants.py`) and a lexer test.
3. Parse it (`parser.py`, `ast_nodes.py`) and add parser and AST tests.
4. Add semantic checks to `validator.py` and validator tests.
5. Make it run in `interpreter.py` and add interpreter tests.
6. Add a CLI test only if it adds a flag, exit code or output channel.
7. Add a sample if it makes a good example.
8. Update the docs, then run `python -m pytest` and `python -m ruff check .`.

## Fixing a bug

1. Write a failing test at the stage where the bug lives.
2. Fix it.
3. Run the whole suite.

## Releasing

The version lives in one place: `__version__` in `payscript/__init__.py`.
`pyproject.toml` reads it from there.

```console
# edit payscript/__init__.py, then:
git commit -am "Release 0.2.0"
git tag v0.2.0
git push --tags
```

Users can then install exactly that release:

```console
pip install git+https://github.com/Az-Zav/PayScript.git@v0.2.0
```