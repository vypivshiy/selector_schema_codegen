import pytest

from ssc_codegen import D, R
from ssc_codegen.ast_ssc import VariableType
from ssc_codegen.document import BaseDocument


@pytest.mark.parametrize(
    "expr",
    [
        D().css("a").css_all("b"),
        D().xpath("//a").xpath_all("//b"),
        D().css_all("a"),
        D().xpath_all("//a"),
    ],
)
def test_document_to_list_document(expr: BaseDocument) -> None:
    assert True


@pytest.mark.parametrize(
    "expr",
    [
        D().raw(),
        D().text(),
        R(),
        D().attr("a"),
        D().css_all("a").index(0).text(),
        D().xpath_all("//a").text().index(0),
    ],
)
def test_doc_to_str(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.STRING


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all("a").text(),
        D().xpath_all("//a").text(),
        D().css_all("a").attr("href"),
        D().xpath_all("//a").attr("href"),
    ],
)
def test_doc_to_list_str(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.LIST_STRING
