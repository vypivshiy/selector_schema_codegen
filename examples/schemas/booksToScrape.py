"""Dummy parser config for http://books.toscrape.com/"""

from ssc_codegen import D, N, ItemSchema, ListSchema, FlatListSchema, DictSchema


class Urls(FlatListSchema):
    # parse to simple List or Array
    """fetch add patches and urls from <a> tag"""
    __SPLIT_DOC__ = D().css_all("a")

    # declare list element
    __ITEM__ = D().attr("href")

class UrlsMap(DictSchema):
    # parse to Map/Dict
    __SPLIT_DOC__ = D().css_all("a")

    # declare map key (should be a String)
    __KEY__ = D().attr("href")

    # declare value
    __VALUE__ = D().raw().trim(" ")


class Books(ListSchema):
    # parse to structured collections with declarated fields

    # this magic field parts document to elements for parse fields
    # used for part elements where query selector is simular (e.g. product cards)
    __SPLIT_DOC__ = D().css_all(".col-lg-3")

    name = D().css(".thumbnail").attr("alt")
    image_url = D().css(".thumbnail").attr("src").fmt("https://{{}}")
    url = D().css(".image_container > a").attr("href")
    rating = D().css(".star-rating").attr("class").ltrim("star-rating ")
    # set default variable, if next block code throw exception (should be a first)
    price = D().default(0).css(".price_color").text().re(r"(\d+)").to_int()


class CataloguePage(ItemSchema):
    # docstrings automatically be ported to generated code.
    # recommended to describe the instructions and (if exists) what errors may occur.
    # Optionally add usage examples
    """books.toscrape.com catalogue page entrypoint parser

    USAGE:

        1. GET <catalog page> (https://books.toscrape.com/, https://books.toscrape.com/catalogue/page-2.html, ...)
        2. add another prepare instruction how to correct cook page (if needed?)

    ISSUES:

        1. nope! Their love being scraped!
    """

    # optional pre-validation document before parse document
    # does not modify document argument
    # if checks not passed - throw exception
    __PRE_VALIDATE__ = D().css("title").text().is_regex(r"Books to Scrape")

    title = D().default("test").is_css("title").css("title").text().re_sub(r'^\s+', '').re_sub(r'\s+$')
    # N() - Nested, send document object to another parser
    urls = N().sub_parser(Urls)
    urls_map = N().sub_parser(UrlsMap)
    books = N().sub_parser(Books)
