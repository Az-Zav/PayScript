# PayScript architecture

PayScript is a small interpreter written in Python. A program passes through
four stages (lexer, parser, validator, interpreter), wired together by
`main.py`. This document describes what each stage does, how the stages depend
on each other, the conventions to keep when changing them, and where to make
the common kinds of change.

Related documents:

- [contributing.md](contributing.md): setup, test layout and workflow
- [reference.md](reference.md): the grammar and validator rules (the language itself)
- [how-the-command-works.md](how-the-command-works.md): how the `payscript` command is created and packaged
- [ast_contract.md](ast_contract.md): the syntax-tree interface between stages

## 1. Overview

```
source -> Lexer -> parse -> validate -> interpret
```

| Stage | Module | Input -> output | Errors it raises |
|---|---|---|---|
| Driver | `main.py` | file path -> exit code | catches everything below |
| Lexer | `lexer.py` | source text -> list of `Token` | unknown character, unterminated string, invalid word, unclosed bracket |
| Parser | `parser.py` | tokens -> `Program` (the AST) | syntax errors (missing `THEN`, stray `END`, a line that starts with a name) |
| Validator | `validator.py` | `Program` -> nothing, or an error | semantic errors: undefined names, missing fields, bad tax tables |
| Interpreter | `interpreter.py` | `Program` -> printed output, payslip files, computed numbers | run-time errors: division by zero, text + number, duplicate label, loop limit |

Each stage consumes only the output of the previous one. A stage either hands
its result forward or raises `PayScriptError`, which stops the run.

## 2. Pipeline diagram

```
   payroll.ps  (plain text on disk)
        |
        v
 +--------------+   main.read_source()      reads the file as UTF-8 text
 |   main.py    |
 +------+-------+
        |  'ADD maria "Bonus" 500\n...'          (a str)
        v
 +--------------+   tokens.py = vocabulary (T, KEYWORDS, SYMBOLS, Token)
 |    LEXER     |   errors: unknown character, unterminated string,
 |   lexer.py   |           unclosed '(' or '[', unknown word 'Foo'
 +------+-------+
        |  [Token(ADD) Token(IDENT maria) Token(STRING "Bonus") Token(NUMBER 500) Token(NEWLINE) ... Token(EOF)]
        v
 +--------------+   builds the nodes defined in ast_nodes.py
 |    PARSER    |   errors: missing THEN, END without a block,
 |  parser.py   |           a line cannot start with the name 'x'
 +------+-------+
        |  Program(statements=[CompanyDecl, EmployeeDecl, PayStmt, PrintStmt, ...])   (the AST)
        v
 +--------------+   uses constants.py (field tables, reserved names)
 |  VALIDATOR   |   errors:   undefined variable, duplicate COMPANY,
 | validator.py |             tax table gap or overlap, missing salary
 +------+-------+   warnings: labels that differ only by case (--strict makes these errors)
        |  the same Program, now known to be consistent
        v
 +--------------+   uses constants.py too
 | INTERPRETER  |   errors: division by zero, text + number,
 |interpreter.py|           duplicate label at run time, loop limit
 +------+-------+
        |
        +--> PRINT   -> terminal (stdout)
        +--> INPUT   <- keyboard (stdin)
        +--> PAYSLIP -> payslips/<handle>.txt

 errors.py (PayScriptError) is raised by all four stages and handled once, in main.py.
```

### How errors travel

- Every language error is a `PayScriptError(message, line, col)`. Its string
  form is `Line 4, col 7: message`.
- `main.main()` catches it once, prints it to standard error and returns exit
  code `1`. No stage prints its own errors.
- File problems (`file not found`, not valid UTF-8) and `--strict` warnings are
  reported as `payscript: error: ...`, also with exit code `1`.
- Validator warnings are printed as `warning: ...` and do not stop the run
  unless `--strict` is used.
- Running out of `INPUT` data is reported cleanly (exit code `1`), and Ctrl+C
  exits with `130`.
- A `RecursionError` from very deeply nested source is converted to a
  "nested too deeply" error, so users never see a Python traceback.

## 3. Module map

All modules live in `payscript/`.

