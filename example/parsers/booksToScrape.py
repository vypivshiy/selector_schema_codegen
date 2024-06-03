# Auto generated code by ssc_gen
# WARNING: Any manual changes made to this file will be lost when this
# is run again. Do not edit this file unless you know what you are doing.

from typing import Optional, Dict, List
from parsel import Selector, SelectorList

from .baseStruct import BaseParser


class Urls(BaseParser):
    """
        fetch add patches and urls from <a> tag

    {
      "__ITEM__": "String"
    }
    """

    def _run_parse(self):
        return [
            self._parse_item(el)
            for el in self._part_document(self.__selector__)
        ]

    def _part_document(self, el):
        var = self._css_all(el, "a")
        return var

    def _parse_item(self, el):
        var = self._attr(el, "href")
        return var


class Books(BaseParser):
    """


    [
      {
        "name": "String",
        "image_url": "String",
        "url": "String",
        "rating": "String",
        "price": "String"
      },
      "..."
    ]
    """

    def _run_parse(self):
        return [
            {
                "name": self._parse_name(el),
                "image_url": self._parse_image_url(el),
                "url": self._parse_url(el),
                "rating": self._parse_rating(el),
                "price": self._parse_price(el),
            }
            for el in self._part_document(self.__selector__)
        ]

    def _part_document(self, el):
        var = self._css_all(el, ".col-lg-3")
        return var

    def _parse_name(self, el):
        var = self._css(el, ".thumbnail")
        var_1 = self._attr(var, "alt")
        return var_1

    def _parse_image_url(self, el):
        var = self._css(el, ".thumbnail")
        var_1 = self._attr(var, "src")
        return var_1

    def _parse_url(self, el):
        var = self._css(el, ".image_container > a")
        var_1 = self._attr(var, "href")
        return var_1

    def _parse_rating(self, el):
        var = self._css(el, ".star-rating")
        var_1 = self._attr(var, "class")
        var_2 = self._str_ltrim(var_1, "star-rating ")
        return var_2

    def _parse_price(self, el):
        try:
            var = self._css(el, ".price_color")
            var_1 = self._attr_text(var)
            var_2 = self._re_match(var_1, "\\d+")
            return var_2
        except Exception:
            return "0"


class CataloguePage(BaseParser):
    """


    {
      "title": "String",
      "urls": [
        "item",
        "..."
      ],
      "books": [
        {
          "name": "String",
          "image_url": "String",
          "url": "String",
          "rating": "String",
          "price": "String"
        },
        "..."
      ]
    }
    """

    def _run_parse(self):
        return {
            "title": self._parse_title(self.__selector__),
            "urls": self._parse_urls(self.__selector__),
            "books": self._parse_books(self.__selector__),
        }

    def _pre_validate(self, el):
        var = self._css(el, "title")
        var_1 = self._attr_text(var)
        var_2 = self._assert_re_match(var_1, "Books to Scrape", "")
        return

    def _parse_title(self, el):
        var = self._css(el, "title")
        var_1 = self._attr_text(var)
        return var_1

    def _parse_urls(self, el):
        var = self._nested_parser(el, Urls)
        return var

    def _parse_books(self, el):
        var = self._nested_parser(el, Books)
        return var