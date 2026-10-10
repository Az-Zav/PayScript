"""Lexer: every keyword, symbol, literal form and lexical error."""

from decimal import Decimal

import pytest

from payscript.errors import PayScriptError
from payscript.tokens import KEYWORDS, SYMBOLS, T

from conftest import tokens


def types(source):
    return [t.type for t in tokens(source)]


@pytest.mark.parametrize("word", sorted(KEYWORDS))
def test_every_keyword_is_recognised(word):
    first = tokens(word)[0]
    assert first.type is T[word]
    assert first.value == word


def test_keyword_set_matches_the_documented_grammar():
    documented = set(
        "COMPANY EMPLOYEE END TAX BELOW ABOVE ADD EXEMPT CONTRIBUTE LESS "
        "PAYSLIP PRINT SET TO IF THEN ELSE WHILE FOR EACH IN FUNCTION RETURN "
        "INPUT LENGTH AND OR NOT TRUE FALSE".split())
    assert KEYWORDS == documented


@pytest.mark.parametrize("text,type_", sorted(SYMBOLS.items()))
def test_every_symbol_is_recognised(text, type_):
    assert tokens(text)[0].type is type_


def test_two_character_symbols_win_over_one_character():
    assert types("<= >= != ->")[:4] == [T.LTE, T.GTE, T.NEQ, T.ARROW]
    assert types("< =")[:2] == [T.LT, T.EQ]


def test_identifier_forms():
    toks = tokens("maria x1 total_pay2")
    assert [t.type for t in toks[:3]] == [T.IDENT] * 3
    assert [t.value for t in toks[:3]] == ["maria", "x1", "total_pay2"]


def test_integer_float_and_percent_values():
    a, b, c, d = tokens("500 1.25 20% 12.5%")[:4]
    assert (a.type, a.value) == (T.NUMBER, 500) and isinstance(a.value, int)
    assert (b.type, b.value) == (T.NUMBER, Decimal("1.25"))
    assert (c.type, c.value) == (T.PERCENT, Decimal("0.20"))
    assert (d.type, d.value) == (T.PERCENT, Decimal("0.125"))


def test_number_followed_by_dot_without_digit_is_not_a_float():
    assert types("3.x")[:3] == [T.NUMBER, T.DOT, T.IDENT]


def test_string_keeps_its_text_and_may_contain_symbols_and_keywords():
    tok = tokens('"ADD // 50% off"')[0]
    assert (tok.type, tok.value) == (T.STRING, "ADD // 50% off")


def test_empty_string():
    assert tokens('""')[0].value == ""


def test_comments_are_ignored():
    assert types("// nothing here") == [T.EOF]
    assert types("SET x TO 1 // trailing")[:5] == [
        T.SET, T.IDENT, T.TO, T.NUMBER, T.NEWLINE]


def test_newlines_become_tokens_and_end_of_file_is_added():
    assert types("PRINT x\nPRINT y") == [
        T.PRINT, T.IDENT, T.NEWLINE, T.PRINT, T.IDENT, T.NEWLINE, T.EOF]


def test_newlines_inside_parentheses_and_brackets_are_ignored():
    assert T.NEWLINE not in types("f(1,\n 2)")[:-2]
    assert T.NEWLINE not in types("[1,\n 2,\n 3]")[:-2]


def test_crlf_line_endings_are_normalised():
    assert types("PRINT x\r\nPRINT y") == types("PRINT x\nPRINT y")


def test_empty_source_is_just_eof():
    assert types("") == [T.EOF]


def test_positions_are_one_based_line_and_column():
    toks = tokens('ADD maria "Bonus" 500\n  PRINT x')
    assert (toks[0].line, toks[0].col) == (1, 1)
    assert (toks[1].line, toks[1].col) == (1, 5)
    assert (toks[2].line, toks[2].col) == (1, 11)
    assert (toks[3].line, toks[3].col) == (1, 19)
    print_tok = next(t for t in toks if t.type is T.PRINT)
    assert (print_tok.line, print_tok.col) == (2, 3)


# ---------- errors ----------

def error_of(source):
    with pytest.raises(PayScriptError) as info:
        tokens(source)
    return info.value


@pytest.mark.parametrize("char", list("@#$&~^|;:?!{}`'\\"))
def test_unknown_character(char):
    err = error_of(f"SET x TO 1 {char}")
    assert f"unknown character '{char}'" in err.message
    assert (err.line, err.col) == (1, 12)


def test_unterminated_string_points_at_the_opening_quote():
    err = error_of('PRINT "oops\nPRINT 1')
    assert err.message == "unterminated string"
    assert (err.line, err.col) == (1, 7)


def test_unterminated_string_at_end_of_file():
    assert error_of('"abc').message == "unterminated string"


@pytest.mark.parametrize("word", ["Maria", "ADDx", "Add", "mAria", "Employee", "_x"])
def test_wrong_case_words_are_rejected(word):
    err = error_of(word)
    assert "unknown word" in err.message and word in err.message


def test_lowercase_keyword_is_just_an_identifier():
    assert tokens("add")[0].type is T.IDENT


def test_error_text_format_is_line_col_message():
    assert str(error_of("\n  @")) == "Line 2, col 3: unknown character '@'"
