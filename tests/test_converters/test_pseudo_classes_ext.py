import pytest

from ssc_codegen import D
from ssc_codegen.ast_ import (
    ExprGetHtmlAttr,
    ExprGetHtmlAttrAll,
    ExprGetHtmlText,
    ExprGetHtmlTextAll,
    ExprGetHtmlRaw,
    ExprGetHtmlRawAll,
    ExprIsCss,
    ExprIsXpath,
)
from ssc_codegen.document import BaseDocument
from ssc_codegen.tokens import TokenType


@pytest.mark.parametrize(
    "expr,expected_node",
    [
        (D().css("a::attr(href)"), ExprGetHtmlAttr.kind),
        (D().css_all("a::attr(href)"), ExprGetHtmlAttrAll.kind),
        (D().xpath("//a/@href"), ExprGetHtmlAttr.kind),
        (D().xpath_all("//a/@href"), ExprGetHtmlAttrAll.kind),
        (D().css("a ::text"), ExprGetHtmlText.kind),
        (D().css_all("a ::text"), ExprGetHtmlTextAll.kind),
        (D().xpath("//a/text()"), ExprGetHtmlText.kind),
        (D().xpath_all("//a/text()"), ExprGetHtmlTextAll.kind),
        (D().css("a ::raw"), ExprGetHtmlRaw.kind),
        (D().css_all("a ::raw"), ExprGetHtmlRawAll.kind),
        (D().xpath("//a/raw()"), ExprGetHtmlRaw.kind),
        (D().xpath_all("//a/raw()"), ExprGetHtmlRawAll.kind),
    ],
)
def test_pseudo_classes_expr(
    expr: BaseDocument, expected_node: TokenType
) -> None:
    assert expr.stack[-1].kind == expected_node


@pytest.mark.parametrize(
    "expr,expected_node",
    [
        (D().is_css("a ::text"), ExprIsCss.kind),
        (D().is_css("a ::raw"), ExprIsCss.kind),
        (D().is_css("a ::attr(href)"), ExprIsCss.kind),
        (D().is_xpath("//a/text()"), ExprIsXpath.kind),
        (D().is_xpath("//a/raw()"), ExprIsXpath.kind),
        (D().is_xpath("//a/@href"), ExprIsXpath.kind),
    ],
)
def test_query_assert_expr(
    expr: BaseDocument, expected_node: TokenType
) -> None:
    assert expr.stack[-1].kind == expected_node
