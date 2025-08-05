import pytest

from ssc_codegen.str_utils import (
    py_str_format_to_fstring,
)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("", ""),
        ('value = "{}".format(value1)', 'value = f"{value1}"'),
        ('value = "{}".format(value1) or None', 'value = f"{value1}" or None'),
    ],
)
def test_py_str_fmt_to_fstring(code: str, expected: str) -> None:
    out = py_str_format_to_fstring(code)
    assert out == expected
