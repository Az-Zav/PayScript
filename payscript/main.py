"""Command-line interface for PayScript.

Usage:  payscript run <file.ps> [--out DIR] [--strict]
        payscript tokens <file.ps>     (debug: print the token stream)

Pipeline:  source -> Lexer -> parse -> validate -> interpret
"""

import argparse
import sys
import warnings
from pathlib import Path

from payscript.errors import PayScriptError
from payscript.interpreter import interpret
from payscript.lexer import Lexer
from payscript.parser import parse
from payscript.validator import validate


def read_source(filename):
    path = Path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"file not found: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not a valid UTF-8 text file") from None


def run_source(source, payslip_dir="payslips", strict=False):
    """Run PayScript source text through every stage.

    Raises PayScriptError for any language error (lexical, syntax, semantic
    or run-time). Validator warnings are printed to stderr; with strict=True
    any warning stops the run before the interpreter starts.
    """
    try:
        tokens = Lexer(source).tokenize()
        program = parse(tokens)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            validate(program)
        for warning in caught:
            print(f"warning: {warning.message}", file=sys.stderr)
        if strict and caught:
            raise ValueError(f"{len(caught)} warning(s) reported (--strict)")

        interpret(program, output=print, input_fn=input, payslip_dir=payslip_dir)
    except RecursionError:
        raise ValueError(
            "the program is nested too deeply (too many nested brackets, "
            "blocks or chained operators)"
        ) from None


def main() -> int:
    """Run the PayScript command-line interface."""
    arg_parser = argparse.ArgumentParser(prog="payscript")
    subparsers = arg_parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run a PayScript source file")
    run_parser.add_argument("filename", help="path to a .ps source file")
    run_parser.add_argument("--out", default="payslips", metavar="DIR",
                            help="folder for generated payslips (default: payslips)")
    run_parser.add_argument("--strict", action="store_true",
                            help="treat validator warnings as errors")
    tokens_parser = subparsers.add_parser(
        "tokens", help="print the token stream of a source file (debugging)")
    tokens_parser.add_argument("filename", help="path to a .ps source file")
    args = arg_parser.parse_args()

    try:
        source = read_source(args.filename)
        if args.command == "tokens":
            for token in Lexer(source).tokenize():
                print(f"{token.type.name:12} {token.value!r:24} "
                      f"Line {token.line} Col {token.col}")
            return 0
        run_source(source, payslip_dir=args.out, strict=args.strict)
    except PayScriptError as error:
        # str(error) is already "Line 4, col 7: message"
        print(error, file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as error:
        print(f"payscript: error: {error}", file=sys.stderr)
        return 1
    except EOFError:
        print("payscript: error: INPUT needed more input than was given",
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\npayscript: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())