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


class TokenType(IntEnum):
    # UTILS
    DOCSTRING = auto()
    IMPORTS = auto()
    VARIABLE = auto()
    MODULE = auto()

    # STRUCTS
    STRUCT = auto()
    STRUCT_INIT = auto()  # used for OOP, or init base class/struct attributes
    STRUCT_FIELD = auto()  # PARSE FUNCTION KEY
    STRUCT_PRE_VALIDATE = auto()  # VALIDATE DOC INPUT BEFORE PARSE
    STRUCT_PART_DOCUMENT = auto()  # SPLIT DOCUMENT TO PARTS
    STRUCT_PARSE_START = auto()  # START PARSE ENTRYPOINT
    STRUCT_CALL_FUNCTION = auto()  # CALL STRUCT_FIELD EXPR

    # TYPES
    TYPEDEF = auto()
    TYPEDEF_FIELD = auto()

    # FIRST
    EXPR_DEFAULT = auto()

    # auto marks by EXPR_DEFAULT
    EXPR_DEFAULT_START = auto()
    EXPR_DEFAULT_END = auto()

    # NESTED STRUCTS
    EXPR_NESTED = auto()

    # RETURN EXPR (AUTO SET)
    EXPR_RETURN = auto()
    # RETURN EXPR (AUTO SET)
    # USED IN __PRE_VALIDATE__ ATTR
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
    EXPR_STRING_RM_PREFIX = auto()
    EXPR_STRING_RM_SUFFIX = auto()
    EXPR_STRING_RM_PREFIX_AND_SUFFIX = auto()

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
    # ARRAY
    EXPR_LIST_ANY_INDEX = auto()
    EXPR_LIST_JOIN = auto()
    EXPR_LIST_LEN = auto()

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

    @classmethod
    def default_tokens(cls) -> tuple["TokenType", ...]:
        return (
            TokenType.EXPR_DEFAULT,
            TokenType.EXPR_DEFAULT_START,
            TokenType.EXPR_DEFAULT_END,
        )

    @classmethod
    def assert_tokens(cls) -> tuple["TokenType", ...]:
        return (
            TokenType.IS_CSS,
            TokenType.IS_XPATH,
            TokenType.IS_EQUAL,
            TokenType.IS_NOT_EQUAL,
            TokenType.IS_CONTAINS,
            TokenType.IS_STRING_REGEX_MATCH,
        )

    @classmethod
    def regex_tokens(cls) -> tuple["TokenType", ...]:
        return (
            TokenType.EXPR_REGEX,
            TokenType.EXPR_REGEX_ALL,
            TokenType.EXPR_REGEX_SUB,
            TokenType.EXPR_LIST_REGEX_SUB,
            TokenType.IS_STRING_REGEX_MATCH,
        )
