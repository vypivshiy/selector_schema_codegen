import pytest

from ssc_codegen import D, Document, ItemSchema, R, N
from ssc_codegen.schema import BaseSchema
from ssc_codegen.static_checker import _DEFAULT_CB_DOCUMENTS  # noqa


class MockParser(ItemSchema):
    pass


@pytest.mark.parametrize(
    "document",
    [
        R().css("a"),
        R().xpath("//a"),
        R().css_all("a"),
        R().xpath_all("//a"),
        N().sub_parser(MockParser).css("a"),
        N().sub_parser(MockParser).sub_parser(MockParser),
        D().trim(""),
        D().index(0),
        D().css("a").default(None),
        D().is_equal(""),
        D().is_not_equal(""),
        D().is_contains(""),
        R().is_css("title"),
        R().is_xpath("//title"),
        R().split(" ").is_contains(1),
        R().split(" ").is_contains(0.1),
        R().split(" ").to_int().is_contains(0.1),
        R().split(" ").to_int().is_contains("a"),
        R().split(" ").to_float().is_contains(1),
        R().split(" ").to_float().is_contains("a"),
        R().is_equal(1),
        R().is_equal(0.1),
        R().to_int().is_equal(0.1),
        R().to_int().is_equal("a"),
        R().to_float().is_equal(1),
        R().to_float().is_equal("a"),
        R().to_len(),
        D().to_len(),
        D().css("a").to_len(),
        D().xpath("//a").to_len(),
        # REGEX
        R().re(""),
        R().re("abc"),
        R().re("("),
        R().re("(.*)(.*)"),
        R().re("(.*)(?:.*)(.*)"),
        R().re_all(""),
        R().re_all("("),
        R().re_all("(.*)(.*)"),
        R().re_all("(.*)(?:.*)(.*)"),
        R().re_sub("("),
        R().is_regex(""),
        R().is_regex("("),
    ],
)
def test_invalid_expr(document: Document) -> None:
    result = all(cb(BaseSchema, "_", document) for cb in _DEFAULT_CB_DOCUMENTS)
    assert not result, f"is valid: {document!r} {document.stack!r}"
