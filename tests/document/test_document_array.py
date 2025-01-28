import pytest
from ssc_codegen import D, R
from ssc_codegen.ast_ssc import VariableType
from ssc_codegen.document import BaseDocument


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all("a"),
        D().xpath_all("//a"),
        D().css_all("a").index(0).xpath_all("//a"),
    ],
)
def test_list_document(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.LIST_DOCUMENT


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all("a").text(),
        D().xpath_all("//a").text(),
        D().css_all("a").attr("a"),
        D().xpath_all("//a").attr("a"),
        D().css_all("a").raw(),
        D().xpath_all("//a").raw(),
        R().split(" "),
        R().re_all(".*"),
    ],
)
def test_list_str(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.LIST_STRING
