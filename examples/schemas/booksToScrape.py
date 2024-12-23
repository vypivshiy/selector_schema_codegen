"""Dummy parser config for http://books.toscrape.com/"""

from ssc_codegen import D, N, ItemSchema, ListSchema, FlatListSchema


class Urls(FlatListSchema):
    """fetch add patches and urls from <a> tag"""

    __SPLIT_DOC__ = D().css_all("a")
    __ITEM__ = D().attr("href")


class Books(ListSchema):
    __SPLIT_DOC__ = D().css_all(".col-lg-3")

    name = D().css(".thumbnail").attr("alt")
    image_url = D().css(".thumbnail").attr("src")
    url = D().css(".image_container > a").attr("href")
    rating = D().css(".star-rating").attr("class").ltrim("star-rating ")
    price = D().default(0).css(".price_color").text().re(r"(\d+)").to_int()


class CataloguePage(ItemSchema):
    __PRE_VALIDATE__ = D().css("title").text().is_regex(r"Books to Scrape")

    title = D().css("title").text().re_sub(r'^\s+', '').re_sub(r'\s+$')
    urls = N().sub_parser(Urls)
    books = N().sub_parser(Books)
