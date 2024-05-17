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
    OP_NESTED_SCHEMA = 25

    # BUILDER TOKENS
    ST_DOCSTRING = 100
    ST_INIT = 101  # init first var. should be start at element
    ST_PRE_VALIDATE = 102
    ST_DEFAULT = 103  # default method wrapper
    ST_METHOD = 104
    ST_NO_RET = 105  # __PRE_VALIDATE__ try/catch wraps
    ST_RET = 106
