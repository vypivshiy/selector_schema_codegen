import pytest

from ssc_codegen import parse_ast
from ssc_codegen.selector_utils import css_to_xpath
from ssc_codegen.ast import (
    Struct,
    Field,
    Filter,
    CssSelect,
    CssSelectAll,
    CssRemove,
    PredCss,
    XpathSelect,
    XpathSelectAll,
    XpathRemove,
    PredXpath,
)


@pytest.mark.parametrize(
    "q,out", [("title", "//title"), ("head > title", "//head/title")]
)
def test_convert_css_to_xpath(q: str, out: str) -> None:
    assert css_to_xpath(q, prefix="//") == out


def _get_struct(module, name: str) -> Struct:
    for node in module.body:
        if isinstance(node, Struct) and node.name == name:
            return node
    raise AssertionError(f"Struct {name!r} not found")


def _get_field(struct: Struct, name: str) -> Field:
    for node in struct.body:
        if isinstance(node, Field) and node.name == name:
            return node
    raise AssertionError(f"Field {name!r} not found")


def test_css_to_xpath_ast_conversion() -> None:
    src = """
    struct Sample {
        title {
            css "title"
        }

        titles {
            css-all "title"
        }

        remove-ad {
            css-remove ".ad"
        }

        filtered-links {
            css-all "a"
            filter {
                css ".icon"
            }
        }
    }
    """
    module = parse_ast(src=src, css_to_xpath=True)
    struct = _get_struct(module, "Sample")

    title = _get_field(struct, "title")
    assert any(isinstance(node, XpathSelect) for node in title.body)
    assert not any(isinstance(node, CssSelect) for node in title.body)

    titles = _get_field(struct, "titles")
    assert any(isinstance(node, XpathSelectAll) for node in titles.body)
    assert not any(isinstance(node, CssSelectAll) for node in titles.body)

    remove_ad = _get_field(struct, "remove-ad")
    assert any(isinstance(node, XpathRemove) for node in remove_ad.body)
    assert not any(isinstance(node, CssRemove) for node in remove_ad.body)

    filtered_links = _get_field(struct, "filtered-links")
    filter_node = next(
        node for node in filtered_links.body if isinstance(node, Filter)
    )
    assert any(isinstance(node, PredXpath) for node in filter_node.body)
    assert not any(isinstance(node, PredCss) for node in filter_node.body)
