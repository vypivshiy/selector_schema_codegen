# Auto generated code by ssc_gen
# WARNING: Any manual changes made to this file will be lost when this
# is run again. Do not edit this file unless you know what you are doing.

from __future__ import annotations  # python 3.7, 3.8 comp
import re
from typing import Any, Union

from parsel import Selector, SelectorList

_T_DICT_ITEM = dict[str, Union[str, list[str]]]
_T_LIST_ITEMS = list[dict[str, Union[str, list[str]]]]


class _BaseStructParser:
    def __init__(self, document: str):
        self.__raw__ = document
        self.__selector__ = Selector(document)
        self._cached_result: Union[_T_DICT_ITEM, _T_LIST_ITEMS] = {}

    def _pre_validate(self, document: Selector) -> None:
        # pre validate entrypoint, contain assert expressions
        pass

    def parse(self):
        """run parser"""
        self._pre_validate(self.__selector__)
        self._start_parse()
        return self

    def view(self) -> Union[_T_DICT_ITEM, _T_LIST_ITEMS]:
        """get parsed values"""
        return self._cached_result

    def _start_parse(self):
        """parse logic entrypoint"""
        pass


class Book(_BaseStructParser):
    """Book object representation

        usage:

            1. GET book page from catalogue eg: http://books.toscrape.com/catalogue/in-her-wake_980/index.html

        Book view() item signature:

    {
        "description": "String",
        "title": "String",
        "price": "String",
        "upc": "String",
        "raw_table_values": "Array['String']"
    }
    """

    def __init__(self, document: str):
        super().__init__(document)
        self._cached_result: _T_DICT_ITEM = {}

    def _pre_validate(self, doc: Selector) -> None:
        var_0 = doc
        var_1 = var_0.css("title")
        var_2 = var_1.css("::text").get()
        assert "Books to Scrape - Sandbox" in var_2
        return

    def _start_parse(self):
        self._cached_result.clear()
        self._cached_result["description"] = self._parse_description(
            self.__selector__
        )
        self._cached_result["title"] = self._parse_title(self.__selector__)
        self._cached_result["price"] = self._parse_price(self.__selector__)
        self._cached_result["upc"] = self._parse_upc(self.__selector__)
        self._cached_result["raw_table_values"] = self._parse_raw_table_values(
            self.__selector__
        )

    def view(self) -> _T_DICT_ITEM:
        return self._cached_result

    def _parse_description(self, doc: Selector):
        """product description"""

        var_0 = doc
        var_1 = var_0.css("#content_inner > article > p")
        var_2 = var_1.css("::text").get()
        return var_2

    def _parse_title(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css("h1")
        var_2 = var_1.css("::text").get()
        return var_2

    def _parse_price(self, doc: Selector):
        var_0 = doc
        try:
            var_2 = var_0.css(".product_main .price_color")
            var_3 = var_2.css("::text").get()
            return var_3
        except Exception as e:
            return None

    def _parse_upc(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css("tr:nth-child(1) td")
        var_2 = var_1.css("::text").get()
        return var_2

    def _parse_raw_table_values(self, doc: Selector):
        """useless list of values"""

        var_0 = doc
        var_1 = var_0.css("tr > td")
        var_2 = var_1.css("::text").getall()
        var_3 = [s.strip(" ") for s in var_2]
        return var_3


class BooksCatalogue(_BaseStructParser):
    """parse books from http://books.toscrape.com/

        prepare:

            1. GET http://books.toscrape.com/ or http://books.toscrape.com/catalogue/page-<INT>.html

        BooksCatalogue view() item signature:

    {
        "url": "String",
        "title": "String",
        "price": "String",
        "image": "String",
        "rating": "String"
    }
    """

    def __init__(self, document: str):
        super().__init__(document)
        self._cached_result: _T_LIST_ITEMS = []

    def _pre_validate(self, doc: Selector) -> None:
        var_0 = doc
        var_1 = var_0.css("title")
        var_2 = var_1.css("::text").get()
        assert "Books to Scrape - Sandbox" in var_2
        return

    def _part_document(self) -> SelectorList:
        doc = self.__selector__
        var_0 = doc
        var_1 = var_0.css(".col-lg-3")
        return var_1

    def _start_parse(self):
        self._cached_result.clear()
        for part in self._part_document():
            self._cached_result.append(
                {
                    "url": self._parse_url(part),
                    "title": self._parse_title(part),
                    "price": self._parse_price(part),
                    "image": self._parse_image(part),
                    "rating": self._parse_rating(part),
                }
            )

    def view(self) -> _T_LIST_ITEMS:
        return self._cached_result

    def _parse_url(self, doc: Selector):
        """page url to product"""

        var_0 = doc
        var_1 = var_0.css("h3 > a")
        var_2 = var_1.attrib["href"]
        var_3 = "http://books.toscrape.com/{}".format(var_2)
        return var_3

    def _parse_title(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css("h3 > a")
        var_2 = var_1.attrib["title"]
        return var_2

    def _parse_price(self, doc: Selector):
        var_0 = doc
        try:
            var_2 = var_0.css(".price_color")
            var_3 = var_2.css("::text").get()
            var_4 = var_3.lstrip("£")
            return var_4
        except Exception as e:
            return "0"

    def _parse_image(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css("img.thumbnail")
        var_2 = var_1.attrib["src"]
        var_3 = var_2.lstrip("..")
        var_4 = "http://books.toscrape.com{}".format(var_3)
        return var_4

    def _parse_rating(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css(".star-rating")
        var_2 = var_1.attrib["class"]
        var_3 = var_2.lstrip("star-rating ")
        return var_3


class Links(_BaseStructParser):
    """dummy link collector from <a> tag
        Links view() item signature:

    {
        "key": "String",
        "value": "String"
    }
    """

    def __init__(self, document: str):
        super().__init__(document)
        self._cached_result: _T_DICT_ITEM = {}

    def _part_document(self) -> SelectorList:
        doc = self.__selector__
        var_0 = doc
        var_1 = var_0.css("a")
        return var_1

    def _start_parse(self):
        self._cached_result.clear()
        for part in self._part_document():
            self._cached_result[self._parse_key(part)] = self._parse_value(part)

    def view(self) -> _T_DICT_ITEM:
        return self._cached_result

    def _parse_key(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.css("::text").get()
        var_2 = var_1.strip(" ")
        return var_2

    def _parse_value(self, doc: Selector):
        var_0 = doc
        var_1 = var_0.attrib["href"]
        return var_1
