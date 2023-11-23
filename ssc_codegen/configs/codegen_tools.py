from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from ssc_codegen.lexer import TokenType
from ssc_codegen.objects import VariableState

if TYPE_CHECKING:
    from ssc_codegen.objects import Node

__all__ = ["ABCExpressionTranslator"]


class ABCExpressionTranslator(ABC):
    """collection rules and hooks for translate to programming languages"""

    # method arg
    METHOD_ARG_NAME: str = NotImplemented
    # variable prefix
    VAR_NAME: str = NotImplemented
    # first variable assigment (if needed)
    FIRST_ASSIGMENT: str = NotImplemented
    # next assignments
    ASSIGMENT: str = NotImplemented
    # \n, ; for examples
    DELIM_LINES: str = NotImplemented
    # delim for try\catch constructions: maybe `\n\t`, `;\n\t`
    DELIM_DEFAULT_WRAPPER: str = NotImplemented
    # imports
    REGEX_IMPORT: str = NotImplemented
    SELECTOR_IMPORT: str = NotImplemented
    #######
    # types
    #######
    # SELECTOR
    SELECTOR_TYPE: str = NotImplemented
    ELEMENT_TYPE: str = NotImplemented
    # SELECTOR_ARRAY
    LIST_OF_ELEMENTS_TYPE: str = NotImplemented
    # ARRAY
    LIST_OF_STRING_TYPE: str = NotImplemented
    # TEXT
    STRING_TYPE: str = NotImplemented

    # generators config TODO
    ALLOW_FLUENT_OPTIMIZATION: bool = False
    # convert commands to css queries
    AUTO_CONVERT_TO_CSS: bool = False
    # convert commands to xpath queries
    AUTO_CONVERT_TO_XPATH: bool = False
    XPATH_START_PREFIX: str = "descendant-or-self::"

    def _gen_var_name(self, node: "Node") -> str:
        """generate variable name shortcut"""
        """assert <name> <expr"""
        if node is None:
            return self.METHOD_ARG_NAME

        _id = node.id
        if _id is None:
            return self.METHOD_ARG_NAME
        return f"{self.VAR_NAME}_{_id}"

    def _VAR(self, node: "Node") -> str:
        """alias of _gen_var_name(node)"""
        return self._gen_var_name(node)

    def _VAR_P(self, node: "Node") -> str:
        """alias of _gen_var_name(node.prev_node)"""
        return self._gen_var_name(node.prev_node)

    @abstractmethod
    def op_no_ret(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_ret(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_wrap_code_with_default_value(
        self,
        node: "Node",
        code: str,
        default_value: str,
    ) -> str:
        pass

    @abstractmethod
    def op_wrap_code(self, node: "Node", code: str) -> str:
        pass

    @abstractmethod
    def op_css(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_xpath(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_css_all(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_xpath_all(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_attr(self, node: "Node", attr_name: str) -> str:
        pass

    @abstractmethod
    def op_text(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_raw(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_string_split(self, node: "Node", substr: str, count=None) -> str:
        pass

    @abstractmethod
    def op_string_format(self, node: "Node", substr: str) -> str:
        pass

    @abstractmethod
    def op_string_trim(self, node: "Node", substr: str) -> str:
        pass

    @abstractmethod
    def op_string_ltrim(self, node: "Node", substr: str) -> str:
        pass

    @abstractmethod
    def op_string_rtrim(self, node: "Node", substr) -> str:
        pass

    @abstractmethod
    def op_string_replace(
        self, node: "Node", old: str, new: str, count=None
    ) -> str:
        pass

    @abstractmethod
    def op_string_join(self, node: "Node", string: str) -> str:
        pass

    @abstractmethod
    def op_regex(self, node: "Node", pattern: str) -> str:
        pass

    @abstractmethod
    def op_regex_all(self, node: "Node", pattern: str) -> str:
        pass

    @abstractmethod
    def op_regex_sub(
        self,
        node: "Node",
        pattern: str,
        repl: str,
        count=None,
    ) -> str:
        pass

    @abstractmethod
    def op_limit(self, node: "Node", max_: str) -> str:
        # TODO rename to OP_LIMIT
        pass

    @abstractmethod
    def op_index(self, node: "Node", index: str) -> str:
        pass

    @abstractmethod
    def op_first_index(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_last_index(self, node: "Node") -> str:
        pass

    @abstractmethod
    def op_assert_equal(self, node: "Node", substring: str) -> str:
        pass

    @abstractmethod
    def op_assert_css(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_assert_xpath(self, node: "Node", query: str) -> str:
        pass

    @abstractmethod
    def op_assert_re_match(self, node: "Node", pattern: str) -> str:
        pass

    @abstractmethod
    def op_assert_starts_with(self, node: "Node", prefix: str) -> str:
        pass

    @abstractmethod
    def op_assert_ends_with(self, node: "Node", suffix: str) -> str:
        pass

    @abstractmethod
    def op_assert_contains(self, node: "Node", substring: str) -> str:
        pass

    @abstractmethod
    def op_skip_pre_validate(self) -> str:
        """stub if `pre_validate` key not provided in config"""
        pass

    @abstractmethod
    def op_skip_part_document(self) -> str:
        """stub if `split` key not provided in config"""
        pass

    @abstractmethod
    def op_ret_nothing(self) -> str:
        pass

    @abstractmethod
    def op_ret_text(self) -> str:
        pass

    @abstractmethod
    def op_ret_array(self) -> str:
        pass

    @abstractmethod
    def op_ret_selector(self) -> str:
        pass

    @abstractmethod
    def op_ret_selector_array(self) -> str:
        pass

    def op_ret_type(self, node: "Node") -> str:
        val_state = node.return_arg_type
        match val_state:
            case VariableState.NO_RETURN:
                return self.op_ret_nothing()
            case VariableState.TEXT:
                return self.op_ret_text()
            case VariableState.ARRAY:
                return self.op_ret_array()
            case VariableState.SELECTOR:
                return self.op_ret_selector()
            case VariableState.SELECTOR_ARRAY:
                return self.op_ret_selector_array()

    @property
    def tokens_map(
        self,
    ) -> dict[TokenType, Callable[["Node", Any, ...], str]]:
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
            TokenType.OP_LIMIT: self.op_limit,
            TokenType.OP_JOIN: self.op_string_join,
            # CODE WRAPPERS
            TokenType.OP_TRANSLATE_DEFAULT_CODE: self.op_wrap_code_with_default_value,
            TokenType.OP_TRANSLATE_CODE: self.op_wrap_code,
            # VALIDATORS
            TokenType.OP_ASSERT: self.op_assert_equal,
            TokenType.OP_ASSERT_CONTAINS: self.op_assert_contains,
            TokenType.OP_ASSERT_STARTSWITH: self.op_assert_starts_with,
            TokenType.OP_ASSERT_ENDSWITH: self.op_assert_ends_with,
            TokenType.OP_ASSERT_MATCH: self.op_assert_re_match,
            TokenType.OP_ASSERT_CSS: self.op_assert_css,
            TokenType.OP_ASSERT_XPATH: self.op_assert_xpath,
            TokenType.OP_NO_RET: self.op_no_ret,
            TokenType.OP_RET: self.op_ret,
        }
