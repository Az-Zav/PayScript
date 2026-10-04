"""Smoke tests for the initialized PayScript package."""

import unittest

from payscript import __version__
from payscript.errors import PayScriptError
from payscript.tokens import Token, TokenType


class ScaffoldTests(unittest.TestCase):
    def test_package_has_version(self) -> None:
        self.assertEqual(__version__, "0.1.0")

    def test_token_can_be_constructed(self) -> None:
        token = Token(TokenType.IDENTIFIER, "employee", 1, 1)
        self.assertEqual(token.value, "employee")

    def test_error_is_exception(self) -> None:
        self.assertTrue(issubclass(PayScriptError, Exception))


if __name__ == "__main__":
    unittest.main()
