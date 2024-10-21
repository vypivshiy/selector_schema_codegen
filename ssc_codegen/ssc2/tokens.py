from enum import IntEnum, auto


class VariableType(IntEnum):
    DOCUMENT = auto()
    LIST_DOCUMENT = auto()
    STRING = auto()
    LIST_STRING = auto()
    NULL = auto()
    # mark accept any variable type
    # used in return and default expr
    ANY = auto()
    # nested functions
    NESTED = auto()


class StructType(IntEnum):
    BASE = auto()

    ITEM = auto()
    DICT = auto()
    LIST = auto()
    FLAT_LIST = auto()


class TokenType(IntEnum):
    # UTILS
    DOCSTRING = auto()
    IMPORTS = auto()
    VARIABLE = auto()
    MODULE = auto()

    # STRUCTS
    STRUCT = auto()
    STRUCT_INIT = auto()  # used for OOP, or init base class/struct attributes
    STRUCT_FIELD = auto()
    STRUCT_PRE_VALIDATE = auto()
    STRUCT_PART_DOCUMENT = auto()
    STRUCT_PARSE_START = auto()
    STRUCT_CALL_FUNCTION = auto()

    # TYPING
    TYPEDEF = auto()
    TYPEDEF_FIELD = auto()

    # EXPR
    EXPR_DEFAULT = auto()
    EXPR_NESTED = auto()
    EXPR_RETURN = auto()
    EXPR_NO_RETURN = auto()

    # DOCUMENT
    EXPR_CSS = auto()
    EXPR_XPATH = auto()
    EXPR_ATTR = auto()
    EXPR_TEXT = auto()
    EXPR_RAW = auto()

    # LIST_DOCUMENT
    EXPR_CSS_ALL = auto()
    EXPR_XPATH_ALL = auto()
    EXPR_ATTR_ALL = auto()
    EXPR_TEXT_ALL = auto()
    EXPR_RAW_ALL = auto()

    # STRING
    EXPR_REGEX = auto()
    EXPR_REGEX_ALL = auto()
    EXPR_REGEX_SUB = auto()
    EXPR_STRING_TRIM = auto()
    EXPR_STRING_LTRIM = auto()
    EXPR_STRING_RTRIM = auto()
    EXPR_STRING_REPLACE = auto()
    EXPR_STRING_FORMAT = auto()
    EXPR_STRING_SPLIT = auto()

    # LIST_STRING
    EXPR_LIST_REGEX_SUB = auto()
    EXPR_LIST_STRING_TRIM = auto()
    EXPR_LIST_STRING_LTRIM = auto()
    EXPR_LIST_STRING_RTRIM = auto()
    EXPR_LIST_STRING_FORMAT = auto()
    EXPR_LIST_STRING_REPLACE = auto()

    # ARRAY
    EXPR_LIST_STRING_INDEX = auto()
    EXPR_LIST_DOCUMENT_INDEX = auto()
    EXPR_LIST_JOIN = auto()

    # ASSERT
    IS_EQUAL = auto()
    IS_NOT_EQUAL = auto()
    IS_CONTAINS = auto()
    IS_CSS = auto()
    IS_XPATH = auto()
    IS_REGEX_MATCH = auto()
