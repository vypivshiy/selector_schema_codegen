from ssc_codegen.structs import ItemStruct
from ssc_codegen.document import Document
from validate import assert_


class Validate:
    @classmethod
    def __call__(cls, *args, **kwargs):
        def wrapper():
            pass
        return wrapper


class Book(ItemStruct):
    """parse books from books.to_scrape/catalogue page"""

    def _(_, doc: Document):
        assert_.css(doc, "head > title")
        doc.css("title")
        assert_.re(doc, r"Books to Scrape - Sandbox")
        return doc

    def title(_, doc: Document):
        """product name"""
        return doc.css("h1").text()

    def price(_, doc: Document):
        """product price"""
        with doc.default('0'):
            return doc.css('.product_main .price_color').text()


    def upc(_, doc: Document):
        doc.css("tr:nth-child(1) td")
        doc.text()
        return doc

    def description(_, doc: Document):
        """product description"""
        return (doc
                .css('#product_description+ p')
                .text()
                )


if __name__ == '__main__':
    with Document().default("1") as d:
        d.text()
    assert_.equal(d, "okay")
    print(d._stack)