import pytest

from ssc_codegen.selector_utils import (
    css_to_xpath,
    xpath_to_css,
)


@pytest.mark.parametrize(
    "q,out", [("title", "//title"), ("head > title", "//head/title")]
)
def test_convert_css_to_xpath(q: str, out: str) -> None:
    assert css_to_xpath(q, prefix="//") == out


@pytest.mark.parametrize(
    "q,out", [("//title", "title"), ("//head/title", "head > title")]
)
def test_convert_xpath_to_css(q: str, out: str) -> None:
    assert xpath_to_css(q) == out
