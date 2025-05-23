import pytest
from ssc_codegen import D, R
from ssc_codegen.tokens import VariableType
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
        R().re_all("(.*)"),
    ],
)
def test_list_str(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.LIST_STRING


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all("a").text().to_len(),
        D().xpath_all("//a").text().to_len(),
        D().css_all("a").attr("a").to_len(),
        D().xpath_all("//a").attr("a").to_len(),
        D().css_all("a").raw().to_len(),
        D().xpath_all("//a").raw().to_len(),
        R().split(" ").to_len(),
        R().re_all("(.*)").to_len(),
        D().css_all("a").to_len(),
        D().xpath_all("//a").to_len(),
        D().css_all("a").index(0).xpath_all("//a").to_len(),
    ],
)
def test_list_len(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.INT


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all("a").text().to_bool(),
        D().xpath_all("//a").text().to_bool(),
        D().css_all("a").attr("a").to_bool(),
        D().xpath_all("//a").attr("a").to_bool(),
        D().css_all("a").raw().to_bool(),
        D().xpath_all("//a").raw().to_bool(),
        R().split(" ").to_bool(),
        R().re_all("(.*)").to_bool(),
        D().css_all("a").to_bool(),
        D().xpath_all("//a").to_bool(),
        D().css_all("a").index(0).xpath_all("//a").to_bool(),
        D(True).css_all("a").to_bool(),
        D(False).css_all("a").to_bool(),
    ],
)
def test_list_to_bool(expr: BaseDocument) -> None:
    assert expr.stack_last_ret == VariableType.BOOL
