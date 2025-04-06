from typing import NamedTuple

from typing_extensions import Self
from ssc_codegen.ast_ import (
    ExprIsXpath,
    ExprXpathAll,
    ExprXpath,
    ExprIsCss,
    ExprCssAll,
    ExprCss,
)
from ssc_codegen.tokens import TokenType

T_SELECT_LIKE_EXPR = (
    ExprCss | ExprCssAll | ExprXpath | ExprXpathAll | ExprIsCss | ExprIsXpath
)
SELECT_LIKE_EXPR = (
    ExprCss.kind,
    ExprCssAll.kind,
    ExprXpath.kind,
    ExprXpathAll.kind,
    ExprIsCss.kind,
    ExprIsXpath.kind,
)
SELECT_CSS_EXPR = (ExprCss.kind, ExprCssAll.kind, ExprIsCss.kind)
SELECT_XPATH_EXPR = (ExprXpath.kind, ExprXpathAll.kind, ExprIsXpath.kind)

# prettify tokens to method names
FMT_MAPPING_METHODS = {
    TokenType.EXPR_DEFAULT: "default",
    TokenType.EXPR_NESTED: "sub_parser",
    TokenType.EXPR_CSS: "css",
    TokenType.EXPR_XPATH: "xpath",
    TokenType.EXPR_ATTR: "attr",
    TokenType.EXPR_TEXT: "text",
    TokenType.EXPR_RAW: "raw",
    TokenType.EXPR_CSS_ALL: "css_all",
    TokenType.EXPR_XPATH_ALL: "xpath_all",
    TokenType.EXPR_ATTR_ALL: "attr",
    TokenType.EXPR_TEXT_ALL: "text",
    TokenType.EXPR_RAW_ALL: "raw",
    TokenType.EXPR_REGEX: "re",
    TokenType.EXPR_REGEX_ALL: "re_all",
    TokenType.EXPR_REGEX_SUB: "re_sub",
    TokenType.EXPR_STRING_TRIM: "trim",
    TokenType.EXPR_STRING_LTRIM: "ltrim",
    TokenType.EXPR_STRING_RTRIM: "rtrim",
    TokenType.EXPR_STRING_REPLACE: "repl",
    TokenType.EXPR_STRING_FORMAT: "fmt",
    TokenType.EXPR_STRING_SPLIT: "split",
    TokenType.EXPR_LIST_REGEX_SUB: "re_sub",
    TokenType.EXPR_LIST_STRING_TRIM: "trim",
    TokenType.EXPR_LIST_STRING_LTRIM: "ltrim",
    TokenType.EXPR_LIST_STRING_RTRIM: "rtrim",
    TokenType.EXPR_LIST_STRING_FORMAT: "fmt",
    TokenType.EXPR_LIST_STRING_REPLACE: "repl",
    TokenType.EXPR_LIST_ANY_INDEX: "index",
    TokenType.EXPR_LIST_JOIN: "join",
    TokenType.EXPR_LIST_LEN: "to_len",
    TokenType.IS_EQUAL: "is_equal",
    TokenType.IS_NOT_EQUAL: "is_not_equal",
    TokenType.IS_CONTAINS: "is_contains",
    TokenType.IS_CSS: "is_css",
    TokenType.IS_XPATH: "is_xpath",
    TokenType.IS_STRING_REGEX_MATCH: "is_regex",
    TokenType.ANY_LIST_STRING_REGEX_MATCH: "any_is_re",
    TokenType.ALL_LIST_STRING_REGEX_MATCH: "all_is_re",
    TokenType.TO_INT: "to_int",
    TokenType.TO_INT_LIST: "to_int",
    TokenType.TO_FLOAT: "to_float",
    TokenType.TO_FLOAT_LIST: "to_float",
    TokenType.TO_JSON: "jsonify",
    TokenType.TO_BOOL: "to_bool",
}


class AnalyzeResult(NamedTuple):
    value: bool
    msg: str

    def __bool__(self) -> bool:
        return self.value

    @classmethod
    def ok(cls) -> Self:
        return cls(True, "")

    @classmethod
    def error(cls, msg: str) -> Self:
        return cls(False, msg)
