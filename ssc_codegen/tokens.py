from enum import IntEnum, auto


class VariableType(IntEnum):
    DOCUMENT = auto()
    LIST_DOCUMENT = auto()
    STRING = auto()
    LIST_STRING = auto()
    # default wrapper marks
    OPTIONAL_STRING = auto()
    OPTIONAL_LIST_STRING = auto()

    NULL = auto()
    # mark accept any variable type
    # used in return and default expr
    ANY = auto()

    # currently used for to_len() operation
    LIST_ANY = auto()

    # nested functions
    NESTED = auto()
    INT = auto()
    LIST_INT = auto()
    FLOAT = auto()
    LIST_FLOAT = auto()
    OPTIONAL_INT = auto()
    OPTIONAL_LIST_INT = auto()
    OPTIONAL_FLOAT = auto()
    OPTIONAL_LIST_FLOAT = auto()

    JSON = auto()
    OPTIONAL_JSON = auto()

    BOOL = auto()


class JsonVariableType(IntEnum):
    # https://json-schema.org/understanding-json-schema/reference/type
    NUMBER = auto()
    STRING = auto()
    FLOAT = auto()
    BOOLEAN = auto()

    OBJECT = auto()
    ARRAY = auto()

    ARRAY_OBJECTS = auto()
    ARRAY_NUMBER = auto()
    ARRAY_STRING = auto()
    ARRAY_FLOAT = auto()
    ARRAY_BOOLEAN = auto()

    OPTIONAL_NUMBER = auto()
    OPTIONAL_STRING = auto()
    OPTIONAL_FLOAT = auto()
    OPTIONAL_BOOLEAN = auto()

    NULL = auto()


class StructType(IntEnum):
    BASE = auto()

    ITEM = auto()
    DICT = auto()
    LIST = auto()
    FLAT_LIST = auto()
    ACC_LIST = auto()

    # current DSL fronted impl auto convert
    # StructType.ITEM to StructType.CONFIG_LITERALS (Singleton structure)
    # if StructType.ITEM not contains parse fields documents
    CONFIG_CLASSVARS = auto()