| Module | Responsibility | Imports from |
|---|---|---|
| `tokens.py` | Token types (`T`), `KEYWORDS`, `SYMBOLS`, the `Token` record | none |
| `errors.py` | `PayScriptError` | none |
| `constants.py` | Language rules shared by more than one stage | none |
| `ast_nodes.py` | AST node classes | none |
| `lexer.py` | Source text to tokens | `tokens`, `errors` |
| `parser.py` | Tokens to AST | `ast_nodes`, `constants`, `errors`, `tokens` |
| `validator.py` | Semantic checks on the AST | `ast_nodes`, `constants`, `errors` |
| `interpreter.py` | Runs the AST, computes pay, writes payslips | `ast_nodes`, `constants`, `errors` |
| `main.py` | Command-line interface and pipeline wiring | all stages |

The stages never import each other. They share data only through the AST and
the modules at the top of this table.

## 4. Shared foundations

### `tokens.py`

The vocabulary of the language and no logic.

- `T` is an `Enum` of every token type (`T.ADD`, `T.PLUS`, `T.IDENT`, `T.NUMBER`, ...).
  Using `T.ADD` instead of the string `"ADD"` turns a typo into an immediate error.
- `KEYWORDS` is the set of reserved words. It is derived from `T`: every
  upper-case member that is not a symbol or literal type is a keyword.
- `SYMBOLS` maps symbol text to a token type. Two-character symbols (`<=`,
  `->`) come first so `<=` is not read as `<` then `=`.
- `Token` holds `type`, `value`, `line` and `col`. The position is what makes
  precise error messages possible in every later stage.

### `errors.py`

One exception class, `PayScriptError(message, line, col)`, shared by all
stages. Because it is the only language error, `main.py` can handle it in one
place.

### `constants.py`

Rules that more than one stage must agree on, defined once:

| Name | Meaning |
|---|---|
| `PAY_KINDS` | `ADD`, `EXEMPT`, `CONTRIBUTE`, `LESS` |
| `RESERVED_LABELS` | Payslip rows PayScript adds itself (`Basic Pay`, `Absences`, `Tardiness`, `Overtime`, `Withholding Tax`); users may not reuse them as labels |
| `COMPUTED_FIELDS` | Read-only numbers an employee exposes (`gross`, `tax`, `net`, ...) |
| `RESERVED_NAMES` | Names users may not use for variables, employees or functions (`company`, `employees` and all computed fields) |
| `COMPANY_FIELDS`, `EMPLOYEE_FIELDS` | Allowed fields, each with its kind (`text` or `number`) and minimum rule |
| `COMPANY_REQUIRED`, `EMPLOYEE_REQUIRED` | Fields that must be present |
| `EMPLOYEE_DEFAULTS` | Values for optional employee fields that are left out |

Behaviour that belongs to a single stage (loop limits, the overtime
multiplier) stays in that stage.

### `ast_nodes.py`

One small frozen dataclass per language construct. Every node carries `line`
and `col`, so even a run-time error can point at the exact place in the
source.

- Expressions (`Expr`): `Literal`, `Name`, `FieldAccess`, `IndexAccess`,
  `ArrayLiteral`, `UnaryExpr`, `BinaryExpr`, `CallExpr`
- Statements (`Stmt`): `CompanyDecl`, `EmployeeDecl`, `TaxTable`,
  `FunctionDecl`, `SetStmt`, `PayStmt`, `PayslipStmt`, `PrintStmt`, `IfStmt`,
  `WhileStmt`, `ForEachStmt`, `ForRangeStmt`, `ReturnStmt`
- Supporting nodes: `FieldEntry`, `IfBranch`, `TaxRow`, `TaxBracket`, `TaxRate`
- `Program(statements=[...])` is the root.

Nodes are frozen, so attributes cannot be reassigned after the parser builds
them. The lists inside them can still be mutated, so treat a finished tree as
read-only. The full interface is in [ast_contract.md](ast_contract.md).

## 5. The stages

### `main.py`: the driver

**Responsibility:** connect the stages and turn exceptions into messages and
exit codes. It contains no language logic.

