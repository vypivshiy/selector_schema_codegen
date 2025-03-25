import pytest

from ssc_codegen import D, R
from ssc_codegen.tokens import VariableType
from ssc_codegen.document import BaseDocument


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
