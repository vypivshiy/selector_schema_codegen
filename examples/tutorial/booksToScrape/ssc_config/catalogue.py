from ssc_codegen import ItemSchema, D, ListSchema, N
import re

FMT_URL = "https://books.toscrape.com/catalogue/{{}}"
FMT_BASE = "https://books.toscrape.com/{{}}"
FMT_URL_CURRENT = "https://books.toscrape.com/catalogue/page-{{}}.html"

# recommended define regexp by re.compile() for extra check syntax
RE_BOOK_PRICE = re.compile(r"(\d+(?:.\d+)?)")


class Book(ListSchema):
    """Exctract a book cards

    Usage:

        - GET https://books.toscrape.com/
        - GET https://books.toscrape.com/catalogue/page-2.html
        - GET https://books.toscrape.com/catalogue/page-50.html
    """

    # should be returns collection of elements
    __SPLIT_DOC__ = D().css_all(".col-lg-3")
    # Optional pre validate method
    __PRE_VALIDATE__ = D().is_css(".col-lg-3 .thumbnail")

    name = D().css(".thumbnail::attr(alt)")
    # fix urls:
    # if response from books.toscrape.com - cards contains /catalogue prefix
    # if response from books.toscrape.com/catalogue - cards exclude this prefix
    image_url = (
        D().css(".thumbnail::attr(src)").rm_prefix("..").ltrim('/').fmt(FMT_BASE)
    )
    url = D().css(".image_container > a::attr(href)").ltrim('/').rm_prefix("catalogue/").fmt(FMT_URL)
    rating = (
        D(0)
        .css(".star-rating::attr(class)")
        .rm_prefix("star-rating ")
        # translate literal rating to integer
        .repl_map(
            {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}
        )
        .to_int()
    )
    # NEW pseudo selector ::text - same as call `.text()` method
    price = (
        D()
        # define float explicitly
        .default(0.0)
        .css(".price_color::text")
        .re(RE_BOOK_PRICE)
        .to_float()
    )

class MainCatalogue(ItemSchema):
    """Extract pagination urls and book cards

    Usage Examples:

        - GET https://books.toscrape.com/
        - GET https://books.toscrape.com/catalogue/page-2.html
        - GET https://books.toscrape.com/catalogue/page-50.html

    Issues:
        - on the first page, prev_page = None
        - on the last page, next_page = None
    """

    books = N().sub_parser(Book)

    prev_page = (
        D()
        .default(None)
        .css(".previous a")
        .attr("href")
        .rm_prefix("catalogue/")
        .fmt(FMT_URL)
    )
    next_page = (
        D()
        .default(None)
        .css(".next a")
        .attr("href")
        .rm_prefix("catalogue/")
        .fmt(FMT_URL)
    )
    curr_page = (
        D().css(".current").text().re(r"Page\s(\d+)").fmt(FMT_URL_CURRENT)
    )
