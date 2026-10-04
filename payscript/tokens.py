"""Token definitions for the PayScript lexer."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Generic token categories; language-specific keywords are TBD."""

    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    KEYWORD = auto()
    OPERATOR = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    """A token produced by the lexer."""

    type: TokenType
    value: str
    line: int
    column: int
