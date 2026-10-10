"""Shared helpers for the pytest suite."""

import warnings
from pathlib import Path

import pytest

from payscript.interpreter import interpret
from payscript.lexer import Lexer
from payscript.parser import parse
from payscript.validator import validate

ROOT = Path(__file__).resolve().parent.parent

COMPANY = 'COMPANY\n    working_days 22\n    hours_per_day 8\nEND\n'
MARIA = 'EMPLOYEE maria\n    name "Maria"\n    salary 22000\nEND\n'
BASE = COMPANY + MARIA


def tokens(source):
    return Lexer(source).tokenize()


def parse_source(source):
    return parse(tokens(source))


def check(source):
    """Lex, parse and validate. Returns the list of warnings raised."""
    program = parse_source(source)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate(program)
    return caught


class Result:
    def __init__(self, lines, payslip_dir, warns):
        self.lines = lines
        self.payslip_dir = payslip_dir
        self.warnings = warns

    def payslip(self, handle):
        return (self.payslip_dir / f"{handle}.txt").read_text(encoding="utf-8")


@pytest.fixture
def run(tmp_path):
    """run(source, inputs=()) -> Result; the full pipeline, payslips in tmp_path."""
    def _run(source, inputs=()):
        queue = list(inputs)
        lines = []

        def fake_input(prompt=""):
            lines.append(prompt)
            if not queue:
                raise EOFError
            return queue.pop(0)

        program = parse_source(source)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            validate(program)
        interpret(program, output=lines.append, input_fn=fake_input,
                  payslip_dir=str(tmp_path))
        return Result(lines, tmp_path, caught)
    return _run


@pytest.fixture
def out(run):
    """out(source, inputs=()) -> list of PRINT lines (BASE is prepended)."""
    def _out(body, inputs=()):
        return run(BASE + body, inputs).lines
    return _out
