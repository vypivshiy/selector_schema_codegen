from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType

KW_EXPR_INDEX = TypedDict("KW_EXPR_INDEX", {"index": int})
ARGS_EXPR_INDEX = tuple[int]


@dataclass(kw_only=True)
class ExprIndex(BaseAstNode[KW_EXPR_INDEX, ARGS_EXPR_INDEX]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_ANY_INDEX
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.ANY


KW_EXPR_JOIN = TypedDict("KW_EXPR_JOIN", {"sep": str})
ARGS_EXPR_JOIN = tuple[str]


@dataclass(kw_only=True)
class ExprListStringJoin(BaseAstNode[KW_EXPR_JOIN, ARGS_EXPR_JOIN]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_JOIN
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprToListLength(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_LEN
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.INT
