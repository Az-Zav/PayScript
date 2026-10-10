"""PayScript benchmark.

Run from the folder that CONTAINS the `payscript` package folder:

    python bench.py                      # synthetic scaling test (1-1000 employees)
    python bench.py samples\\*.ps         # also time your own .ps files
    python bench.py --reps 50            # more repetitions = steadier numbers

Times are medians in milliseconds. Payslips go to a temp folder, not yours.
"""
import argparse, glob, os, platform, shutil, statistics, sys, tempfile, time

from payscript.lexer import Lexer
from payscript.parser import parse
from payscript.validator import validate
from payscript.interpreter import interpret


def gen(n):
    """Build a PayScript program with n employees (1 ADD, 1 LESS, 1 PRINT each)."""
    s = "COMPANY\n    working_days 22\n    hours_per_day 8\nEND\n\n"
    for i in range(n):
        s += f'EMPLOYEE e{i}\n    name "Emp {i}"\n    salary {20000 + i}\n    position "Staff"\nEND\n'
        s += f'ADD e{i} "Bonus" 500\nLESS e{i} "Loan" 200\n'
    for i in range(n):
        s += f"PRINT e{i}.name, e{i}.net\n"
    return s


def median_ms(fn, reps):
    times = []
    for _ in range(reps):
        start = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times), result


def time_stages(src, reps, slipdir):
    lex, toks = median_ms(lambda: Lexer(src).tokenize(), reps)
    par, prog = median_ms(lambda: parse(toks), reps)
    val, _ = median_ms(lambda: validate(prog), reps)
    run, _ = median_ms(lambda: interpret(prog, output=lambda *a: None,
                                         input_fn=lambda *a: "0", payslip_dir=slipdir), reps)
    return len(toks), lex, par, val, run


def row(label, toks, lex, par, val, run):
    print(f"{label:<22}{toks:>8}{lex:>9.2f}{par:>9.2f}{val:>10.2f}{run:>12.2f}{lex+par+val+run:>9.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="your own .ps files to time")
    ap.add_argument("--reps", type=int, default=30)
    args = ap.parse_args()

    print(f"Python {platform.python_version()} | {platform.system()} {platform.release()} | "
          f"{platform.machine()} | {os.cpu_count()} logical CPUs\n")
    head = f"{'Program':<22}{'Tokens':>8}{'Lexer':>9}{'Parser':>9}{'Validator':>10}{'Interpreter':>12}{'Total':>9}"
    print(head + "\n" + "-" * len(head))

    slipdir = tempfile.mkdtemp()
    try:
        for n in (1, 10, 100, 1000):
            reps = args.reps if n <= 100 else max(5, args.reps // 6)
            row(f"synthetic {n} emp", *time_stages(gen(n), reps, slipdir))

        paths = [p for pat in args.files for p in (glob.glob(pat) or [pat])]
        for p in paths:
            try:
                src = open(p, encoding="utf-8").read()
                row(os.path.basename(p)[:21], *time_stages(src, args.reps, slipdir))
            except Exception as e:  # invalid samples or ones needing INPUT
                print(f"{os.path.basename(p)[:21]:<22} skipped: {e}")

        # payslip file writing
        src = gen(100) + "".join(f"PAYSLIP e{i}\n" for i in range(100))
        prog = parse(Lexer(src).tokenize())
        t, _ = median_ms(lambda: interpret(prog, output=lambda *a: None, payslip_dir=slipdir), 10)
        print(f"\n100 payslips written: {t:.1f} ms")
    finally:
        shutil.rmtree(slipdir, ignore_errors=True)


if __name__ == "__main__":
    main()