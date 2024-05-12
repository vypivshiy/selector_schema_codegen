from ssc_codegen2._compat import IntEnum


class TokenType(IntEnum):
    """Instructions tokens representation"""
    # SELECTORS
    OP_XPATH = 1
    "extract first element by xpath query"

    OP_XPATH_ALL = 2
    "extract all elements by xpath query"

    OP_CSS = 3
    "extract first element by css query"

    OP_CSS_ALL = 4
    "extract all elements by css query"

    OP_ATTR = 5
    "extract attribute from element"

    OP_ATTR_TEXT = 6
    "extract text inside attribute"

    OP_ATTR_RAW = 7
    "extract attribute and text"

    # REGEX
    # extract first result match
    OP_REGEX = 8
    # extract all result matches
    OP_REGEX_ALL = 9
    # crop result by regex pattern
    # spamegg ('^spam') -> egg
    OP_REGEX_SUB = 10
    # STRINGS
    # split by LEFT and RIGHT match
    OP_STRING_TRIM = 11
    # split by LEFT match
    OP_STRING_L_TRIM = 12
    # split by RIGHT
    OP_STRING_R_TRIM = 13
    # replace string by pattern
    OP_STRING_REPLACE = 14
    OP_STRING_FORMAT = 15
    OP_STRING_SPLIT = 16

    # ARRAY
    OP_INDEX = 17
    OP_JOIN = 18

    # DEFAULT VALUE IF parse result failed
    OP_DEFAULT = 19  # wrap try/catch mark

    # PRE VALIDATE OPERATIONS (assert)
    OP_ASSERT_EQUAL = 20
    OP_ASSERT_CONTAINS = 21
    OP_ASSERT_RE_MATCH = 22
    OP_ASSERT_CSS = 23
    OP_ASSERT_XPATH = 24

    # HELPER TOKENS
    OP_DOCSTRING = 100
    OP_METHOD_NAME = 101
    OP_INIT = 102  # init first var. should be start at element
    OP_NO_RET = 103  # __PRE_VALIDATE__ try/catch wraps
    OP_RET = 104

    # try/except or try/catch tokens
    OP_DEFAULT_START = 105
    OP_DEFAULT_END = 106

    # tokens for build struct classes
    OP_SCHEMA_NAME = 200
    OP_NESTED_SCHEMA = 201
    OP_SCHEMA_VALIDATOR = 202
    # pre-validate method before init
