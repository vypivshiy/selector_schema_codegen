# examples/tutorial/booksToScrape/schema3.py
from ssc_codegen import ItemSchema, D, ListSchema, N

FMT_URL = "https://books.toscrape.com/catalogue/{{}}"
FMT_URL_CURRENT = "https://books.toscrape.com/catalogue/page-{{}}.html"
FMT_THUMBNAIL_BOOK = "https://books.toscrape.com{{}}"

class Book(ListSchema):
    __SPLIT_DOC__ = D().css_all(".col-lg-3")

    name = D().css(".thumbnail").attr("alt")
    image_url = D().css(".thumbnail").attr("src").ltrim('..').fmt(FMT_THUMBNAIL_BOOK)
    url = D().css(".image_container > a").attr("href").fmt(FMT_URL)
    rating = D().css(".star-rating").attr("class").ltrim("star-rating ")
    # convert price to integer
    price = D().default(0).css(".price_color").text().re(r"(\d+)").to_int()


class MainCatalogue(ItemSchema):
    # docstring is optional feature
    # converter translate to output code
    # it will later make life easier to use!
    """parse main catalogue page

    Response input examples:
        - https://books.toscrape.com/
        - https://books.toscrape.com/catalogue/page-2.html

    """
    books = N().sub_parser(Book)

    prev_page = D().default(None).css('.previous a').attr('href').ltrim('catalogue/').fmt(FMT_URL)
    next_page = D().default(None).css('.next a').attr('href').ltrim('catalogue/').fmt(FMT_URL)
    curr_page = D().css('.current').text().re(r'Page\s(\d+)').fmt(FMT_URL_CURRENT)