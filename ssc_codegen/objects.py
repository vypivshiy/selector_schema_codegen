from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TokenType(Enum):
    """all command enum representation"""

    # SELECTORS
    OP_XPATH = 0
    OP_XPATH_ALL = 1
    OP_CSS = 2
    OP_CSS_ALL = 3
    OP_ATTR = 4
    OP_ATTR_TEXT = 5
    OP_ATTR_RAW = 6
    # REGEX
    OP_REGEX = 7
    OP_REGEX_ALL = 8
    OP_REGEX_SUB = 9
    # STRINGS
    OP_STRING_TRIM = 10
    OP_STRING_L_TRIM = 11
    OP_STRING_R_TRIM = 12
    OP_STRING_REPLACE = 13
    OP_STRING_FORMAT = 14
    OP_STRING_SPLIT = 15
    # ARRAY
    OP_INDEX = 16
    OP_FIRST = 17
    OP_LAST = 18
    OP_LIMIT = 19
    OP_JOIN = 20
    # ANY
    OP_COMMENT = 21
    OP_TRANSLATE_DEFAULT_CODE = 22  # wrap try/catch mark
    OP_TRANSLATE_CODE = 23
    OP_NEW_LINE = 24
    OP_CUSTOM_FORMATTER = 25
    # VALIDATORS
    OP_ASSERT = 26
    OP_ASSERT_CONTAINS = 27
    OP_ASSERT_STARTSWITH = 28
    OP_ASSERT_ENDSWITH = 29
    OP_ASSERT_MATCH = 30
    OP_ASSERT_CSS = 31
    OP_ASSERT_XPATH = 32
    # declare return statements for translator
    OP_NO_RET = 33
    OP_RET = 34

    @classmethod
    def tokens_selector_all(cls):
        return (
            TokenType.OP_CSS,
            TokenType.OP_XPATH,
            TokenType.OP_CSS_ALL,
            TokenType.OP_XPATH_ALL,
        )

    @classmethod
    def tokens_selector_css(cls):
        return (
            TokenType.OP_CSS,
            TokenType.OP_CSS_ALL,
            TokenType.OP_ASSERT_CSS
        )

    @classmethod
    def tokens_selector_xpath(cls):
        return (
            TokenType.OP_XPATH,
            TokenType.OP_XPATH_ALL,
            TokenType.OP_ASSERT_XPATH
        )

    @classmethod
    def tokens_selector_fetch_one(cls):
        return TokenType.OP_CSS, TokenType.OP_XPATH

    @classmethod
    def tokens_selector_fetch_all(cls):
        return TokenType.OP_CSS_ALL, TokenType.OP_XPATH_ALL

    @classmethod
    def tokens_selector_extract(cls):
        return TokenType.OP_ATTR, TokenType.OP_ATTR_TEXT, TokenType.OP_ATTR_RAW

    @classmethod
    def tokens_regex(cls):
        return (
            TokenType.OP_REGEX,
            TokenType.OP_REGEX_ALL,
            TokenType.OP_REGEX_SUB,
        )

    @classmethod
    def tokens_string(cls):
        return (
            TokenType.OP_STRING_FORMAT,
            TokenType.OP_STRING_REPLACE,
            TokenType.OP_STRING_SPLIT,
            TokenType.OP_STRING_L_TRIM,
            TokenType.OP_STRING_R_TRIM,
            TokenType.OP_STRING_TRIM,
        )

    @classmethod
    def tokens_array(cls):
        return (
            TokenType.OP_INDEX,
            TokenType.OP_FIRST,
            TokenType.OP_LAST,
            TokenType.OP_LIMIT,
            TokenType.OP_JOIN,
        )

    @classmethod
    def tokens_asserts(cls):
        return (
            TokenType.OP_ASSERT,
            TokenType.OP_ASSERT_STARTSWITH,
            TokenType.OP_ASSERT_ENDSWITH,
            TokenType.OP_ASSERT_CSS,
            TokenType.OP_ASSERT_XPATH,
            TokenType.OP_ASSERT_CONTAINS,
            TokenType.OP_ASSERT_MATCH,
        )

    @classmethod
    def token_fluent_optimization(cls):
        return (
            TokenType.OP_CSS,
            TokenType.OP_XPATH,
            TokenType.OP_XPATH_ALL,
            TokenType.OP_CSS_ALL,
            TokenType.OP_INDEX,
            TokenType.OP_ATTR,
            TokenType.OP_ATTR_RAW,
            TokenType.OP_ATTR_TEXT,
        )


class Token:
    def __init__(
        self,
        token_type: TokenType,
        args: Optional[tuple[str, ...]],
        line: int,
        pos: int,
        code: str,
    ):
        """Token model

        :param token_type: token type, enum
        :param args: command arguments. tuple of strings
        :param line: line num
        :param pos: line position
        :param code: raw line command
        """
        self.token_type = token_type
        self._args = args
        self.line = line
        self.pos = pos
        self._code = code

    @property
    def id(self):
        return hash(self)

    def __hash__(self):
        hash_ = hash(self._code) + hash(self.values) + self.line + self.pos
        # hash should be positive for generate variables names
        return hash_ * -1 if hash_ < 0 else hash_

    @property
    def raw_code(self):
        return self._code

    @property
    def values(self) -> tuple[str, ...]:
        """remove quotes matched groups `'"`"""
        if not self._args:
            return ()
        return self._args

    @values.setter
    def values(self, value: tuple[str, ...]):
        self._args = value

    def __repr__(self):
        return f"{self.line}::{self.pos}: val_{self.id} = {self.token_type}, args={self.values}"


TT_COMMENT = "//"
TT_NEW_LINE = "\n"


class VariableState(Enum):
    """variable states in Syntax analyzer and codegen representation"""

    SELECTOR = 0
    SELECTOR_ARRAY = 1  # dynamic list/vector of node elements
    TEXT = 2
    ARRAY = 3  # dynamic list/vector of string types
    NO_RETURN = 4  # return nothing


@dataclass(repr=False)
class Node:
    """node representation like. AST structure have linked list struct"""

    num: int
    count: int
    token: Token
    var_state: VariableState
    ast_tree: dict[int, "Node"]
    prev: Optional[int]
    next: Optional[int]

    def __repr__(self):
        return f"Node_{self.num}_{self.count}(prev={self.prev}, next={self.next}, var={self.var_state}, token={self.token})"

    @property
    def id(self) -> Optional[int]:
        # exclude enumerate assert tokens
        if (
            self.token.token_type not in TokenType.tokens_asserts()
            and self.token.token_type != TokenType.OP_TRANSLATE_DEFAULT_CODE
        ):
            return self.num

        prev_node = self.prev_node
        # scan non-assert token and return id
        while True:
            if prev_node is None:
                return None

            elif prev_node.token.token_type in TokenType.tokens_asserts():
                prev_node = prev_node.prev_node
                continue
            else:
                return prev_node.id

    @property
    def return_arg_type(self) -> VariableState:
        # return variable state of return value
        node = self.ast_tree[self.count-1]
        if node.token.token_type == TokenType.OP_NO_RET:
            return VariableState.NO_RETURN
        return node.var_state

    @property
    def next_node(self) -> Optional["Node"]:
        if self.next is not None:
            return self.ast_tree[self.next]
        return None

    @property
    def prev_node(self) -> Optional["Node"]:
        if self.prev is not None:
            return self.ast_tree[self.prev]
        return None
