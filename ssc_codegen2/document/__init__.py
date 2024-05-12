from ssc_codegen2.document.selector import DocumentOpHtml
from ssc_codegen2.document.regex import DocumentOpRegex
from ssc_codegen2.document.array import DocumentOpArray
from ssc_codegen2.document.text import DocumentOpString

__all__ = ['Document', 'D']


class Document(DocumentOpHtml,
               DocumentOpArray,
               DocumentOpString,
               DocumentOpRegex):
    pass


def D() -> Document:
    """Document object shortcut"""
    return Document()


if __name__ == '__main__':
    d = D().css_all('a').text().replace('a', 'b')
    print(d)
