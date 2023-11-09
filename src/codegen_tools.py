import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Optional, overload
from dataclasses import dataclass

from src.lexer import TokenType
from src.analyzer import VariableState, Analyzer

if TYPE_CHECKING:
    from src.lexer import Token


__all__ = ['ABCExpressionTranslator', 'generate_code']


class ABCExpressionTranslator(ABC):
    """collection rules HOW NEED translate tokens to code"""
    # variable name (be overwritten step-by-step)
    VAR_NAME: str = NotImplemented
    # first variable assigment (if needed)
    FIRST_ASSIGMENT: str = NotImplemented
    # next assignments
    ASSIGMENT: str = NotImplemented
    # \n, ; for example
    DELIM_LINES: str = NotImplemented
    # delim for try\catch constructions: maybe `\n\t`, `;\n\t`
    DELIM_DEFAULT_WRAPPER: str = NotImplemented
    # imports
    REGEX_IMPORT: str = NotImplemented
    SELECTOR_IMPORT: str = NotImplemented
    # selector type
    SELECTOR_TYPE: str = NotImplemented

    @classmethod
    @abstractmethod
    def op_wrap_code_with_default_value(cls, state: Optional[VariableState], var_i: int, code: str, default_value: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_wrap_code(cls, state: Optional[VariableState], var_i: int, code: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_css(cls, state: VariableState, var_i: int, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_xpath(cls, state: VariableState, var_i: int, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_css_all(cls, state: VariableState, var_i: int, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_xpath_all(cls, state: VariableState, var_i: int, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_attr(cls, state: VariableState, var_i: int, attr_name: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_text(cls, state: VariableState, var_i: int) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_raw(cls, state: VariableState, var_i: int) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_split(cls, state: VariableState, var_i: int, substr: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_format(cls, state: VariableState, var_i: int, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_trim(cls, state: VariableState, var_i: int, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_ltrim(cls, state: VariableState, var_i: int, substr: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_rtrim(cls, state: VariableState, var_i: int, substr) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_replace(cls, state: VariableState, var_i: int, old: str, new: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_string_join(cls, state: VariableState, var_i: int, string: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex(cls, state: VariableState, var_i: int, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex_all(cls, state: VariableState, var_i: int, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_regex_sub(cls, state: VariableState, var_i: int, pattern: str, repl: str, count=None) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_slice(cls, state: VariableState, var_i: int, start: str, end: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_index(cls, state: VariableState, var_i: int, index: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_first_index(cls, state: VariableState, var_i: int):
        pass

    @classmethod
    @abstractmethod
    def op_last_index(cls, state: VariableState, var_i: int):
        pass

    @classmethod
    @abstractmethod
    def op_assert_equal(cls, state: VariableState, var_i: int, substring: str):
        pass

    @classmethod
    @abstractmethod
    def op_assert_css(cls, state: VariableState, var_i: int, query: str):
        pass

    @classmethod
    @abstractmethod
    def op_assert_xpath(cls, state: VariableState, var_i: int, query: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_re_match(cls, state: VariableState, var_i: int, pattern: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_starts_with(cls, state: VariableState, var_i: int, prefix: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_ends_with(cls, state: VariableState, var_i: int, suffix: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def op_assert_contains(cls, state: VariableState, var_i: int, substring: str) -> str:
        pass

    @property
    def tokens_map(self) -> dict[TokenType: Callable[[VariableState, int, ...], str]]:
        """return dict by token_type : cast_token_to_code method"""
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
            TokenType.OP_DEFAULT: self.op_wrap_code_with_default_value,
            TokenType.OP_DEFAULT_CODE: self.op_wrap_code,
            # VALIDATORS
            TokenType.OP_ASSERT: self.op_assert_equal,
            TokenType.OP_ASSERT_CONTAINS: self.op_assert_contains,
            TokenType.OP_ASSERT_STARTSWITH: self.op_assert_starts_with,
            TokenType.OP_ASSERT_ENDSWITH: self.op_assert_ends_with,
            TokenType.OP_ASSERT_MATCH: self.op_assert_re_match,
            TokenType.OP_ASSERT_CSS: self.op_assert_css,
            TokenType.OP_ASSERT_XPATH: self.op_assert_xpath
        }


@dataclass
class BlockCode:
    """generated block code structure"""
    code: str
    selector_import: str
    selector_type: str
    var_name: str
    translator_instance: ABCExpressionTranslator
    regex_import: Optional[str] = None
    name: str = "dummy"


@overload
def generate_code(tokens: list["Token"],
                  translator: ABCExpressionTranslator,
                  *,
                  convert_to_css: bool = False) -> BlockCode:
    pass


@overload
def generate_code(tokens: list["Token"],
                  translator: ABCExpressionTranslator,
                  *,
                  convert_to_xpath: bool = False,
                  xpath_prefix: Optional[str] = None) -> BlockCode:
    pass


def generate_code(tokens: list["Token"],
                  translator: ABCExpressionTranslator,
                  *,
                  convert_to_css: bool = False,
                  convert_to_xpath: bool = False,
                  xpath_prefix: Optional[str] = None
                  ) -> BlockCode:

    default_token = None  # default token detect var
    lines = []
    regex_import: Optional[str] = None
    selector_import = translator.SELECTOR_IMPORT
    selector_type = translator.SELECTOR_TYPE

    analyze = Analyzer(tokens)
    if convert_to_css and convert_to_xpath:
        warnings.warn("Passed css and xpath converters, ignore operation", category=RuntimeWarning)

    elif convert_to_css:
        analyze.convert_xpath_to_css()

    elif convert_to_xpath:
        analyze.convert_css_to_xpath(xpath_prefix) if xpath_prefix else analyze.convert_css_to_xpath()

    for i, ctx_token in enumerate(analyze.lazy_analyze()):
        token, var_state = ctx_token
        if i == 0 and token.token_type == TokenType.OP_DEFAULT:
            default_token = token
            continue

        if token.token_type in TokenType.tokens_regex():
            regex_import = translator.REGEX_IMPORT

        # generate line code
        translator_method = translator.tokens_map.get(token.token_type)
        c = translator_method(var_state, i, *token.values)
        if token.token_type not in TokenType.tokens_asserts():
            c = f"{translator.VAR_NAME} {translator.ASSIGMENT} {c}"
        lines.append(c)

    # assembly
    code = translator.DELIM_LINES.join(lines)
    if default_token:
        full_code = translator.op_wrap_code_with_default_value(None, i + 1, code, *default_token.values)
    else:
        full_code = translator.op_wrap_code(None, i + 1, code)

    return BlockCode(code=full_code,
                     regex_import=regex_import,
                     selector_import=selector_import,
                     selector_type=selector_type,
                     var_name=translator.VAR_NAME,
                     translator_instance=translator)
