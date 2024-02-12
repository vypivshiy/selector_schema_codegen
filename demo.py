import os
from typing import Optional, Sequence

from ssc_codegen.template import render_code
from ssc_codegen.structs import ItemStruct, DictStruct, ListStruct
from ssc_codegen.document import Document
from ssc_codegen.generator import StructParser


class DemoItem(ItemStruct):
    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        return self.assert_.css(doc, "title")

    def name(self, doc: Document):
        return doc.css('title').text()

    def urls(self, doc: Document):
        return doc.css_all('div > a').attr('href')


class DemoDict(DictStruct):

    def __split_document_entrypoint__(self, doc: Document) -> Sequence[Document]:
        return doc.css_all('div')

    def key(self, doc: Document) -> Document:
        return doc.text()

    def value(self, doc: Document) -> Document:
        return doc.attr('href')


class DemoList(ListStruct):

    def __split_document_entrypoint__(self, doc: Document) -> Document:
        return doc.css_all('div')

    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        return self.assert_.css(doc, 'title')

    def url(self, doc: Document):
        return doc.css('a').attr('href')

    def name(self, doc: Document):
        """docstring
        test


        1

        2

        3"""
        return doc.css('a').text()


if __name__ == '__main__':
    # from ssc_codegen.converters.py_parsel import converter
    # from ssc_codegen.converters.py_selectolax import converter
    from ssc_codegen.converters.dart_universal_html import converter
    code = render_code(converter, DemoItem(), DemoDict(), DemoList())
    with open("ex_parser.dart", 'w') as f:
        f.write(code)
    os.system('dart format ex_parser.dart')


