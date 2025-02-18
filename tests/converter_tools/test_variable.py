from ssc_codegen.ast_ssc import Variable
from ssc_codegen.converters.base import left_right_var_names
from ssc_codegen.tokens import VariableType
import pytest


@pytest.mark.parametrize(
    "name, variable, expected_prev, expected_next",
    [
        # Basic cases
        (
            "var",
            Variable(num=0, count=1, type=VariableType.STRING),
            "var",
            "var1",
        ),
        (
            "var",
            Variable(num=1, count=2, type=VariableType.INT),
            "var1",
            "var2",
        ),
        (
            "var",
            Variable(num=2, count=3, type=VariableType.FLOAT),
            "var2",
            "var3",
        ),
        # Different base name
        (
            "different",
            Variable(num=2, count=3, type=VariableType.LIST_STRING),
            "different2",
            "different3",
        ),
        # Corner cases
        # Empty name
        ("", Variable(num=0, count=1, type=VariableType.STRING), "", "1"),
        ("", Variable(num=1, count=2, type=VariableType.INT), "1", "2"),
        # Large numbers
        (
            "var",
            Variable(num=100, count=101, type=VariableType.FLOAT),
            "var100",
            "var101",
        ),
        # Special characters in name
        (
            "var@",
            Variable(num=0, count=1, type=VariableType.STRING),
            "var@",
            "var@1",
        ),
        (
            "var@",
            Variable(num=1, count=2, type=VariableType.INT),
            "var@1",
            "var@2",
        ),
        # Single-character name
        ("x", Variable(num=0, count=1, type=VariableType.STRING), "x", "x1"),
        ("x", Variable(num=1, count=2, type=VariableType.INT), "x1", "x2"),
    ],
)
def test_left_right_var_names(
    name, variable, expected_prev, expected_next
) -> None:
    prev, next_ = left_right_var_names(name, variable)
    assert prev == expected_prev
    assert next_ == expected_next
