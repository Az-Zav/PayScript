"""Command-line interface for PayScript."""

import argparse
from pathlib import Path

from payscript.errors import PayScriptError


def _run_file(filename: str) -> None:
    path = Path(filename)
    if not path.is_file():
        raise PayScriptError(f"PayScript file not found: {path}")
    raise PayScriptError("PayScript execution is not implemented yet.")


def main() -> int:
    """Run the PayScript command-line interface."""
    parser = argparse.ArgumentParser(prog="payscript")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run a PayScript source file")
    run_parser.add_argument("filename", help="path to a .ps source file")
    args = parser.parse_args()

    try:
        if args.command == "run":
            _run_file(args.filename)
    except PayScriptError as error:
        parser.exit(1, f"payscript: error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
