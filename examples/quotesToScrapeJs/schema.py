"""demo example for demonstrate work with json"""
from ssc_codegen import Json, R, ItemSchema


class Author(Json):
    name: str
    goodreads_links: str
    slug: str

class Quote(Json):
    # mark as array entrypoint
    # if object (map/dict) contains in document - do not add it
    __IS_ARRAY__ = True

    tags: list[str]
    author: Author
    text: str

class Main(ItemSchema):
    """http://quotes.toscrape.com/js/ parser

    USAGE:
        GET http://quotes.toscrape.com/js/, http://quotes.toscrape.com/js/page/2/
    """
    # primitive regular expression for extract raw json body
    # its more difficult part - extract and enchant to valid json input
    data = R().re(r'var\s+\w+\s*=\s*(\[[\s\S]*?\]);').jsonify(Quote)
