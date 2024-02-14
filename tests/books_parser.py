"""example test books.toscrape selector schemas"""
from typing import Optional

from ssc_codegen.document import Document
from ssc_codegen.schemas import ListSchema, ItemSchema
from ssc_codegen.template import render_code

__all__ = ["Book", "BooksCatalogue"]


class BooksCatalogue(ListSchema):
    """parse books from catalogue"""

    def __split_document_entrypoint__(self, doc: Document) -> Document:
        return doc.css_all(".col-lg-3")

    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        doc.css('title').text()
        self.assert_.contains(doc, "Books to Scrape - Sandbox")
        return doc

    def url(self, doc: Document):
        """page url to product"""
        return doc.css('h3 > a').attr('href').format('https://books.toscrape.com/catalogue/{{}}')

    def title(self, doc: Document):
        return doc.css('h3 > a').attr('title')

    def price(self, doc: Document):
        with doc.default('0'):
            doc.css('.price_color').text().lstrip("£")
        return doc

    def image(self, doc: Document):
        return doc.css('img.thumbnail').attr('src').lstrip('..').format("https://books.toscrape.com{{}}")

    def rating(self, doc: Document):
        return doc.css(".star-rating").attr('class').lstrip('star-rating ')


class Book(ItemSchema):
    """sample docstring

    test 123

    - okay
    """
    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        doc.css('title').text()
        self.assert_.contains(doc, "Books to Scrape - Sandbox")
        return doc

    def description(self, doc: Document):
        """product description"""
        # selectolax not support `+` operator
        # old selector: #product_description+ p
        return doc.css("#content_inner > article > p").text()

    def title(self, doc: Document):
        return doc.css('h1').text()

    def price(self, doc: Document):
        with doc.default("0"):
            return doc.css(".product_main .price_color").text()

    def upc(self, doc: Document):
        """upc

        lorem upsum dolor"""
        return doc.css("tr:nth-child(1) td").text()

    def raw_table_values(self, doc: Document):
        """useless list of values"""
        return doc.css_all("tr > td").text().strip(" ")
