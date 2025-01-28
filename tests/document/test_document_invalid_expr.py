import pytest
from ssc_codegen import D, N, R, ItemSchema


class MockParser(ItemSchema):
    pass


def test_raw_invalid_expr() -> None:
    with pytest.raises(SyntaxError):
        R().css("a")

    with pytest.raises(SyntaxError):
        R().xpath("a")

    with pytest.raises(SyntaxError):
        R().xpath_all("a")

    with pytest.raises(SyntaxError):
        R().css_all("a")


def test_nested_invalid_expr() -> None:
    with pytest.raises(SyntaxError):
        N().sub_parser(MockParser).css("a")

    with pytest.raises(SyntaxError):
        N().sub_parser(MockParser).sub_parser(MockParser)


def test_invalid_doc_expr() -> None:
    with pytest.raises(SyntaxError):
        D().trim("")

    with pytest.raises(SyntaxError):
        D().index(0)

    with pytest.raises(SyntaxError):
        D().is_regex("")

    with pytest.raises(SyntaxError):
        D().css("a").default(None)

    with pytest.raises(SyntaxError):
        D().is_equal("")

    with pytest.raises(SyntaxError):
        D().is_not_equal("")

    with pytest.raises(SyntaxError):
        D().is_contains("")

    with pytest.raises(SyntaxError):
        R().is_css("title")

    with pytest.raises(SyntaxError):
        R().is_xpath("//title")

