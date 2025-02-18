import pytest

from ssc_codegen import D, Document
from ssc_codegen.document import BaseDocument
from ssc_codegen.document_utlis import (
    convert_css_to_xpath,
    convert_xpath_to_css,
)
from ssc_codegen.tokens import TokenType


def extract_all_queries(d: BaseDocument) -> set[str]:
    # HACK: usage magic method instead check TokenTypes
    return set(
        i.query
        for i in d.stack
        if i.kind
        in (
            TokenType.EXPR_CSS,
            TokenType.EXPR_CSS_ALL,
            TokenType.EXPR_XPATH,
            TokenType.EXPR_XPATH_ALL,
            TokenType.IS_CSS,
            TokenType.IS_XPATH,
        )
    )


def extract_all_tokens(d: BaseDocument) -> list[TokenType]:
    return [i.kind for i in d.stack]


# NOTE: hardcoded XPATH prefix //
@pytest.mark.parametrize(
    "doc,queries_expected",
    [
        (D().css("a"), {"//a"}),
        (D().css_all("a"), {"//a"}),
        (D().css("div").css("p > a"), {"//div", "//p/a"}),
        (D().is_css("a"), {"//a"}),
        (
            D().css("div.foo"),
            {
                "//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' foo ')]"
            },
        ),
        (
            D().css(".foo"),
            {
                "//*[@class and contains(concat(' ', normalize-space(@class), ' '), ' foo ')]"
            },
        ),
        (
            D().css("#foo"),
            {"//*[@id = 'foo']"},
        ),
    ],
)
def test_convert_css_to_xpath_queries(
    doc: Document, queries_expected: set[str]
) -> None:
    d_converted = convert_css_to_xpath(doc, prefix="//")
    queries = extract_all_queries(d_converted)
    assert queries == queries_expected


@pytest.mark.parametrize(
    "doc,tokens_expected",
    [
        (D().css("a"), [TokenType.EXPR_XPATH]),
        (D().css_all("a"), [TokenType.EXPR_XPATH_ALL]),
        (D().is_css("a"), [TokenType.IS_XPATH]),
        (D().css("a").is_css("b"), [TokenType.EXPR_XPATH, TokenType.IS_XPATH]),
        (
            D().css("a").css_all("b").first().is_css("c"),
            [
                TokenType.EXPR_XPATH,
                TokenType.EXPR_XPATH_ALL,
                TokenType.EXPR_LIST_DOCUMENT_INDEX,
                TokenType.IS_XPATH,
            ],
        ),
    ],
)
def test_convert_css_to_xpath_tokens(
    doc: Document, tokens_expected: list[TokenType]
) -> None:
    d_converted = convert_css_to_xpath(doc, prefix="//")
    d_tokens = extract_all_tokens(d_converted)
    assert d_tokens == tokens_expected


@pytest.mark.parametrize(
    "doc,queries_expected",
    [
        (D().xpath("//a"), {"a"}),
        (D().xpath("//a/b"), {"a > b"}),
        (D().xpath_all("//a/b/c"), {"a > b > c"}),
        (D().is_xpath("//a/b/c"), {"a > b > c"}),
    ],
)
def test_convert_xpath_to_css_queries(
    doc: Document, queries_expected: set[str]
) -> None:
    d_converted = convert_xpath_to_css(doc)
    queries = extract_all_queries(d_converted)
    assert queries == queries_expected


@pytest.mark.parametrize(
    "doc,tokens_expected",
    [
        (D().xpath("//a"), [TokenType.EXPR_CSS]),
        (D().xpath_all("//a"), [TokenType.EXPR_CSS_ALL]),
        (D().is_xpath("//a"), [TokenType.IS_CSS]),
        (
            D().xpath("//a").is_xpath("//b"),
            [TokenType.EXPR_CSS, TokenType.IS_CSS],
        ),
        (
            D().xpath("//a").xpath_all("//b").first().is_xpath("//c"),
            [
                TokenType.EXPR_CSS,
                TokenType.EXPR_CSS_ALL,
                TokenType.EXPR_LIST_DOCUMENT_INDEX,
                TokenType.IS_CSS,
            ],
        ),
    ],
)
def test_convert_xpath_to_css_tokens(
    doc: Document, tokens_expected: list[TokenType]
) -> None:
    d_converted = convert_xpath_to_css(doc)
    d_tokens = extract_all_tokens(d_converted)
    assert d_tokens == tokens_expected
