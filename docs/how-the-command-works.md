# How the `payscript` command works, and how it ships

Background reading: how pip turns a Python function into a terminal command,
and how PayScript is packaged and installed on other machines. For a tour of
the code itself, see [architecture.md](architecture.md).

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