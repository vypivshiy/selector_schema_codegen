import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

from src.lexer import TokenType, tokenize
from src.analyzer import Analyzer

if TYPE_CHECKING:
    from src.lexer import Token


class ABCExpressionTranslator(ABC):
    """collection rules HOW NEED translate tokens to code"""
    # extract one element
    FETCH_ONE: str = NotImplemented
    # extract all elements
    FETCH_ALL: str = NotImplemented
    # variable name (be overwritten step-by-step)
    VAR_NAME: str = NotImplemented
    # first variable assigment (if needed)
    FIRST_ASSIGMENT: str = NotImplemented
    # next assignments
    ASSIGMENT: str = NotImplemented
    # \n, ; for example
    DELIM_LINES: str = NotImplemented
    # delim for try\catch constructions
    DELIM_DEFAULT_WRAPPER: str = NotImplemented
    # imports
    REGEX_IMPORT: str = NotImplemented
    SELECTOR_IMPORT: str = NotImplemented
    # selector type
    SELECTOR_TYPE: str = NotImplemented

    @classmethod
    @abstractmethod
    def op_default_value_wrapper(cls, code: str, default_value: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_code_wrap_default(cls, code: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_css(cls, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_xpath(cls, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_css_all(cls, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_xpath_all(cls, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_attr(cls, attr_name: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_text(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_raw(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_split(cls, substr: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_format(cls, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_trim(cls, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_ltrim(cls, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_rtrim(cls, substr) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_replace(cls, old: str, new: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_join(cls, string: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex(cls, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex_all(cls, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex_sub(cls, pattern: str, repl: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_slice(cls, start: str, end: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_index(cls, index: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_first_index(cls):
        pass

    @classmethod
    @abstractmethod
    def op_last_index(cls):
        pass

    @classmethod
    @abstractmethod
    def op_assert_equal(cls, substring: str):
        pass

    @classmethod
    @abstractmethod
    def op_assert_css(cls, query: str):
        pass

    @classmethod
    @abstractmethod
    def op_assert_xpath(cls, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_re_match(cls, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_starts_with(cls, prefix: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_ends_with(cls, suffix: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_contains(cls, substring: str) -> str:
        pass

    @property
    def tokens_map(self) -> dict[TokenType: Callable[[...], str]]:
        return {
            TokenType.OP_XPATH: self.op_xpath,
            TokenType.OP_XPATH_ALL: self.op_xpath_all,
            TokenType.OP_CSS: self.op_css,
            TokenType.OP_CSS_ALL: self.op_css_all,
            TokenType.OP_ATTR: self.op_attr,
            TokenType.OP_ATTR_TEXT: self.op_text,
            TokenType.OP_ATTR_RAW: self.op_raw,
            # REGEX
            TokenType.OP_REGEX: self.op_regex,
            TokenType.OP_REGEX_ALL: self.op_regex_all,
            TokenType.OP_REGEX_SUB: self.op_regex_sub,
            # STRINGS
            TokenType.OP_STRING_TRIM: self.op_string_trim,
            TokenType.OP_STRING_L_TRIM: self.op_string_ltrim,
            TokenType.OP_STRING_R_TRIM: self.op_string_rtrim,
            TokenType.OP_STRING_REPLACE: self.op_string_replace,
            TokenType.OP_STRING_FORMAT: self.op_string_format,
            TokenType.OP_STRING_SPLIT: self.op_string_split,
            # ARRAY
            TokenType.OP_INDEX: self.op_index,
            TokenType.OP_FIRST: self.op_first_index,
            TokenType.OP_LAST: self.op_last_index,
            TokenType.OP_SLICE: self.op_slice,
            TokenType.OP_JOIN: self.op_string_join,
            # CODE WRAPPERS
            TokenType.OP_DEFAULT: self.op_default_value_wrapper,
            TokenType.OP_DEFAULT_CODE: self.op_code_wrap_default,
            # VALIDATORS
            TokenType.OP_ASSERT: self.op_assert_equal,
            TokenType.OP_ASSERT_CONTAINS: self.op_assert_contains,
            TokenType.OP_ASSERT_STARTSWITH: self.op_assert_starts_with,
            TokenType.OP_ASSERT_ENDSWITH: self.op_assert_ends_with,
            TokenType.OP_ASSERT_MATCH: self.op_assert_re_match,
            TokenType.OP_ASSERT_CSS: self.op_assert_css,
            TokenType.OP_ASSERT_XPATH: self.op_assert_xpath
        }


def generate_code(tokens: list["Token"], translator: ABCExpressionTranslator):
    pass
