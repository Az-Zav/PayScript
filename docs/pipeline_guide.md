# PayScript: How the Pipeline Works (A Senior Dev's Guide)

Written for: a junior dev who wants a mental model of the codebase, how the CLI command exists, and how this ships to other machines.

Everything below is based on the code in `payscript/`, `pyproject.toml` and the generated `.egg-info`, not on guesses.

---

## 1. The big picture in one paragraph

A PayScript program is just **text**. The computer can't do anything useful with raw text, so we push it through four stations. Each station takes the output of the previous one, does *one* job, and either hands the result forward or stops with an error that says `Line 4, col 7: message`.

Think of it like a restaurant order:

| Station | Restaurant analogy | Real job |
|---|---|---|
| Lexer | Waiter splits your sentence into individual words | Text → list of tokens |
| Parser | Waiter checks the order is grammatical and writes it as a ticket | Tokens → tree (AST) |
| Validator | Kitchen manager checks "do we even have that ingredient?" | Tree → same tree, or an error |
| Interpreter | The cook actually cooks | Tree → printed output + payslip files |

---

## 2. Pipeline visualization

```
   payroll.ps  (plain text on disk)
        │
        ▼
 ┌──────────────┐   main.read_source()      reads file as UTF-8 text
 │   main.py    │
 └──────┬───────┘
        │  "ADD maria \"Bonus\" 500\n..."        (a str)
        ▼
 ┌──────────────┐   tokens.py = vocabulary (T, KEYWORDS, SYMBOLS, Token)
 │   LEXER      │   errors: unknown character, unterminated string,
 │  lexer.py    │           unclosed '(' , "unknown word 'Foo'"
 └──────┬───────┘
        │  [Token(ADD) Token(IDENT maria) Token(STRING "Bonus") Token(NUMBER 500) Token(NEWLINE) ... Token(EOF)]
        ▼
 ┌──────────────┐   builds nodes defined in ast_nodes.py
 │   PARSER     │   errors: "missing THEN", "END without a block",
 │  parser.py   │           "a line cannot start with the name 'x'"
 └──────┬───────┘
        │  Program(statements=[CompanyDecl, EmployeeDecl, PayStmt, PrintStmt, ...])   (the AST)
        ▼
 ┌──────────────┐   uses constants.py (field tables, reserved names)
 │  VALIDATOR   │   errors: undefined variable, duplicate COMPANY,
 │ validator.py │           tax table gap/overlap, missing salary
 └──────┬───────┘   warnings: labels differing only by case  (--strict makes these errors)
        │  same Program, now known to be sane
        ▼
 ┌──────────────┐   uses constants.py too
 │ INTERPRETER  │   errors: division by zero, text + number,
 │interpreter.py│           duplicate label at run time, infinite loop guard
 └──────┬───────┘
        │
        ├──► PRINT  → terminal (stdout)
        ├──► INPUT  ← keyboard (stdin)
        └──► PAYSLIP → payslips/<handle>.txt

 errors.py (PayScriptError) is raised by ALL four stations and caught once, in main.py.
```

The one-line version lives in `main.py`'s docstring: `source -> Lexer -> parse -> validate -> interpret`.

---

## 3. File-by-file mental model

### The supporting cast (no pipeline "step", but everyone depends on them)

#### `tokens.py`: the vocabulary
**Mental model:** a dictionary of every kind of "word" the language has. It contains no logic.
- `T`: an Enum of every token type (`T.ADD`, `T.PLUS`, `T.IDENT`, `T.NUMBER` ...). Using `T.ADD` instead of the string `"ADD"` means a typo is an immediate error instead of a silent bug.
- `KEYWORDS`: the set of reserved words. The lexer asks "is this word a keyword?"
- `SYMBOLS`: lookup table from `"<="` to `T.LTE`. Two-character symbols are listed first so `<=` isn't read as `<` then `=`.
- `Token`: a tiny record: `type`, `value`, `line`, `col`. The `line`/`col` are what make good error messages possible later.

#### `errors.py`: the one error type
**Mental model:** one exception class, `PayScriptError(message, line, col)`, used by every station. Because it's the *only* language error, `main.py` can catch it in one place and print `Line 4, col 7: message`.

