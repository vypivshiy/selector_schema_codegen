# autogenerated by ssc-gen DO NOT_EDIT

from __future__ import annotations
import re
import sys
from typing import List, TypedDict, Union, Optional
from contextlib import suppress

if sys.version_info >= (3, 10):
    from types import NoneType
else:
    NoneType = type(None)

from parsel import Selector, SelectorList
from parsel.selector import _SelectorType  # noqa

T_Book = TypedDict(
    "T_Book",
    {
        "name": str,
        "image_url": str,
        "url": str,
        "rating": str,
        "price": int,
    },
)
T_MainCatalogue = TypedDict(
    "T_MainCatalogue",
    {
        "books": List[T_Book],
        "prev_page": Optional[str],
        "next_page": Optional[str],
        "curr_page": str,
    },
)


class Book:
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

    def __init__(self, document: Union[str, _SelectorType]) -> None:
        self._document = (
            Selector(document) if isinstance(document, str) else document
        )

    def _split_doc(self, v: Union[Selector, _SelectorType]) -> SelectorList:
        return v.css(".col-lg-3")

    def _parse_name(self, v: Union[Selector, _SelectorType]) -> str:
        v0 = v.css(".thumbnail")
        return v0.attrib["alt"]

    def _parse_image_url(self, v: Union[Selector, _SelectorType]) -> str:
        v0 = v.css(".thumbnail")
        v1 = v0.attrib["src"]
        v2 = v1[len("..") :] if v1.startswith("..") else v1
        return f"https://books.toscrape.com/{v2}"

    def _parse_url(self, v: Union[Selector, _SelectorType]) -> str:
        v0 = v.css(".image_container > a")
        v1 = v0.attrib["href"]
        v2 = v1[len("catalogue") :] if v1.startswith("catalogue") else v1
        v3 = v2[len("/") :] if v2.startswith("/") else v2
        return f"https://books.toscrape.com/catalogue/{v3}"

    def _parse_rating(self, v: Union[Selector, _SelectorType]) -> str:
        v0 = v.css(".star-rating")
        v1 = v0.attrib["class"]
        return v1.lstrip("star-rating ")

    def _parse_price(self, v: Union[Selector, _SelectorType]) -> int:
        v0 = v
        with suppress(Exception):
            v1 = v0.css(".price_color")
            v2 = "".join(v1.css("::text").getall())
            v3 = re.search("(\\d+)", v2)[1]
            return int(v3)
        return 0

    def parse(self) -> List[T_Book]:
        return [
            {
                "name": self._parse_name(el),
                "image_url": self._parse_image_url(el),
                "url": self._parse_url(el),
                "rating": self._parse_rating(el),
                "price": self._parse_price(el),
            }
            for el in self._split_doc(self._document)
        ]


class MainCatalogue:
    """parse main catalogue page

        Response input examples:
            - https://books.toscrape.com/
            - https://books.toscrape.com/catalogue/page-2.html



    {
        "books": [
            {
                "name": "String",
                "image_url": "String",
                "url": "String",
                "rating": "String",
                "price": "Int"
            },
            "..."
        ],
        "prev_page": "String",
        "next_page": "String",
        "curr_page": "String"
    }"""

    def __init__(self, document: Union[str, _SelectorType]) -> None:
        self._document = (
            Selector(document) if isinstance(document, str) else document
        )

    def _parse_books(self, v: Union[Selector, _SelectorType]) -> List[T_Book]:
        return Book(v).parse()

    def _parse_prev_page(
        self, v: Union[Selector, _SelectorType]
    ) -> Optional[str]:
        v0 = v
        with suppress(Exception):
            v1 = v0.css(".previous a")
            v2 = v1.attrib["href"]
            return (
                v2[len("catalogue/") :] if v2.startswith("catalogue/") else v2
            )
        return None

    def _parse_next_page(
        self, v: Union[Selector, _SelectorType]
    ) -> Optional[str]:
        v0 = v
        with suppress(Exception):
            v1 = v0.css(".next a")
            v2 = v1.attrib["href"]
            v3 = v2[len("catalogue/") :] if v2.startswith("catalogue/") else v2
            return f"https://books.toscrape.com/catalogue/{v3}"
        return None

    def _parse_curr_page(self, v: Union[Selector, _SelectorType]) -> str:
        v0 = v.css(".current")
        v1 = "".join(v0.css("::text").getall())
        v2 = re.search("Page\\s(\\d+)", v1)[1]
        return f"https://books.toscrape.com/catalogue/page-{v2}.html"

    def parse(self) -> T_MainCatalogue:
        return {
            "books": self._parse_books(self._document),
            "prev_page": self._parse_prev_page(self._document),
            "next_page": self._parse_next_page(self._document),
            "curr_page": self._parse_curr_page(self._document),
        }
