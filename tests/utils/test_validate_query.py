import pytest
from cssselect import SelectorSyntaxError

from ssc_codegen.selector_utils import (
    validate_css_query,
    validate_xpath_query,
)


@pytest.mark.parametrize("q", ["//title", "111", "body > nth-child(1)"])
def test_fail_validate_css_query(q: str) -> None:
    with pytest.raises(SelectorSyntaxError):
        validate_css_query(q)


@pytest.mark.parametrize("q", ["head > title", "!111"])
def test_fail_validate_xpath_query(q: str) -> None:
    with pytest.raises(SelectorSyntaxError):
        validate_xpath_query(q)


@pytest.mark.parametrize(
    "q",
    [
        "title",
        "head > title",
        # note: several backend css parser may be not fully support css2 specs
        "body > div:nth-child(1)",
    ],
)
def test_validate_css_query(q: str) -> None:
    validate_css_query(q)


@pytest.mark.parametrize(
    "q",
    ["//head/title", "descendant-or-self::body/div"],
)
def test_validate_xpath_query(q: str) -> None:
    validate_xpath_query("//head/title")
