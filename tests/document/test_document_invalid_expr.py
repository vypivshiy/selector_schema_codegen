from typing import Callable

import pytest

from ssc_codegen import D, Document, ItemSchema, N, R


class MockParser(ItemSchema):
    pass


@pytest.mark.parametrize(
    "document",
    [
        # NOTE: lambda wrapper needed for avoid throw error in python compile bytecode stage
        lambda: R().css("a"),
        lambda: R().xpath("//a"),
        lambda: R().css_all("a"),
        lambda: R().xpath_all("//a"),
        lambda: N().sub_parser(MockParser).css("a"),
        lambda: N().sub_parser(MockParser).sub_parser(MockParser),
        lambda: D().trim(""),
        lambda: D().index(0),
        lambda: D().is_regex(""),
        lambda: D().css("a").default(None),
        lambda: D().is_equal(""),
        lambda: D().is_not_equal(""),
        lambda: D().is_contains(""),
        lambda: R().is_css("title"),
        lambda: R().is_xpath("//title"),
        lambda: R().split(" ").is_contains(1),
        lambda: R().split(" ").is_contains(0.1),
        lambda: R().split(" ").to_int().is_contains(0.1),
        lambda: R().split(" ").to_int().is_contains("a"),
        lambda: R().split(" ").to_float().is_contains(1),
        lambda: R().split(" ").to_float().is_contains("a"),
        lambda: R().is_equal(1),
        lambda: R().is_equal(0.1),
        lambda: R().to_int().is_equal(0.1),
        lambda: R().to_int().is_equal("a"),
        lambda: R().to_float().is_equal(1),
        lambda: R().to_float().is_equal("a"),
    ],
)
def test_invalid_expr(document: Callable[[], Document]) -> None:
    with pytest.raises(SyntaxError):
        document()
