# autogenerated by ssc-gen DO NOT_EDIT
from __future__ import annotations
import re
from typing import TypedDict, Union
from contextlib import suppress

from parsel import Selector, SelectorList

T_Main = TypedDict("T_Main", {"title": str, "title_rescue_assert": str})


class Main:
    """Example validate document input and fields

        USAGE:
            - pass index.html document from 4_validation folder

        ISSUES:
            - if title not equal Demo page - throw error


    {
        "title": "String",
        "title_rescue_assert": "String"
    }"""

    def __init__(self, document: Union[str, SelectorList, Selector]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    def _pre_validate(self, value: Union[Selector, SelectorList]) -> None:
        assert value.css("title"), ""
        value1 = value
        value2 = value1.css("title")
        value3 = "".join(value2.css("::text").getall())
        assert value3 == "Demo page", ""
        value4 = value3
        assert value4 != "Real page", ""
        value5 = value4
        assert re.search("[dD]...\\s*p...", value5), ""
        value6 = value5
        value7 = value6.split(" ")
        assert "Demo" in value7, ""
        return

    def _parse_title(self, value: Selector) -> str:
        value1 = value.css("title")
        value2 = "".join(value1.css("::text").getall())
        assert value2 == "Demo page", ""
        value3 = value2
        return value3

    def _parse_title_rescue_assert(self, value: Selector) -> str:
        value1 = value
        with suppress(Exception):
            value2 = value1.css("title")
            value3 = "".join(value2.css("::text").getall())
            assert value3 == "IM not demo page!", ""
            value4 = value3
            return value4
        return "I SAY ITS DEMO PAGE"

    def parse(self) -> T_Main:
        self._pre_validate(self._doc)
        return {
            "title": self._parse_title(self._doc),
            "title_rescue_assert": self._parse_title_rescue_assert(self._doc),
        }