#### `constants.py`: rules everyone must agree on
**Mental model:** the "shared rulebook". If the parser, validator and interpreter each hard-coded "what fields can an EMPLOYEE have?" they would drift apart. So it's defined once:
- `PAY_KINDS`: `ADD, EXEMPT, CONTRIBUTE, LESS`
- `RESERVED_LABELS`: payslip rows PayScript adds itself (`Basic Pay`, `Tax`...) that users can't reuse
- `COMPUTED_FIELDS`: read-only numbers like `gross`, `net`, `tax`
- `COMPANY_FIELDS` / `EMPLOYEE_FIELDS` / `*_REQUIRED` / `EMPLOYEE_DEFAULTS`: what's allowed, what's mandatory, what defaults apply

#### `ast_nodes.py`: the shape of the tree
**Mental model:** the "blueprint" of a program once it's understood. Every construct in the language gets one small frozen dataclass:
- Expressions (`Expr`): `Literal`, `Name`, `FieldAccess` (`maria.salary`), `IndexAccess` (`list[1]`), `ArrayLiteral`, `UnaryExpr`, `BinaryExpr`, `CallExpr`
- Statements (`Stmt`): `CompanyDecl`, `EmployeeDecl`, `SetStmt`, `PayStmt`, `PayslipStmt`, `PrintStmt`, `IfStmt`, `WhileStmt`, `ForEachStmt`, `ForRangeStmt`, `FunctionDecl`, `ReturnStmt`, `TaxTable`
- Everything is a `Program(statements=[...])` at the top.

Every node carries `line` and `col`, so even a run-time error can point at the exact place in the user's file. Nodes are **frozen**: nobody can mutate the tree after the parser builds it. The full contract is in [ast_contract.md](ast_contract.md).

---

### Station 0: `main.py`, the conductor

**Mental model:** the front desk. It doesn't understand PayScript; it just wires the stations together and turns exceptions into friendly messages and exit codes.

| Function | What it does, simply |
|---|---|
| `read_source(filename)` | Checks the file exists, reads it as UTF-8, gives a clear error if it isn't text. |
| `run_source(source, payslip_dir, strict)` | **The pipeline itself**: `Lexer(source).tokenize()` → `parse(tokens)` → `validate(program)` → `interpret(program, ...)`. Also collects validator warnings and prints them to stderr; with `strict=True` any warning aborts. |
| `main()` | Parses CLI arguments with `argparse` (`run`, `tokens`, `--out`, `--strict`), calls the above, catches `PayScriptError` / file errors / Ctrl+C, and returns an exit code (`0` ok, `1` error, `130` interrupted). |

Why `warnings.catch_warnings` in `run_source`? The validator reports non-fatal problems through Python's `warnings` system. `main.py` collects them and decides: print them, or (with `--strict`) fail.

---

### Station 1: `lexer.py`, text → tokens

**Mental model:** a cursor walking through the text one character at a time, deciding "what kind of thing starts here?" and cutting it out as a token. It has **no idea** whether the tokens make sense together; it only knows what each word *is*.

State it tracks: `pos` (where the cursor is), `line`/`col` (for errors), `tokens` (output so far), `open_brackets` (so newlines inside `( ... )` or `[ ... ]` are ignored).

| Method | What it does, simply |
|---|---|
| `peek(offset)` | Look at a character without moving. Returns `""` past the end. |
| `advance()` | Consume one character and keep `line`/`col` correct. |
| `add_token(...)` | Append a `Token` to the output list. |
| `tokenize()` | **The main loop.** Looks at the current character and dispatches: whitespace → skip, `\n` → NEWLINE token, `//` → comment, `"` → string, digit → number, letter → word, otherwise symbol. At the end, makes sure there's a final NEWLINE and an EOF token. |
| `skip_comment()` | Eats characters until end of line. |
| `read_string()` | Reads `"..."`; errors if the closing quote is missing. |
| `read_number()` | Reads `500` (int) or `1.25` (`Decimal`, exact money math); a trailing `%` makes `20%` into `0.20` as a `PERCENT` token. |
| `read_word()` | Reads a word. In `KEYWORDS` → keyword token; lowercase → `IDENT`; mixed case → error. **This is where the "keywords UPPERCASE, names lowercase" rule is enforced.** |
| `read_symbol()` | Tries two-character symbols first (`<=`, `->`), then one. Tracks bracket depth. Unknown char → error. |

