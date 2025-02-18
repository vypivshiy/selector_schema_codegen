import pytest
from ssc_codegen.str_utils import (
    to_snake_case,
    to_upper_camel_case,
    to_lower_camel_case,
    wrap_double_quotes,
    wrap_backtick,
    escape_str,
)


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        ("camelCase", "camel_case"),
        ("PascalCase", "pascal_case"),
        ("already_snake_case", "already_snake_case"),
        ("Mixed_Case_Example", "mixed_case_example"),
        ("", ""),
    ],
)
def test_to_snake_case(input_str: str, expected_output: str) -> None:
    assert to_snake_case(input_str) == expected_output


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        ("snake_case", "SnakeCase"),
        ("alreadyCamelCase", "AlreadyCamelCase"),
        ("mixed_case_example", "MixedCaseExample"),
        ("", ""),
    ],
)
def test_to_upper_camel_case(input_str, expected_output) -> None:
    assert to_upper_camel_case(input_str) == expected_output


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        ("snake_case", "snakeCase"),
        ("AlreadyCamelCase", "alreadyCamelCase"),
        ("mixed_case_example", "mixedCaseExample"),
        ("", ""),
    ],
)
def test_to_lower_camel_case(input_str, expected_output) -> None:
    assert to_lower_camel_case(input_str) == expected_output


@pytest.mark.parametrize(
    "input_str, escape_ch, expected_output",
    [
        ("hello", "\\", '"hello"'),
        ('hello"world', "\\", '"hello\\"world"'),
        ("", "\\", '""'),
        ('hello"world', "*", '"hello*"world"'),
    ],
)
def test_wrap_double_quotes(input_str, escape_ch, expected_output) -> None:
    assert wrap_double_quotes(input_str, escape_ch) == expected_output


@pytest.mark.parametrize(
    "input_str, escape_ch, expected_output",
    [
        ("hello", "\\", "`hello`"),
        ("hello`world", "\\", "`hello\\`world`"),
        ("", "\\", "``"),
        ("hello`world", "*", "`hello*`world`"),
    ],
)
def test_wrap_backtick(input_str, escape_ch, expected_output) -> None:
    assert wrap_backtick(input_str, escape_ch) == expected_output


@pytest.mark.parametrize(
    "input_str, pattern, escape_ch, expected_output",
    [
        ("hello.world", r"\.", "\\", "hello\\.world"),
        ("hello^world", r"\^", "\\", "hello\\^world"),
        ("hello$world", r"\$", "\\", "hello\\$world"),
        ("hello-world", r"\-", "*", "hello*-world"),
        ("", r"[\-.^$*+?{}\[\]\\|()]", "\\", ""),
    ],
)
def test_escape_str(input_str, pattern, escape_ch, expected_output) -> None:
    assert escape_str(input_str, pattern, escape_ch) == expected_output
