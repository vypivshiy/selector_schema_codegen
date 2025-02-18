import pytest

from ssc_codegen import D, R
from ssc_codegen.ast_ssc import VariableType
from ssc_codegen.document import BaseDocument


def test_fail_str_format() -> None:
    with pytest.raises(SyntaxError):
        R().fmt("wow")


@pytest.mark.parametrize(
    "expr",
    [
        R().split(" ").index(0),
        R().trim(""),
        R().ltrim(""),
        R().rtrim(""),
        R().repl("", ""),
        R().fmt("{{}}"),
        D()
        .css("#video")
        .attr("data-parameters")
        .repl("\\", "")
        .repl("&quot;", '"'),
    ],
)
def test_string_expr(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.STRING