---

### Station 2: `parser.py`, tokens → tree

**Mental model:** grammar police + architect. It reads the flat token list and checks it follows the language's grammar, building a tree as it goes. It's a **recursive-descent parser**: one method per grammar rule, and rules call each other. (Think: "an IF contains a block; a block contains statements; a statement might be another IF.")

Helper methods (the toolbox):

| Method | What it does, simply |
|---|---|
| `parse(tokens)` (module function) | Entry point: `Parser(tokens).parse()`. |
| `peek / advance` | Look at / consume the current token. |
| `check(*types)` | "Is the current token one of these types?" (doesn't consume) |
| `match(*types)` | `check` + consume if true. |
| `expect(type, what)` | Must be this token, else raise a helpful error. |
| `skip_newlines / end_of_statement` | Handle blank lines; require a line break after a statement. |
| `expect_end(opener, what)` | Require the closing `END` and say which opener is unclosed. |
| `error / describe` | Build readable error messages with line/col. |

Structure methods:

| Method | What it does, simply |
|---|---|
| `Parser.parse` | Loop: read lines until EOF → `Program`. |
| `parse_line` / `parse_block` | One statement + newline / a run of lines until `END`/`ELSE`. |
| `parse_statement` | **The dispatcher.** Looks at the first token and picks the right `parse_*` method. |

Statement methods (each returns one AST node):

| Method | Parses |
|---|---|
| `parse_company`, `parse_employee`, `parse_field_lines` | `COMPANY ... END`, `EMPLOYEE x ... END` and their `name value` lines |
| `parse_tax_table`, `parse_tax_row`, `parse_bracket`, `parse_rate` | `TAX ... END` rows like `BELOW 20000 -> 0%` |
| `parse_function`, `parse_return` | `FUNCTION f(a, b) ... END`, `RETURN x` |
| `parse_if`, `parse_while`, `parse_for` | control flow (`FOR EACH x IN list` and `FOR EACH i IN 1 -> 3`) |
| `parse_set`, `parse_target` | `SET x TO value` |
| `parse_pay` | `ADD / EXEMPT / CONTRIBUTE / LESS` (one method for all four) |
| `parse_payslip`, `parse_print` | `PAYSLIP x`, `PRINT a, b` |

Expression methods: **precedence climbing**, one method per precedence level, lowest to highest:

```
parse_expression → parse_or → parse_and → parse_not → parse_comparison
   → parse_additive (+ -) → parse_term (* /) → parse_unary (-x)
   → parse_postfix (.field  [index]) → parse_call → parse_primary (number, string, name, parens)
```

Why this ladder? Because `2 + 3 * 4` has to become `2 + (3 * 4)`. Each level only calls the next-tighter level for its operands, so multiplication naturally binds tighter than addition.

---

### Station 3: `validator.py`, "is this program sane?"

**Mental model:** a proofreader. The parser only knows grammar (`SET x TO y + 1` is grammatical even if `y` doesn't exist). The validator catches meaning problems **before anything runs**, so users don't get a half-finished payslip run followed by a crash.

Key idea: it carries a `_Scope`, a record of "what names/functions/employees exist *so far at this point in the code*". Branches and loops get a `.copy()` so names invented inside don't leak out.

| Function | What it does, simply |
|---|---|
| `validate(program)` | **Entry point.** Exactly one COMPANY, at most one TAX; then runs the two passes below. |
| `_check_structure` / `_bodies` | Pass 1: declarations (COMPANY/EMPLOYEE/TAX/FUNCTION) only at top level. |
| `_check_fields` / `_check_field_value` | Required fields present, no unknown/duplicate fields, values the right kind (text vs number, positive vs non-negative). Uses `constants.py`. |
| `_check_statements` + `_check_company/_employee/_tax_table/_function/_return/_set/_print/_pay/_payslip/_if/_while/_for` | Pass 2: one small checker per statement type, passing the scope along. |
| `_new_name`, `_reserved` | Reject reserved or already-used names. |
| `_has_return` | Every function must end up returning a value. |
| `_check_expression`, `_check_call` | Names defined? Function exists and has the right argument count? |
| `_check_assignment`, `_check_target` | Can't `SET` a computed field (e.g. `maria.net`); pay targets must be employees. |
| `_check_label`, `_number` | Pay label rules (reserved labels, duplicate labels, case-only differences → *warning*). |
| `_check_tax`, `_check_tax_coverage`, `_overlap` | Tax table sanity: no overlapping rows, no gaps, ranges ordered. |
| `PayScriptWarning` | A non-fatal problem class, surfaced via `warnings`. |

---

### Station 4: `interpreter.py`, actually running it

**Mental model:** a tree walker. It starts at the top of `Program.statements` and, for each node, calls a method named after the node's class. This is a classic **"visitor by naming convention"**: `execute()` does `getattr(self, "exec_" + type(stmt).__name__)`, and `evaluate()` does the same with `eval_`. To add a new statement you add a node class and an `exec_<ClassName>` method.

Runtime objects:

| Class | Role |
|---|---|
| `Company` | Holds `working_days`, `hours_per_day`. |
| `Employee` | Holds input fields and the lists of ADD/EXEMPT/CONTRIBUTE/LESS items. Its computed fields (`daily_rate`, `hourly_rate`, `basic_pay`, `gross`, `taxable`, `tax`, `net`...) are **recalculated every time they're read**, so PRINTing before and after an `ADD` shows different numbers. |
| `Function` | A user-defined function (stores its declaration). |
| `ReturnSignal` | An exception used as a "jump out of this function now" mechanism for `RETURN`. |

The payroll math (all in `Employee`): `daily = salary / working_days` → `hourly = daily / hours_per_day` → `basic_pay = salary − absences − tardiness` → `gross = basic + overtime(×1.25) + ADD + EXEMPT` → `tax` from the table on `taxable = basic + overtime + ADD − CONTRIBUTE` → `net = gross − CONTRIBUTE − tax − LESS`.

`Interpreter` methods, grouped:

| Group | Methods | Simple explanation |
|---|---|---|
| Entry | `run`, `results`, `execute_block`, `execute` | Walk statements; dispatch by node class name. |
| Declarations | `exec_CompanyDecl`, `exec_EmployeeDecl`, `exec_TaxTable`, `exec_FunctionDecl` | Store the company, create `Employee` objects, prepare tax rows, register functions. |
| Actions | `exec_SetStmt`, `exec_PayStmt`, `exec_PayslipStmt`, `exec_PrintStmt` | Assign variables, record pay items, write payslips, print. |
| Control flow | `exec_IfStmt`, `exec_WhileStmt`, `exec_ForEachStmt`, `exec_ForRangeStmt`, `exec_ReturnStmt` | Branch and loop (loops stop at `MAX_LOOP_ITERATIONS`, calls at `MAX_CALL_DEPTH`). |
| Expressions | `evaluate`, `eval_Literal`, `eval_Name`, `eval_FieldAccess`, `eval_IndexAccess`, `eval_UnaryExpr`, `eval_BinaryExpr`, `eval_ArrayLiteral` | Turn an expression node into a Python value. |
| Calls | `eval_CallExpr`, `call_input`, `call_length`, `call_function` | Built-ins (`INPUT`, `LENGTH`) and user functions (new scope pushed on `self.scopes`). |
| Helpers | `lookup`, `resolve_employee`, `number`, `boolean`, `condition`, `require_numbers`, `require_same_type`, `array_index` | Safe variable lookup and type checks with good errors. |
| Tax | `prepare_tax_rows`, `compute_tax` | Convert the tax table once; find the matching row and compute `fixed + rate × (taxable − base)`. |
| Payslip | `payslip_lines`, `render_payslip`, `write_payslip` | Build the rows, align the columns, write `payslips/<handle>.txt`. |

Module-level helpers: `money()` (round to centavos with `ROUND_HALF_UP`), `normalize`, `copy_value`, `format_value`, `format_money`, `convert_input` (turns typed `INPUT` text into number/text), and `interpret()` (the convenience wrapper `main.py` calls).

Design detail worth noticing: the interpreter takes `output=print` and `input_fn=input` as *parameters*. That's **dependency injection**: tests can pass fake ones instead of touching the real terminal.

---

### Not part of the pipeline, but part of the repo

| File | Why it exists |
|---|---|
| `tests/` | pytest suite, roughly one file per station (`test_lexer.py`, `test_parser.py`, ...). |
| `samples/valid`, `samples/invalid` | Example `.ps` programs; the comments (`// expect-out:`, `// expect-error:`) are the expected results. |
| `run_samples.py` | Runs every sample through the real CLI and reports PASS/FAIL. |
| `bench.py` | Benchmarking helper. |
| `docs/` | Language documentation and the AST contract. |
| `payscript.egg-info/` | **Generated** by `pip install -e .`. Not source. Already in `.gitignore`. |

---

## 4. How `payscript run file.ps` works in the terminal

Two pieces make this work. Neither is magic.

### Piece 1: `main()` is an ordinary Python function

In `pyproject.toml`:

```toml
[project.scripts]
payscript = "payscript.main:main"
```

Read it as: *"create a command called `payscript`. When it's run, import the module `payscript.main` and call the function `main()`."*

### Piece 2: pip generates a tiny launcher for it

When you run `pip install .` (or `pip install -e .` as you did for development), pip reads that line and creates a small executable file in the environment's `Scripts` folder. You can see it in your own machine:

```
.venv\Scripts\payscript.exe          ← the launcher pip generated (Windows)
```

(On Linux/macOS it's a small script at `.venv/bin/payscript`.)

That launcher is basically:

```python
from payscript.main import main
raise SystemExit(main())      # the return value (0 / 1) becomes the exit code
```

### Putting it together

```
you type:   payscript run payroll.ps --out out
                │
                ▼
     shell finds payscript.exe on PATH   (the venv's Scripts folder is on PATH when activated)
                │
                ▼
     launcher imports payscript.main and calls main()
                │
                ▼
     argparse reads sys.argv:  command="run", filename="payroll.ps", out="out"
                │
                ▼
     read_source → run_source → Lexer → parse → validate → interpret
                │
                ▼
     exit code 0 (success) or 1 (error)
```

Things to notice:
- **"On PATH" is the real requirement.** The command works only where the folder holding `payscript.exe` is on `PATH`. A virtualenv's `activate` script does that for you.
- `if __name__ == "__main__": raise SystemExit(main())` at the bottom of `main.py` is a *second* way in: `python payscript/main.py run file.ps`. It's useful, but it's not what the `payscript` command uses.
- **Gap I noticed:** there's no `payscript/__main__.py`, so `python -m payscript run file.ps` will **not** work. It's a 3-line file to add (`from payscript.main import main; raise SystemExit(main())`) and is a nice fallback when `Scripts` isn't on PATH.

### Why does it work from any folder in your setup?

You installed in editable mode (`pip install -e .`). The file `.venv\Lib\site-packages\__editable___payscript_0_1_0_finder.py` contains a mapping that says "when someone imports `payscript`, load it from `...\PayScript\PayScript\payscript`". So your launcher runs your *live working copy*; edit the code and the next `payscript run` uses it. That's a **developer convenience**, not how end users get it (next section).

---

## 5. Packaging and installing it "like a real language"

### The short answers

1. **Can users install it without cloning the repo?** Yes. That's what a Python *package* does.
2. **Will they see the repo's files (tests, samples, docs, `.git`)?** No. Only what you explicitly package.
3. **Will they see the `.py` source of the language itself?** Yes, with the default approach, and that's normal. See below.

### Where the "like Python" comparison needs a correction

When you install Python you do not get "the language without its source" in the way you might expect:
- The **interpreter** (`python.exe`) is compiled C. You get the binary, not the C source.
- But Python's **standard library is installed as plain `.py` files** (look in `Lib/` of any Python install). The code for `argparse`, `pathlib` etc. is right there and readable.

So even "real" languages often ship readable source for the parts written in themselves. PayScript is written *in Python*, so the "binary" is Python itself. Installed PayScript will be `.py` files inside `site-packages/payscript/`. That's perfectly normal and nobody finds it strange. What users *won't* have is the repo scaffolding.

### The standard route: build a wheel and `pip install` it

What goes into a distribution is decided by `pyproject.toml`:

```toml
[tool.setuptools]
packages = ["payscript"]     # ONLY this folder is packaged
```

So the shipped artifact contains `payscript/*.py` plus metadata, and **not** `tests/`, `samples/`, `docs/`, `bench.py`, `run_samples.py` or `.git`.

```
python -m pip install build
python -m build                    # creates dist/payscript-0.1.0-py3-none-any.whl
                                   #         dist/payscript-0.1.0.tar.gz
```

On another machine:

```
pip install payscript-0.1.0-py3-none-any.whl        # from the file
# or, after uploading to PyPI:
pip install payscript
# or straight from GitHub:
pip install git+https://github.com/<you>/PayScript.git
```

The install does two things you already saw locally: copies `payscript/` into `site-packages`, and generates the `payscript` launcher from `[project.scripts]`. Afterwards `payscript run file.ps` works anywhere, and the repo isn't needed at all.

**Requirement:** the target machine needs Python ≥ 3.10 (`requires-python` in `pyproject.toml`). There are no third-party runtime dependencies (only `pytest`/`ruff` under `dev`), which makes this easy.

Tip: `pipx install payscript` is the nicest end-user experience for CLI tools. It puts the command on PATH in its own isolated environment.

### If you want "no Python needed, just a payscript.exe"

| Option | What users get | Source visible? | Notes |
|---|---|---|---|
| **Wheel / PyPI** (above) | `pip install` → command | Yes, `.py` files in site-packages | Simplest, standard, needs Python |
| **PyInstaller / `shiv`** | One `payscript.exe` bundling Python + your code | Bundled as bytecode inside the exe; not casually readable, but recoverable | Works with no Python installed; bigger file; build per OS |
| **Nuitka** | A real compiled native executable | Compiled to C, much harder to reverse | Slower build, closest to "Python's own binary" |

For a school/portfolio language, the wheel is the right answer. Reach for PyInstaller when someone says "my users don't have Python."

### What you'd need to do before shipping

1. **Check `README.md` and `LICENSE` are what you want public**, since both are referenced by `pyproject.toml`.
2. **Add `payscript/__main__.py`** (so `python -m payscript` works).
3. **Bump `version`** in *both* `pyproject.toml` and `payscript/__init__.py` (they're duplicated today; consider making one the source of truth).
4. **Build in a clean environment and test it** (`python -m venv test_env`, install the wheel, run a sample from a different folder). This catches "works only because the repo is next to it" bugs.
5. **Add `authors`, `classifiers`, `urls`** to `pyproject.toml` if publishing publicly.

### Quick sanity check you can run yourself

```
python -m pip install build
python -m build
python -m venv ..\scratch_env
..\scratch_env\Scripts\pip install dist\payscript-0.1.0-py3-none-any.whl
..\scratch_env\Scripts\payscript run samples\valid\01_basic_salary.ps
```

If that prints `Juan Dela Cruz 25000.00` from a venv that has never seen your repo, you've proven the packaging works. (I haven't run this build here; the description above is how the configuration in your `pyproject.toml` behaves.)

---

## 6. Cheat sheet

| Question | Answer |
|---|---|
| Where does the pipeline order live? | `run_source()` in `main.py` |
| Where is the keyword/name casing rule? | `Lexer.read_word` |
| Where is operator precedence? | The `parse_or → ... → parse_primary` ladder in `parser.py` |
| Where do "undefined variable" errors come from? | `validator.py` (`_check_expression`) |
| Where is the payroll formula? | `Employee` in `interpreter.py` |
| Where is the tax lookup? | `Interpreter.compute_tax` |
| What creates the `payscript` command? | `[project.scripts]` in `pyproject.toml` + pip's launcher |
| What decides what ships to users? | `[tool.setuptools] packages` in `pyproject.toml` |
| How do I add a new employee field? | `constants.py` (+ `Employee` methods if computed); a test checks they match |
| How do I add a new statement? | New node in `ast_nodes.py`, `parse_*` in the parser, `_check_*` in the validator, `exec_*` in the interpreter |