| Function | Role |
|---|---|
| `read_source(filename)` | Checks the file exists and reads it as UTF-8 |
| `run_source(source, payslip_dir, strict)` | The pipeline: `Lexer(source).tokenize()`, `parse(tokens)`, `validate(program)`, `interpret(program, ...)` |
| `main()` | Builds the `argparse` interface (`run`, `tokens`, `--out`, `--strict`, `--version`), calls the above, and maps exceptions to exit codes |

The validator reports non-fatal problems through Python's `warnings` module.
`run_source` collects them with `warnings.catch_warnings`, prints them to
standard error and, with `strict=True`, aborts before the interpreter starts.

### `lexer.py`: text to tokens

**Responsibility:** cut the source into tokens. The lexer knows what each word
*is*, not whether the words make sense together.

**Entry point:** `Lexer(source).tokenize()`, which returns a list of `Token`
ending in `NEWLINE` and `EOF`.

How it works: a cursor (`pos`, with `line` and `col`) walks the text and
dispatches on the current character: whitespace is skipped, `\n` becomes a
`NEWLINE`, `//` starts a comment, `"` starts a string, a digit starts a number,
a letter starts a word, anything else is a symbol.

Rules enforced here:

- **Keywords are UPPERCASE and names are lowercase.** `read_word` accepts a
  keyword, or an identifier made of lowercase letters, digits and `_`, and
  rejects everything else.
- **Names and keywords are ASCII only.** Text inside `"..."` and `//`
  comments may hold any characters.
- **Numbers** are `int` when written without a fraction and `Decimal`
  otherwise, so money arithmetic is exact. `20%` becomes a `PERCENT` token
  holding `0.20`.
- **Newlines are ignored inside `(...)` and `[...]`.** An opening bracket that
  is never closed is reported at the place where it was opened.
- Strings have no escape sequences.

### `parser.py`: tokens to tree

**Responsibility:** check the token stream against the grammar and build the
AST. It is a recursive-descent parser: one method per grammar rule, and rules
call each other.

**Entry point:** `parse(tokens)`, which returns a `Program`.

Structure:

- `Parser.parse` reads lines until `EOF`. `parse_line` reads one statement plus
  its line break, and `parse_block` reads lines until `END` or `ELSE`.
- `parse_statement` is the dispatcher. It looks at the first token and calls
  the matching `parse_*` method, and it produces the helpful errors for a line
  that starts with `END`, `ELSE` or a bare name.
- Each statement kind has its own method (`parse_company`, `parse_employee`,
  `parse_tax_table`, `parse_function`, `parse_if`, `parse_while`, `parse_for`,
  `parse_set`, `parse_pay`, `parse_payslip`, `parse_print`, `parse_return`).
  `parse_pay` handles all four pay commands.
- Small helpers (`peek`, `advance`, `check`, `match`, `expect`,
  `expect_end`) keep the rule methods short and their error messages
  consistent.

**Expressions** use precedence climbing, one method per level, from loosest to
tightest binding:

```
parse_expression -> parse_or -> parse_and -> parse_not -> parse_comparison
  -> parse_additive (+ -) -> parse_term (* /) -> parse_unary (-x)
  -> parse_postfix (.field  [index]) -> parse_call -> parse_primary
```

Each level calls only the next tighter level for its operands, so `2 + 3 * 4`
becomes `2 + (3 * 4)` without any special casing.

### `validator.py`: semantic checks

**Responsibility:** catch problems the grammar cannot, before anything runs, so
users do not get a half-finished payslip run followed by a crash.

**Entry point:** `validate(program)`. It returns `None` for a consistent
program and raises `PayScriptError` at the **first** problem. It also accepts
hand-built ASTs, so it can be tested without the lexer or parser.

Structure:

1. **Program-level checks:** exactly one `COMPANY`, at most one `TAX`.
2. **Structure pass** (`_check_structure`, `_check_fields`): declarations are
   only allowed at the top level, required fields are present, no unknown or
   duplicate fields, and values have the right kind.
3. **Statement pass** (`_check_statements`): one small `_check_*` function per
   statement type, found through the `_STATEMENT_CHECKS` table, plus checks for
   expressions, targets, pay labels and tax tables.

