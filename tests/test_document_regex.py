import pytest
from ssc_codegen import R
from ssc_codegen.ast_ssc import VariableType


def test_fail_compile_regex():
    with pytest.raises(SyntaxError):
        R().re(")")

    with pytest.raises(SyntaxError):
        R().is_regex(")")


@pytest.mark.parametrize(
    "expr", [R().re_all("").index(0), R().re(""), R().re_sub("", "")]
)
def test_assert_expr(expr):
    assert expr.stack_last_ret == VariableType.STRING
