import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum


    class StrEnum(str, Enum):
        pass


class SchemaType(StrEnum):
    BASE = "BASE"  # base
    ITEM = "Map"
    LIST_ITEM = "Array[Map]"
    LIST_FLATTEN = "Array"
    DICT = "MAP_PAIR"


class SchemaKeywords(StrEnum):
    SPLIT_DOC = "__SPLIT_DOC__"
    FLAT_LIST_ITEM = "__ITEM__"
    DICT_KEY = "__KEY__"
    DICT_VALUE = "__VALUE__"
    PRE_VALIDATE = "__PRE_VALIDATE__"


SNAKE_CASE_ALIASES = {
    SchemaKeywords.SPLIT_DOC: "_part_document",
    SchemaKeywords.FLAT_LIST_ITEM: "_parse_item",
    SchemaKeywords.DICT_KEY: "_parse_key",
    SchemaKeywords.DICT_VALUE: "_parse_value",
    SchemaKeywords.PRE_VALIDATE: "_pre_validate",
}

CAMEL_CASE_ALIASES = {
    SchemaKeywords.SPLIT_DOC: "_partDocument",
    SchemaKeywords.FLAT_LIST_ITEM: "_parseItem",
    SchemaKeywords.DICT_KEY: "_parseKey",
    SchemaKeywords.DICT_VALUE: "_parseValue",
    SchemaKeywords.PRE_VALIDATE: "_preValidate",
}
