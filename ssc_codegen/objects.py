from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple, Any, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from ssc_codegen.document import Document


class VariableState(IntEnum):
    DOCUMENT = 0
    LIST_DOCUMENT = 1
    STRING = 2
    LIST_STRING = 3
    NONE = 4
    DOCSTRING = 5  # ///


class TokenType(IntEnum):
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
    OP_JOIN = 20
    # ANY
    OP_DEFAULT = 22  # wrap try/catch mark
    # VALIDATORS
    OP_ASSERT_EQUAL = 26
    OP_ASSERT_CONTAINS = 27
    OP_ASSERT_RE_MATCH = 30
    OP_ASSERT_CSS = 31
    OP_ASSERT_XPATH = 32
    # UTILS HELPER TOKENS
    OP_DOCSTRING = 100
    OP_FUNCTION_HEAD = 101
    OP_INIT = 103  # for init first var
    OP_NO_RET = 104  # for validators: try/catch wraps
    OP_RET = 105
    # try/except or try/catch tokens
    OP_DEFAULT_START = 106
    OP_DEFAULT_END = 107
    # tokens for build struct classes
    OP_STRUCT = 200
    OP_STRUCT_INIT = 201
    # pre-validate method before init
    OP_STRUCT_VALIDATOR = 202
    # private parse method
    # OP_STRUCT_METHOD = 203
    # public parse method. should be allowed override
    OP_STRUCT_PARSE = 204


class Expression(NamedTuple):
    num: int
    variable_state: VariableState
    token_type: TokenType
    arguments: tuple[Any, ...]
    message: Optional[str] = None  # FOR ASSERT


@dataclass(repr=False)
class Node:
    """AST node representation"""

    num: int
    count: int
    expression: Expression
    ast_tree: dict[int, "Node"]
    prev: Optional[int]
    next: Optional[int]

    @property
    def var_state(self):
        return self.expression.variable_state

    @property
    def token(self) -> TokenType:
        return self.expression.token_type

    def __repr__(self):
        return (f"Node_[{self.num},{self.count}](prev={self.prev}, next={self.next}, var_state={self.var_state.name!r}, "
                f"token={self.token.name!r})")

    @property
    def id(self) -> Optional[int]:
        # exclude enumerate assert, system tokens
        if (
                self.token not in (TokenType.OP_ASSERT_CSS,
                                   TokenType.OP_ASSERT_XPATH,
                                   TokenType.OP_ASSERT_CONTAINS,
                                   TokenType.OP_ASSERT_EQUAL,
                                   TokenType.OP_ASSERT_RE_MATCH,
                                   # SYSTEM
                                   TokenType.OP_FUNCTION_HEAD,
                                   TokenType.OP_DEFAULT_START,
                                   TokenType.OP_DEFAULT_END,
                                   TokenType.OP_RET,
                                   TokenType.OP_NO_RET
                                   )
        ):
            return self.num

        prev_node = self.prev_node
        # scan non-assert token and return id
        while True:
            if prev_node is None:
                return None

            elif prev_node.token in ():
                prev_node = prev_node.prev_node
                continue
            else:
                return prev_node.id

    @property
    def return_arg_type(self) -> VariableState:
        # return variable state of return value
        node = self.ast_tree[self.count - 1]
        # TODO refactoring
        if node.token == TokenType.OP_RET:
            node = node.prev_node
        elif node.token == TokenType.OP_NO_RET:
            return VariableState.NONE

        # OP_DEFAULT_END, OP_RET
        if node.token == TokenType.OP_DEFAULT_END:
            node = node.prev_node.prev_node

        if node.var_state == VariableState.DOCUMENT:
            return VariableState.STRING
        elif node.var_state == VariableState.LIST_DOCUMENT:
            return VariableState.LIST_STRING

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


# CONSTANTS EXPR
EXPR_INIT = Expression(
    -1,
    VariableState.NONE,
    TokenType.OP_INIT,
    arguments=()
)

EXPR_RET = Expression(-1,
                      VariableState.NONE,
                      TokenType.OP_RET,
                      arguments=(), )

EXPR_NO_RET = Expression(-1,
                         VariableState.NONE,
                         TokenType.OP_NO_RET,
                         arguments=())


def create_default_expr(doc: "Document") -> "Document":
    default_expr = doc.pop(0)
    value = default_expr.arguments[0]
    start_default_expr = Expression(
        -1,
        VariableState.NONE,
        TokenType.OP_DEFAULT_START,
        arguments=()
    )
    end_default_expr = Expression(
        -1,
        VariableState.NONE,
        TokenType.OP_DEFAULT_END,
        arguments=(value,)
    )
    doc.insert(0, start_default_expr)
    doc.append(end_default_expr)
    return doc
