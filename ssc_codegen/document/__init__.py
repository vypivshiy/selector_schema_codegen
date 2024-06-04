from ssc_codegen.document.array import DocumentOpArray
from ssc_codegen.document.nested import DocumentOpNested
from ssc_codegen.document.regex import DocumentOpRegex
from ssc_codegen.document.selector import (
    DocumentOpHtml,
    DocumentOpHtmlSingle,
    DocumentOpSelectorConverter,
)
from ssc_codegen.document.text import DocumentOpString
from ssc_codegen.document.validate import DocumentOpAssert

__all__ = ["Document", "D", "Nested", "N", "R"]


class Document(
    DocumentOpHtml,
    DocumentOpArray,
    DocumentOpString,
    DocumentOpRegex,
    DocumentOpAssert,
):
    pass


class Nested(
    DocumentOpNested, DocumentOpHtmlSingle, DocumentOpSelectorConverter
):
    pass


def D() -> Document:
    """Document object shortcut"""
    return Document()


def N() -> Nested:
    """Nested document object shortcut"""
    return Nested()


def R() -> Document:
    """D().raw() object shortcut alias. Useful for string/regex operations"""
    return D().raw()


if __name__ == "__main__":
    d = (
        D()
        .css_all("a")
        .text()
        .replace("a", "b")
        .first()
        .assert_re(r"\w+", "not word")
    )
    print(d)
