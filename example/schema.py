"""Dummy parser config for http://books.toscrape.com/"""
from typing import Optional, Sequence

from ssc_codegen import Document, ListSchema, ItemSchema, DictSchema, render_code

# DECLARATIVE THIS who need generate
__all__ = ["Book", "BooksCatalogue", "Links"]


class Book(ItemSchema):
    # you can provide docstring - it send to generated class. for example, HOW TO prepare document step-by-step
    # before parse
    # this schema returns value form
    # {<key_name_1>: <value_1>, <key_name_2>: <value_2>, ... <key_name_n>: <value_n>
    """Book object representation

    usage:

        1. GET book page from catalogue eg: http://books.toscrape.com/catalogue/in-her-wake_980/index.html
    """
    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        # Optional pre validate document interface
        # if check not passed - throw AssertError
        doc.css('title').text()
        self.assert_.contains(doc, "Books to Scrape - Sandbox")
        return doc

    # all items for scraping write next form:
    # def <item_name>(_, doc: Document):
    #  ...

    # you can write scrape logic by fluent interface or imperative
    # this example returns struct:
    # {description: ...,
    # title: ...
    # price: ...
    # upc: ...
    # raw_table_values: [...]
    def description(self, doc: Document):
        # optional you can pass docstring
        """product description"""
        # you can pass `#product_description+ p` selector, but
        # selectolax not support this
        return (doc
                .css("#content_inner > article > p")
                .text()
                )

    def title(self, doc: Document):
        # same as a:
        # return doc.css('h1').text()
        d1 = doc.css('h1')
        title_str = d1.text()
        return title_str

    def price(self, doc: Document):
        # doc.default provide try/except, try/catch logic
        # if inner logic failed - return default value
        with doc.default(None):
            return doc.css(".product_main .price_color").text()

    def upc(self, doc: Document):
        return doc.css("tr:nth-child(1) td").text()

    def raw_table_values(self, doc: Document):
        """useless list of values"""
        return doc.css_all("tr > td").text().strip(" ")


class Links(DictSchema):
    # DICT schema converts all value to
    # {key_1: value_1, key_2: value_2, ... key_n: value_n} map
    """dummy link collector from <a> tag"""

    def __split_document_entrypoint__(self, doc: Document) -> Sequence[Document]:
        return doc.css_all('a')

    def key(self, doc: Document) -> Document:
        # set key as TEXT inner <a> tag
        return doc.text().strip(" ")

    def value(self, doc: Document) -> Document:
        # extract 'href' attribute
        return doc.attr('href')


class BooksCatalogue(ListSchema):
    """parse books from http://books.toscrape.com/

    prepare:

        1. GET http://books.toscrape.com/ or http://books.toscrape.com/catalogue/page-<INT>.html
    """

    def __split_document_entrypoint__(self, doc: Document) -> Document:
        # part document to elements for access needed elements
        return doc.css_all(".col-lg-3")

    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        doc.css('title').text()
        self.assert_.contains(doc, "Books to Scrape - Sandbox")
        return doc

    def url(self, doc: Document):
        """page url to product"""
        #  format command provide {{}} syntax for mark where need pass prev value-----------
        #                                                                                   v
        return doc.css('h3 > a').attr('href').format('http://books.toscrape.com/{{}}')

    def title(self, doc: Document):
        return doc.css('h3 > a').attr('title')

    def price(self, doc: Document):
        with doc.default('0'):
            # also have simple enchant value like strip, regex
            #                                      v
            doc.css('.price_color').text().lstrip("£")
        return doc

    def image(self, doc: Document):
        return doc.css('img.thumbnail').attr('src').lstrip('..').format("http://books.toscrape.com{{}}")

    def rating(self, doc: Document):
        return doc.css(".star-rating").attr('class').lstrip('star-rating ')


def generate_code_manual():
    from pathlib import Path
    import subprocess

    from ssc_codegen.converters.py_parsel import converter
    code = render_code(converter, Book(), BooksCatalogue())
    Path("books_to_scrape.py").write_text(code)
    # (recommended) optional call formatter for prettify code style
    subprocess.call(f'black books_to_scrape.py')


if __name__ == '__main__':
    # you can manually generate code or usage CLI interface
    # CLI command works as generate_code_manual function:
    # ssc-gen example.py py.parsel -o books_to_scrape.py
    generate_code_manual()
