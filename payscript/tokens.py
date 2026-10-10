# tokens.py
#
# What is this file?
# The shared "vocabulary" of PayScript. It has no logic. It just defines
# the pieces that the lexer produces and the parser reads.
#
# How the pieces fit together:
#   The lexer chops source text into small labeled pieces called tokens.
#   Example: ADD maria "Bonus" 500
#   becomes:  ADD, maria, "Bonus", 500
#   Each piece is a Token, and each Token has a type from the list T.
#
# Who uses it:
#   Dev 1 (lexer):  creates Tokens using T, KEYWORDS and SYMBOLS.
#   Dev 2 (parser): reads Tokens and checks their type, e.g. tok.type == T.THEN.
#   Everyone else:  rarely needs it.
#
# Rule: don't change this file alone. Post changes in the group chat first,
# because Dev 2 and Dev 4 depend on it.
#
# ------------------------------------------------------------------

from dataclasses import dataclass   # makes simple "record" classes
from enum import Enum, auto         # makes a fixed list of named choices


# T = the menu of every token type that exists.
# Use the names (T.ADD, T.PLUS), never plain text, so typos get caught.
# auto() just gives each name a unique number. Ignore it.
class T(Enum):
    # Names and values
    IDENT = auto(); NUMBER = auto(); STRING = auto(); PERCENT = auto()
    # Structure
    NEWLINE = auto(); EOF = auto()
    # Keywords: declarations
    COMPANY = auto(); EMPLOYEE = auto(); END = auto(); TAX = auto()
    BELOW = auto(); ABOVE = auto(); FUNCTION = auto(); RETURN = auto()
    # Keywords: pay and output
    ADD = auto(); EXEMPT = auto(); CONTRIBUTE = auto(); LESS = auto()
    PAYSLIP = auto(); PRINT = auto()
    # Keywords: control flow
    SET = auto(); TO = auto(); IF = auto(); THEN = auto(); ELSE = auto()
    WHILE = auto(); FOR = auto(); EACH = auto(); IN = auto()
    # Keywords: built-ins and logic
    INPUT = auto(); LENGTH = auto()
    AND = auto(); OR = auto(); NOT = auto(); TRUE = auto(); FALSE = auto()
    # Symbols
    EQ = auto(); NEQ = auto(); LT = auto(); LTE = auto(); GT = auto(); GTE = auto()
    PLUS = auto(); MINUS = auto(); STAR = auto(); SLASH = auto(); ARROW = auto()
    DOT = auto(); COMMA = auto()
    LPAREN = auto(); RPAREN = auto(); LBRACKET = auto(); RBRACKET = auto()


# KEYWORDS = the reserved words, as a set.
# The lexer asks: "I just read the word ADD. Is it a keyword?"
# (Built by taking all of T and removing the non-keywords.)
KEYWORDS = {t.name for t in T if t.name.isupper() and t.name not in
            {"IDENT","NUMBER","STRING","PERCENT","NEWLINE","EOF","EQ","NEQ","LT",
             "LTE","GT","GTE","PLUS","MINUS","STAR","SLASH","ARROW","DOT","COMMA",
             "LPAREN","RPAREN","LBRACKET","RBRACKET"}}


# SYMBOLS = a lookup table: symbol text -> token type.
# The lexer reads "<=" and looks up T.LTE.
# Two-character symbols come first so "<=" isn't read as "<" then "=".
SYMBOLS = {
    "->": T.ARROW, "<=": T.LTE, ">=": T.GTE, "!=": T.NEQ,
    "=": T.EQ, "<": T.LT, ">": T.GT, "+": T.PLUS, "-": T.MINUS,
    "*": T.STAR, "/": T.SLASH, ".": T.DOT, ",": T.COMMA,
    "(": T.LPAREN, ")": T.RPAREN, "[": T.LBRACKET, "]": T.RBRACKET,
}


# Token = one piece of the source code.
#   type:  what kind it is (a value from T)
#   value: what it contained (the word, number, or string text)
#   line:  which line it was on
#   col:   which column it started at
# Example: Token(T.NUMBER, 500, 9, 19) = "the number 500 at line 9, column 19".
# Line and col are what make errors like "Line 4, col 7" possible.
#
# Value rules (agree on these): 20% is stored as 0.20, 500 is an int,
# 1.25 is a Decimal (exact, no binary rounding).
@dataclass
class Token:
    type: T
    value: object
    line: int
    col: int