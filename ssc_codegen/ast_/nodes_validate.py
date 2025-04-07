from dataclasses import dataclass
from typing import TypedDict, ClassVar, Sequence

from ssc_codegen.ast_.base import BaseAstNode
from ssc_codegen.tokens import TokenType, VariableType

T_EQ_OR_NE_ARG = str | int | float | bool

KW_ASSERT_EQ_OR_NE = TypedDict(
    "KW_ASSERT_EQ_OR_NE", {"item": T_EQ_OR_NE_ARG, "msg": str}
)
ARGS_ASSERT_EQ = tuple[T_EQ_OR_NE_ARG, str]


@dataclass(kw_only=True)
class ExprIsEqual(BaseAstNode[KW_ASSERT_EQ_OR_NE, ARGS_ASSERT_EQ]):
    kind: ClassVar[TokenType] = TokenType.IS_EQUAL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY

    exclude_types: Sequence[VariableType] = (
        VariableType.DOCUMENT,
        VariableType.LIST_DOCUMENT,
        VariableType.JSON,
        VariableType.NESTED,
    )


@dataclass(kw_only=True)
class ExprIsNotEqual(BaseAstNode[KW_ASSERT_EQ_OR_NE, ARGS_ASSERT_EQ]):
    kind: ClassVar[TokenType] = TokenType.IS_NOT_EQUAL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    exclude_types: Sequence[VariableType] = (
        VariableType.DOCUMENT,
        VariableType.LIST_DOCUMENT,
        VariableType.JSON,
        VariableType.NESTED,
    )


T_IS_IN_ARG = str | int | float
KW_ASSERT_IN = TypedDict("KW_ASSERT_IN", {"item": T_EQ_OR_NE_ARG, "msg": str})
ARGS_ASSERT_IN = tuple[T_EQ_OR_NE_ARG, str]


@dataclass(kw_only=True)
class ExprIsContains(BaseAstNode[KW_ASSERT_IN, ARGS_ASSERT_IN]):
    kind: ClassVar[TokenType] = TokenType.IS_CONTAINS
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.ANY
    exclude_types: Sequence[VariableType] = (VariableType.LIST_DOCUMENT,)


KW_IS_REGEX = TypedDict(
    "KW_IS_REGEX", {"pattern": str, "ignore_case": bool, "msg": str}
)
ARGS_IS_REGEX = tuple[str, bool, str]


@dataclass(kw_only=True)
class ExprStringIsRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    kind: ClassVar[TokenType] = TokenType.IS_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringAnyRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    kind: ClassVar[TokenType] = TokenType.ANY_LIST_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringAllRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    kind: ClassVar[TokenType] = TokenType.ALL_LIST_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_IS_SELECT = TypedDict("KW_IS_SELECT", {"query": str, "msg": str})
ARGS_IS_SELECT = tuple[str, str]


@dataclass(kw_only=True)
class ExprIsCss(BaseAstNode[KW_IS_SELECT, ARGS_IS_SELECT]):
    kind: ClassVar[TokenType] = TokenType.IS_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprIsXpath(BaseAstNode[KW_IS_SELECT, ARGS_IS_SELECT]):
    kind: ClassVar[TokenType] = TokenType.IS_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_HAS_ATTR = TypedDict("KW_HAS_ATTR", {"key": str, "msg": str})
ARGS_HAS_ATTR = tuple[str, str]


@dataclass(kw_only=True)
class ExprHasAttr(BaseAstNode[KW_HAS_ATTR, ARGS_HAS_ATTR]):
    kind: ClassVar[TokenType] = TokenType.HAS_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprListHasAttr(BaseAstNode[KW_HAS_ATTR, ARGS_HAS_ATTR]):
    kind: ClassVar[TokenType] = TokenType.HAS_LIST_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


# TODO:
# ExprIsBiggerThan
# ExprIsBiggerOrEq
# ExprIsLessThan
# ExprIsLessOrEq
