"""Dummy parser config for http://books.toscrape.com/"""

from ssc_codegen.document import D, N
from ssc_codegen.schema import (
    ItemSchema,
    ListSchema,
    FlattenListSchema,
)


class Urls(FlattenListSchema):
    """fetch add patches and urls from <a> tag"""

    __SPLIT_DOC__ = D().css_all("a")
    __ITEM__ = D()["href"]


class Books(ListSchema):
    __SPLIT_DOC__ = D().css_all(".col-lg-3")

    name = D().css(".thumbnail")["alt"]
    image_url = D().css(".thumbnail")["src"]
    url = D().css(".image_container > a")["href"]
    rating = D().css(".star-rating")["class"].ltrim("star-rating ")
    price = D().default("0").css(".price_color").text().re(r"\d+")


class CataloguePage(ItemSchema):
    __PRE_VALIDATE__ = D().css("title").text().assert_re(r"Books to Scrape")

    title = D().css("title").text()
    urls: Urls = N().sub_parser(Urls)
    books: Books = N().sub_parser(Books)