class TokenType(IntEnum):
    # UTILS
    DOCSTRING = auto()
    IMPORTS = auto()
    VARIABLE = auto()
    MODULE = auto()
    CLASSVAR = auto()
    """used for configuration purposes

    this variable should be not change in the multithread parse mode 
    due to the risk of race-condition or other side effects.
    """

    # utils nodes
    CODE_START = auto()
    """insert to ast after DOCSTRING and IMPORTS tokens
    
    maybe used for inject custom code after generate docstring and imports strings
    """

    CODE_END = auto()
    """insert to end an ast tree.

    maybe usef for inject custom code or logic
    """

    # STRUCTS
    STRUCT = auto()
    STRUCT_INIT = auto()
    """used for OOP, or init base class/struct attributes if the target language supports the OOP paradigm"""
    STRUCT_FIELD = auto()
    """parse function key. Stores the parser logic for each field"""
    STRUCT_PRE_VALIDATE = auto()
    """Validate document input before run parser"""

    STRUCT_PART_DOCUMENT = auto()
    """Split document to parts for several structures"""
    STRUCT_PARSE_START = auto()
    """start parse enrtypoint"""

    STRUCT_CALL_FUNCTION = auto()  # CALL STRUCT_FIELD EXPR
    """contains inner `STRUCT_PARSE_START` node. Means that it calls a function/method for parsing"""
    STRUCT_CALL_CLASSVAR = auto()
    """contains inner `STRUCT_PARSE_START` node. Means that it push CLASSVAR value"""

    # TYPES
    # If target language is not static-typed or not supports type-hints - will be ignored and not generated
    TYPEDEF = auto()
    TYPEDEF_FIELD = auto()

    # Should be a first in parse expressions
    # later will be converted to EXPR_DEFAULT_START and EXPR_DEFAULT_END
    EXPR_DEFAULT = auto()

    # auto marks by EXPR_DEFAULT
    EXPR_DEFAULT_START = auto()
    EXPR_DEFAULT_END = auto()

    # NESTED STRUCTS
    EXPR_NESTED = auto()

    # RETURN EXPR (AUTO SET)
    EXPR_RETURN = auto()
    # USED IN __PRE_VALIDATE__ ATTR (AUTO SET)
    EXPR_NO_RETURN = auto()

    # DOCUMENT
    EXPR_CSS = auto()
    EXPR_XPATH = auto()
    EXPR_ATTR = auto()
    EXPR_TEXT = auto()
    EXPR_RAW = auto()
    EXPR_MAP_ATTRS = auto()

    # DOCUMENT (side effect)
    EXPR_CSS_REMOVE = auto()
    EXPR_XPATH_REMOVE = auto()

    # LIST_DOCUMENT
    EXPR_CSS_ALL = auto()
    EXPR_XPATH_ALL = auto()
    EXPR_ATTR_ALL = auto()
    EXPR_TEXT_ALL = auto()
    EXPR_RAW_ALL = auto()
    EXPR_MAP_ATTRS_ALL = auto()

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
    EXPR_STRING_RM_PREFIX = auto()
    EXPR_STRING_RM_SUFFIX = auto()
    EXPR_STRING_RM_PREFIX_AND_SUFFIX = auto()
    EXPR_STRING_MAP_REPLACE = auto()
    EXPR_STRING_UNESCAPE = auto()

    # LIST_STRING
    EXPR_LIST_REGEX_SUB = auto()
    EXPR_LIST_STRING_TRIM = auto()
    EXPR_LIST_STRING_LTRIM = auto()
    EXPR_LIST_STRING_RTRIM = auto()
    EXPR_LIST_STRING_FORMAT = auto()
    EXPR_LIST_STRING_REPLACE = auto()
    EXPR_LIST_STRING_RM_PREFIX = auto()
    EXPR_LIST_STRING_RM_SUFFIX = auto()
    EXPR_LIST_STRING_RM_PREFIX_AND_SUFFIX = auto()
    EXPR_LIST_STRING_MAP_REPLACE = auto()
    EXPR_LIST_STRING_UNESCAPE = auto()

    # ARRAY
    EXPR_LIST_ANY_INDEX = auto()
    EXPR_LIST_JOIN = auto()
    EXPR_LIST_LEN = auto()
    EXPR_LIST_UNIQUE = auto()

    # ASSERT
    IS_EQUAL = auto()
    IS_NOT_EQUAL = auto()
    IS_CONTAINS = auto()
    IS_CSS = auto()
    IS_XPATH = auto()
    IS_STRING_REGEX_MATCH = auto()
    ANY_LIST_STRING_REGEX_MATCH = auto()
    ALL_LIST_STRING_REGEX_MATCH = auto()
    HAS_ATTR = auto()
    HAS_LIST_ATTR = auto()

    # NUMERIC
    TO_INT = auto()
    TO_INT_LIST = auto()
    TO_FLOAT = auto()
    TO_FLOAT_LIST = auto()

    # JSON OP
    TO_JSON = auto()
    # STRUCTS
    JSON_STRUCT = auto()
    JSON_FIELD = auto()

    # bool
    TO_BOOL = auto()

    # FILTER
    EXPR_FILTER = auto()

    FILTER_OR = auto()
    FILTER_AND = auto()
    FILTER_NOT = auto()
    # FILTER EXPR (STR)
    FILTER_STR_IN = auto()
    FILTER_STR_STARTS = auto()
    FILTER_STR_ENDS = auto()
    FILTER_STR_RE = auto()

    FILTER_STR_LEN_EQ = auto()
    FILTER_STR_LEN_NE = auto()
    FILTER_STR_LEN_LT = auto()
    FILTER_STR_LEN_LE = auto()
    FILTER_STR_LEN_GT = auto()
    FILTER_STR_LEN_GE = auto()

    FILTER_EQ = auto()
    FILTER_NE = auto()


# collections of tokens (for static chekcks, etc)

TOKENS_REGEX = (
    TokenType.EXPR_REGEX,
    TokenType.EXPR_REGEX_ALL,
    TokenType.EXPR_REGEX_SUB,
    TokenType.EXPR_LIST_REGEX_SUB,
    TokenType.IS_STRING_REGEX_MATCH,
    TokenType.ALL_LIST_STRING_REGEX_MATCH,
    TokenType.ANY_LIST_STRING_REGEX_MATCH,
)

TOKENS_DEFAULT = (
    TokenType.EXPR_DEFAULT,
    TokenType.EXPR_DEFAULT_START,
    TokenType.EXPR_DEFAULT_END,
)
