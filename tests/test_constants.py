"""The shared language rules in payscript/constants.py stay consistent."""

from payscript import constants, interpreter, parser, validator
from payscript.tokens import T


def test_computed_fields_match_what_the_interpreter_computes():
    assert set(interpreter.Employee.COMPUTED) == set(constants.COMPUTED_FIELDS)


def test_every_computed_field_is_a_reserved_name():
    assert set(constants.COMPUTED_FIELDS) <= constants.RESERVED_NAMES
    assert {"company", "employees"} <= constants.RESERVED_NAMES


def test_required_fields_are_declared_fields():
    assert set(constants.COMPANY_REQUIRED) <= set(constants.COMPANY_FIELDS)
    assert set(constants.EMPLOYEE_REQUIRED) <= set(constants.EMPLOYEE_FIELDS)


def test_defaults_are_for_optional_declared_fields_only():
    defaults = set(constants.EMPLOYEE_DEFAULTS)
    assert defaults <= set(constants.EMPLOYEE_FIELDS)
    assert not defaults & set(constants.EMPLOYEE_REQUIRED)


def test_number_fields_are_derived_from_the_field_table():
    assert set(constants.EMPLOYEE_NUMBER_FIELDS) == {
        name for name, (kind, _) in constants.EMPLOYEE_FIELDS.items()
        if kind == "number"}


def test_stages_use_the_shared_objects_not_private_copies():
    assert validator.RESERVED_NAMES is constants.RESERVED_NAMES
    assert validator.RESERVED_LABELS is constants.RESERVED_LABELS
    assert interpreter.RESERVED_LABELS is constants.RESERVED_LABELS
    assert interpreter.PAY_KINDS is constants.PAY_KINDS
    assert validator.EMPLOYEE_FIELDS is constants.EMPLOYEE_FIELDS


def test_parser_pay_tokens_cover_every_pay_kind():
    assert [t.name for t in parser.PAY_KINDS] == list(constants.PAY_KINDS)
    assert all(isinstance(t, T) for t in parser.PAY_KINDS)
