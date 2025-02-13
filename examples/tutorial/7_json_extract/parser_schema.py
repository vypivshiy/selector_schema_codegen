# autogenerated by ssc-gen DO NOT_EDIT
from __future__ import annotations
import json
from typing import List, TypedDict, Union
import sys

if sys.version_info >= (3, 10):
    from types import NoneType
else:
    NoneType = type(None)

from parsel import Selector, SelectorList

J_Attributes = TypedDict(
    "J_Attributes", {"spam": float, "eggs": str, "default": NoneType}
)
J_Content = TypedDict("J_Content", {"a": List[str], "attributes": J_Attributes})
T_Main = TypedDict("T_Main", {"jsn": J_Content})


class Main:
    """

    {
        "jsn": {
            "a": "string",
            "attributes": {
                "spam": "float",
                "eggs": "string",
                "default": "null"
            }
        }
    }"""

    def __init__(self, document: Union[str, SelectorList, Selector]) -> None:
        self._doc = (
            Selector(document) if isinstance(document, str) else document
        )

    def _parse_jsn(self, value: Selector) -> J_Content:
        value1 = value.css("script")
        value2 = "".join(value1.css("::text").getall())
        value3 = json.loads(value2)
        return value3

    def parse(self) -> T_Main:
        return {"jsn": self._parse_jsn(self._doc)}
