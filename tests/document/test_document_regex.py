import pytest
from ssc_codegen import R
from ssc_codegen.ast_ssc import VariableType
from ssc_codegen.document import BaseDocument


@pytest.mark.parametrize("pattern", ["(", ""])
def test_fail_compile_regex(pattern: str) -> None:
    with pytest.raises(SyntaxError):
        R().re(pattern)

    with pytest.raises(SyntaxError):
        R().re_all(pattern)

    with pytest.raises(SyntaxError):
        R().re_sub(pattern)

    with pytest.raises(SyntaxError):
        R().is_regex(pattern)


@pytest.mark.parametrize(
    "expr", [R().re_all("0").index(0), R().re("0"), R().re_sub("0", "")]
)
def test_assert_expr(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.STRING
