# Token: DOCSTRING
"""Dummy parser config for http://books.toscrape.com/"""

# Token: IMPORTS
from __future__ import annotations

import re
from contextlib import suppress
from typing import List, TypedDict, Union

from parsel import Selector, SelectorList

# Token: TYPEDEF
T_Urls = List[str]
# Token: TYPEDEF
T_Books_ITEM = TypedDict(
    "T_Books_ITEM",
    {"name": str, "image_url": str, "url": str, "rating": str, "price": int},
)
T_Books = List[T_Books_ITEM]
# Token: TYPEDEF
T_CataloguePage = TypedDict(
    "T_CataloguePage", {"title": str, "urls": T_Urls, "books": T_Books}
)


# Token: STRUCT
class Urls:
    # Token: DOCSTRING
    """fetch add patches and urls from <a> tag

    [
        "String",
        "..."
    ]"""

    # Token: STRUCT_INIT
    def __init__(self, document: Union[str, SelectorList, Selector]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    # Token: STRUCT_PART_DOCUMENT
    def _split_doc(self, value: Selector) -> SelectorList:
        # Token: EXPR_CSS_ALL
        value1 = value.css("a")
        # Token: EXPR_RETURN ret_type: LIST_DOCUMENT
        return value1

    # Token: STRUCT_FIELD
    def _parse_item(self, value: Selector) -> str:
        # Token: EXPR_ATTR
        value1 = value.css("::attr(href)").get()
        # Token: EXPR_RETURN ret_type: STRING
        return value1

    # Token: STRUCT_PARSE_START struct_type: FLAT_LIST
    # Call instructions count: 2
    def parse(self) -> T_Urls:
        return [self._parse_item(e) for e in self._split_doc(self._doc)]


# Token: STRUCT
class Books:
    # Token: DOCSTRING
    """

    [
        {
            "name": "String",
            "image_url": "String",
            "url": "String",
            "rating": "String",
            "price": "Int"
        },
        "..."
    ]"""

    # Token: STRUCT_INIT
    def __init__(self, document: Union[str, SelectorList, Selector]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    # Token: STRUCT_PART_DOCUMENT
    def _split_doc(self, value: Selector) -> SelectorList:
        # Token: EXPR_CSS_ALL
        value1 = value.css(".col-lg-3")
        # Token: EXPR_RETURN ret_type: LIST_DOCUMENT
        return value1

    # Token: STRUCT_FIELD
    def _parse_name(self, value: Selector) -> str:
        # Token: EXPR_CSS
        value1 = value.css(".thumbnail")
        # Token: EXPR_ATTR
        value2 = value1.css("::attr(alt)").get()
        # Token: EXPR_RETURN ret_type: STRING
        return value2

    # Token: STRUCT_FIELD
    def _parse_image_url(self, value: Selector) -> str:
        # Token: EXPR_CSS
        value1 = value.css(".thumbnail")
        # Token: EXPR_ATTR
        value2 = value1.css("::attr(src)").get()
        # Token: EXPR_STRING_FORMAT
        value3 = "https://{}".format(value2) if value2 else value2
        # Token: EXPR_RETURN ret_type: STRING
        return value3

    # Token: STRUCT_FIELD
    def _parse_url(self, value: Selector) -> str:
        # Token: EXPR_CSS
        value1 = value.css(".image_container > a")
        # Token: EXPR_ATTR
        value2 = value1.css("::attr(href)").get()
        # Token: EXPR_RETURN ret_type: STRING
        return value2

    # Token: STRUCT_FIELD
    def _parse_rating(self, value: Selector) -> str:
        # Token: EXPR_CSS
        value1 = value.css(".star-rating")
        # Token: EXPR_ATTR
        value2 = value1.css("::attr(class)").get()
        # Token: EXPR_STRING_LTRIM
        value3 = value2.lstrip("star-rating ")
        # Token: EXPR_RETURN ret_type: STRING
        return value3

    # Token: STRUCT_FIELD
    def _parse_price(self, value: Selector) -> int:
        # Token: EXPR_DEFAULT_START
        value1 = value
        with suppress(Exception):
            # Token: EXPR_CSS
            value2 = value1.css(".price_color")
            # Token: EXPR_TEXT
            value3 = value2.css("::text").get()
            # Token: EXPR_REGEX
            value4 = re.search("(\\d+)", value3)[1]
            # Token: TO_INT
            value5 = int(value4)
            # Token: EXPR_RETURN ret_type: INT
            return value5
        # Token: EXPR_DEFAULT_END
        return 0

    # Token: STRUCT_PARSE_START struct_type: LIST
    # Call instructions count: 6
    def parse(self) -> List[T_Books]:
        return [
            {
                "name": self._parse_name(e),
                "image_url": self._parse_image_url(e),
                "url": self._parse_url(e),
                "rating": self._parse_rating(e),
                "price": self._parse_price(e),
            }
            for e in self._split_doc(self._doc)
        ]


# Token: STRUCT
class CataloguePage:
    # Token: DOCSTRING
    """

    {
        "title": "String",
        "urls": [
            "String",
            "..."
        ],
        "books": [
            {
                "name": "String",
                "image_url": "String",
                "url": "String",
                "rating": "String",
                "price": "ANY"
            },
            "..."
        ]
    }"""

    # Token: STRUCT_INIT
    def __init__(self, document: Union[str, SelectorList, Selector]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    # Token: STRUCT_PRE_VALIDATE
    def _pre_validate(self, value: Union[Selector, SelectorList]) -> None:
        # Token: EXPR_CSS
        value1 = value.css("title")
        # Token: EXPR_TEXT
        value2 = value1.css("::text").get()
        # Token: IS_REGEX_MATCH
        assert re.search("Books to Scrape", value2), ""
        # Token: EXPR_NO_RETURN
        return

    # Token: STRUCT_FIELD
    def _parse_title(self, value: Selector) -> str:
        # Token: EXPR_DEFAULT_START
        value1 = value
        with suppress(Exception):
            # Token: IS_CSS
            assert value1.css("title"), ""
            value2 = value1
            # Token: EXPR_CSS
            value3 = value2.css("title")
            # Token: EXPR_TEXT
            value4 = value3.css("::text").get()
            # Token: EXPR_REGEX_SUB
            value5 = re.sub("^\\s+", "", value4)
            # Token: EXPR_REGEX_SUB
            value6 = re.sub("\\s+$", "", value5)
            # Token: EXPR_RETURN ret_type: STRING
            return value6
        # Token: EXPR_DEFAULT_END
        return "test"

    # Token: STRUCT_FIELD
    def _parse_urls(self, value: Selector) -> T_Urls:
        # Token: EXPR_NESTED
        value1 = Urls(value).parse()
        # Token: EXPR_RETURN ret_type: NESTED
        return value1

    # Token: STRUCT_FIELD
    def _parse_books(self, value: Selector) -> List[T_Books]:
        # Token: EXPR_NESTED
        value1 = Books(value).parse()
        # Token: EXPR_RETURN ret_type: NESTED
        return value1

    # Token: STRUCT_PARSE_START struct_type: ITEM
    # Call instructions count: 4
    def parse(self) -> T_CataloguePage:
        self._pre_validate(self._doc)
        return {
            "title": self._parse_title(self._doc),
            "urls": self._parse_urls(self._doc),
            "books": self._parse_books(self._doc),
        }
