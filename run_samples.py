"""Run every sample program and report PASS or FAIL.

Usage:
    python run_samples.py              run all samples
    python run_samples.py 02 bad_char  run only samples whose name contains a word

Each sample states what it expects in ordinary // comments:

    // input: 500                  one line typed into INPUT() (repeat for more)
    // expect-out: <text>          what the program prints (repeat for more lines)
    // expect-payslip maria:       followed by comment lines holding payslips/maria.txt
    //   Maria Santos
    //   Basic Pay            22000.00
    // expect-error: Line 9, col 9: unknown character '@'

A sample with no expectation only has to run without an error.
Whitespace is compared loosely (runs of spaces count as one), so the
check is about content and order, not exact column alignment.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE_FOLDERS = ("valid", "invalid")


def normalize(text):
    return re.sub(r"[ \t]+", " ", text).strip()


def normalize_lines(text):
    return [normalize(line) for line in text.strip().splitlines()]


def parse_expectations(source):
    """Read the // annotations of a sample into a dict."""
    exp = {"input": [], "out": [], "payslips": {}, "error": None}
    current = None  # handle of the payslip block being read
    for raw in source.splitlines():
        line = raw.strip()
        if current is not None and re.match(r"^//\s{2,}\S", raw):
            exp["payslips"][current].append(line[2:].strip())
            continue
        current = None
        if line.startswith("// input:"):
            exp["input"].append(line[len("// input:"):].strip())
        elif line.startswith("// expect-out:"):
            exp["out"].append(line[len("// expect-out:"):].strip())
        elif line.startswith("// expect-error:"):
            exp["error"] = line[len("// expect-error:"):].strip()
        else:
            m = re.match(r"^// expect-payslip\s+(\w+)\s*:", line)
            if m:
                current = m.group(1)
                exp["payslips"][current] = []
    return exp


def check(exp, returncode, stdout, stderr, payslip_dir):
    """Return a list of problems (an empty list means the sample passed)."""
    problems = []

    if exp["error"] is not None:
        if returncode == 0:
            problems.append("expected an error but the program succeeded")
        error_lines = [normalize(l) for l in stderr.splitlines()]
        if normalize(exp["error"]) not in error_lines:
            problems.append(f"expected error: {exp['error']}\n"
                            f"      got stderr:     {stderr.strip() or '(nothing)'}")
        return problems

    if returncode != 0:
        problems.append(f"program failed (exit {returncode}): {stderr.strip()}")
        return problems

    if exp["out"]:
        want = [normalize(l) for l in exp["out"]]
        got = normalize_lines(stdout)
        if got != want:
            problems.append(f"output differs\n      expected: {want}\n      got:      {got}")

    for handle, expected_lines in exp["payslips"].items():
        path = Path(payslip_dir) / f"{handle}.txt"
        if not path.is_file():
            problems.append(f"payslip {handle}.txt was not written")
            continue
        want = [normalize(l) for l in expected_lines]
        got = normalize_lines(path.read_text(encoding="utf-8"))
        if got != want:
            problems.append(f"payslip {handle}.txt differs\n"
                            f"      expected: {want}\n      got:      {got}")
    return problems


def run_sample(path):
    """Run one sample in a scratch folder. Returns (problems, exp)."""
    exp = parse_expectations(path.read_text(encoding="utf-8"))
    stdin = "".join(line + "\n" for line in exp["input"])
    with tempfile.TemporaryDirectory() as scratch:
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "payscript.main", "run", str(path)],
            input=stdin, capture_output=True, text=True, encoding="utf-8",
            cwd=scratch, env=env, timeout=30,
        )
        problems = check(exp, result.returncode, result.stdout, result.stderr,
                         Path(scratch) / "payslips")
    return problems


def main(argv=None):
    words = (argv if argv is not None else sys.argv[1:])
    passed = failed = 0
    for folder in SAMPLE_FOLDERS:
        for path in sorted((ROOT / "samples" / folder).glob("*.ps")):
            if words and not any(w in path.name for w in words):
                continue
            label = f"{folder}/{path.name}"
            try:
                problems = run_sample(path)
            except subprocess.TimeoutExpired:
                problems = ["timed out after 30 seconds"]
            if problems:
                failed += 1
                print(f"FAIL  {label}")
                for problem in problems:
                    print(f"      {problem}")
            else:
                passed += 1
                print(f"PASS  {label}")
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())