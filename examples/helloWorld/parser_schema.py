# autogenerated by ssc-gen DO NOT_EDIT
from __future__ import annotations
from typing import TypedDict, Union
import sys

if sys.version_info >= (3, 10):
    from types import NoneType
else:
    NoneType = type(None)

from parsel import Selector
from parsel.selector import _SelectorType  # noqa

T_HelloWorld = TypedDict(
    "T_HelloWorld",
    {
        "title": str,
    },
)


class HelloWorld:
    """

    {
        "title": "String"
    }"""

    def __init__(self, document: Union[str, _SelectorType]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    def _parse_title(self, value: Selector) -> str:
        value1 = value.css("title")
        return "".join(value1.css("::text").getall())

    def parse(self) -> T_HelloWorld:
        return {"title": self._parse_title(self._doc)}
