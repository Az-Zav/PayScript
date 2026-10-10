"""Smoke tests for the initialized PayScript package."""

from payscript import __version__
from payscript.errors import PayScriptError
from payscript.tokens import T, Token


def test_package_has_version():
    assert __version__ == "0.1.0"


def test_token_can_be_constructed():
    token = Token(T.IDENT, "employee", 1, 1)
    assert token.value == "employee"


def test_error_is_exception():
    assert issubclass(PayScriptError, Exception)