**Scope model:** a `_Scope` records which names, functions, employees and loop
variables exist *at this point in the code*. IF branches, loops and function
bodies receive `scope.copy()`, so names invented inside them do not leak out.
`INPUT` and `LENGTH` are pre-registered as known functions.

Two things are deliberately **not** checked here and are left to run time:

- duplicate pay labels on one employee, because the same label may legitimately
  appear in different `IF` branches;
- whether `maria.foo` is a real field, or whether a loop variable holds an
  employee.

Non-fatal findings (labels that differ only by case) are emitted as
`PayScriptWarning` and validation continues.

### `interpreter.py`: running the program

**Responsibility:** execute the AST, compute pay, and produce output.

**Entry point:** `interpret(program, output=print, input_fn=input,
payslip_dir="payslips")`. It runs the program and returns each employee's
computed numbers.

#### Dispatch

The interpreter is a tree walker. `execute(stmt)` calls
`exec_<ClassName>(stmt)` and `evaluate(expr)` calls `eval_<ClassName>(expr)`,
using the node's class name. **To support a new node type, add a method with
the matching name**; there is no registry to update.

#### Runtime objects

| Class | Role |
|---|---|
| `Company` | Holds `working_days` and `hours_per_day` |
| `Employee` | Holds the input fields and the ADD/EXEMPT/CONTRIBUTE/LESS items. Its computed fields are recalculated every time they are read, so a `PRINT` before and after an `ADD` shows different numbers |
| `Function` | A user-defined function (stores its declaration) |
| `ReturnSignal` | Internal exception used to leave a function on `RETURN` |

Variables live in `Interpreter.globals`. Each function call pushes a new local
scope onto `Interpreter.scopes`, so global variables are not visible inside a
function.

#### How pay is computed

`Employee` derives everything from the input fields and the items recorded by
the pay commands. There is one method per computed field, each registered in
the `Employee.COMPUTED` table, and none of them cache: every read recalculates
from the current fields and items. Amounts are rounded with `money()`
(centavos, halves up) at the point they are computed.

