from ssc_codegen2.document.selector import DocumentOpHtml, DocumentOpHtmlSingle
from ssc_codegen2.document.regex import DocumentOpRegex
from ssc_codegen2.document.array import DocumentOpArray
from ssc_codegen2.document.text import DocumentOpString
from ssc_codegen2.document.nested import DocumentOpNested
from ssc_codegen2.document.validate import DocumentOpAssert


__all__ = ["Document", "D", "Nested", "N"]


class Document(
    DocumentOpHtml, DocumentOpArray, DocumentOpString, DocumentOpRegex, DocumentOpAssert
):
    pass


class Nested(DocumentOpNested, DocumentOpHtmlSingle, ):
    pass


def D() -> Document:
    """Document object shortcut"""
    return Document()


def N() -> Nested:
    """Nested document shortcut"""
    return Nested()


if __name__ == "__main__":
    d = D().css_all("a").text().replace("a", "b").first().assert_re(r'\w+', 'not word')
    print(d)