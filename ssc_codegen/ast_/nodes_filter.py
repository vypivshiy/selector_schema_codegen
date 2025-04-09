from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType


# TODO: static analyzer for filter operations
# TODO: implement operators for DOCUMENT, INT, FLOAT
@dataclass(kw_only=True)
class Filter(BaseAstNode):
    kind: ClassVar[TokenType] = TokenType.FILTER
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterOr(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_OR
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    # TODO: typing body accept Filter-like nodes


@dataclass(kw_only=True)
class FilterAnd(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_AND
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    # TODO: typing body accept Filter-like nodes


@dataclass(kw_only=True)
class FilterNot(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_NOT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    # TODO: typing body accept Filter-like nodes


KW_STR_IN = TypedDict("KW_STR_IN", {"substr": str})
ARGS_STR_IN = tuple[str]

KW_STR_STARTS_OR_ENDS = TypedDict(
    "KW_STR_STARTS_OR_ENDS", {"substr": tuple[str, ...]}
)
ARGS_STR_STARTS_OR_ENDS = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterStrIn(BaseAstNode[KW_STR_IN, ARGS_STR_IN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_IN
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrStarts(
    BaseAstNode[KW_STR_STARTS_OR_ENDS, ARGS_STR_STARTS_OR_ENDS]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_STARTS
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrEnds(
    BaseAstNode[KW_STR_STARTS_OR_ENDS, ARGS_STR_STARTS_OR_ENDS]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_ENDS
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


KW_STR_RE = TypedDict("KW_STR_RE", {"pattern": str, "ignore_case": bool})
ARGS_STR_RE = tuple[str, bool]


@dataclass(kw_only=True)
class FilterStrRe(BaseAstNode[KW_STR_RE, ARGS_STR_RE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_RE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


# TODO: provide API for int, float, etc
KW_STR_EQ_OR_NE = TypedDict("KW_STR_EQ_OR_NE", {"value": str})
ARGS_STR_EQ_OR_NE = tuple[str]


@dataclass(kw_only=True)
class FilterEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterNotEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprFilter(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_FILTER
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    # TODO: typing body accept Filter-like nodes