The formulas themselves are listed in
[section 14 of the language guide](language-guide.md#14-how-pay-is-calculated),
so there is a single copy to keep up to date. The only constant that lives in
the interpreter is `OVERTIME_MULTIPLIER` (see Limits below).

#### Tax lookup

`prepare_tax_rows` converts the `TAX` block once, and `compute_tax` scans the
rows in order and uses the first one that matches:

- `BELOW n` matches when `taxable < n`
- `ABOVE n` matches when `taxable > n`
- `a -> b` matches when `a <= taxable <= b` (both ends included)

The tax is `fixed + rate * (taxable - base)`, where `base` is the row's own
lower bound (0 for a `BELOW` row). With no tax table, or no matching row, the
tax is 0.

#### Payslips

`payslip_lines` builds the rows in a fixed order: `Basic Pay`, then
`Absences`, `Tardiness` and `Overtime` when they are greater than 0, then the
`ADD`, `EXEMPT` and `CONTRIBUTE` items, `Withholding Tax`, the `LESS` items,
`Gross` and `Net Pay`. `render_payslip` aligns the columns and
`write_payslip` writes `<handle>.txt`, creating the folder if needed.

#### Limits

| Constant | Value | Effect |
|---|---|---|
| `MAX_LOOP_ITERATIONS` | 1,000,000 | one `WHILE` or `FOR` loop may run at most this many times |
| `MAX_CALL_DEPTH` | 100 | function calls may nest at most this deep |
| `OVERTIME_MULTIPLIER` | 1.25 | applied to the hourly rate for overtime |

## 6. Conventions

Keep these when changing the code:

1. **One error type.** Raise `PayScriptError(message, line, col)` with the
   position of the offending node or token. Never print errors from inside a
   stage.
2. **Treat the AST as read-only.** Nodes are frozen; build new nodes instead of
   changing old ones.
3. **Share rules through `constants.py`.** If two stages need the same fact,
   define it there so they cannot drift apart.
4. **Exact money.** Use `Decimal`, never `float`, and round with the
   interpreter's `money()` helper.
5. **Name interpreter methods after node classes** (`exec_*`, `eval_*`).
6. **Inject I/O.** The interpreter takes `output` and `input_fn` as parameters,
   so tests pass fakes instead of touching the terminal.
7. **Warnings are not errors.** Report non-fatal findings with
   `PayScriptWarning`, and let `main.py` decide what to do with them.
8. **Validator messages** start with an area prefix, for example `COMPANY:`,
   `NAME:` or `FUNCTION:`, followed by the problem.

## 7. Extending PayScript

Each recipe lists the files to change in order. Tests live in `tests/`; see
[contributing.md](contributing.md) for the layout and where each kind of test
goes.

### Add an employee input field

1. `constants.py`: add it to `EMPLOYEE_FIELDS` (kind and minimum rule). Add it
   to `EMPLOYEE_REQUIRED` or `EMPLOYEE_DEFAULTS` as appropriate.
2. `interpreter.py`: use it in the `Employee` formulas if it affects pay.
3. Tests: `test_constants.py`, `test_validator.py`, `test_interpreter.py`.
4. Document it in `reference.md`.

### Add a computed employee field

1. `constants.py`: add the name to `COMPUTED_FIELDS`.
2. `interpreter.py`: add a method to `Employee` **and** an entry in
   `Employee.COMPUTED`.
3. `test_constants.py` fails if the two lists disagree, which is the check that
   you did both. Add a test in `test_interpreter.py`.

### Add a statement

1. `tokens.py`: add the token type (and keyword) to `T`.
2. `ast_nodes.py`: add the node class.
3. `parser.py`: add a `parse_*` method and a branch in `parse_statement`.
4. `validator.py`: add a `_check_*` function and register it in
   `_STATEMENT_CHECKS`. If the statement contains nested statements, update
   `_bodies` as well.
5. `interpreter.py`: add `exec_<NodeClassName>`.
6. Tests at each stage: lexer, parser, `test_ast_nodes.py`, validator,
   interpreter.

### Add a built-in function (like `INPUT` or `LENGTH`)

1. `tokens.py`: add the keyword.
2. `parser.py`: allow it in `parse_call` and `parse_primary`.
3. `validator.py`: register it, with its argument count, in the default
   `_Scope.functions`.
4. `interpreter.py`: add a `call_<name>` method and a branch in
   `eval_CallExpr`.

### Add a validator rule

1. Add the check to the relevant `_check_*` function in `validator.py`, with an
   area-prefixed message.
2. Add a test in `test_validator.py`.
3. Add a file to `samples/invalid/` only if it makes a good user-facing example.

### Change the payroll formula

All of it is in `Employee` in `interpreter.py`. Update the formulas in
[language-guide.md](language-guide.md#14-how-pay-is-calculated) (section 14),
any affected rule in `reference.md`, and the interpreter tests together.

## 8. Find it fast

| Question | Answer |
|---|---|
| Where is the pipeline order defined? | `run_source()` in `main.py` |
| Where is the keyword and name casing rule? | `Lexer.read_word` |
| Where is operator precedence? | The `parse_or` to `parse_primary` ladder in `parser.py` |
| Where do "undefined variable" errors come from? | `_check_expression` in `validator.py` |
| Where is the payroll formula? | `Employee` in `interpreter.py` |
| Where is the tax lookup? | `Interpreter.compute_tax` |
| Where is the payslip layout? | `payslip_lines` and `render_payslip` in `interpreter.py` |
| Where are field names and required fields? | `constants.py` |
| What creates the `payscript` command? | `[project.scripts]` in `pyproject.toml` (see [how-the-command-works.md](how-the-command-works.md)) |
| What decides what ships to users? | `[tool.setuptools] packages` in `pyproject.toml` |

## 9. Tests

There is roughly one test file per stage:

| Stage | Tests |
|---|---|
| Constants (and their agreement with the interpreter) | `tests/test_constants.py` |
| Lexer | `tests/test_lexer.py` |
| Parser | `tests/test_parser.py` |
| AST nodes | `tests/test_ast_nodes.py` |
| Validator | `tests/test_validator.py` |
| Interpreter | `tests/test_interpreter.py` |
| Command line and sample programs | `tests/test_cli.py` |

[contributing.md](contributing.md) explains the layers, the shared fixtures and
the workflow for adding a test.
