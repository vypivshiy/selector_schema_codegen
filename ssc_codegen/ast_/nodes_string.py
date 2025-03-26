from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode
from ssc_codegen.tokens import TokenType, VariableType

KW_STR_TRIM = TypedDict("KW_STR_TRIM", {"substr": str})


@dataclass(kw_only=True)
class ExprStringTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_TRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringLeftTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_LTRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRightTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RTRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_TRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringLeftTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_LTRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRightTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RTRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_FMT = TypedDict("KW_STR_FMT", {"fmt": str})


@dataclass(kw_only=True)
class ExprStringFormat(BaseAstNode[KW_STR_FMT, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_FORMAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringFormat(BaseAstNode[KW_STR_FMT, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_FORMAT
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_SEP = TypedDict("KW_STR_SEP", {"sep": str})


@dataclass(kw_only=True)
class ExprStringSplit(BaseAstNode[KW_STR_SEP, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_SPLIT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_REPL = TypedDict("KW_STR_REPL", {"old": str, "new": str})


@dataclass(kw_only=True)
class ExprStringReplace(BaseAstNode[KW_STR_REPL, tuple[str, str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_REPLACE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringReplace(BaseAstNode[KW_STR_REPL, tuple[str, str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_REPLACE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RE = TypedDict(
    "KW_STR_RE", {"pattern": str, "group": int, "ignore_case": bool}
)


@dataclass(kw_only=True)
class ExprStringRegex(BaseAstNode[KW_STR_RE, tuple[str, int, bool]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


KW_STR_RE_ALL = TypedDict(
    "KW_STR_RE_ALL", {"pattern": str, "ignore_case": bool}
)


@dataclass(kw_only=True)
class ExprStringRegexAll(BaseAstNode[KW_STR_RE_ALL, tuple[str, bool]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_ALL
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RE_SUB = TypedDict("KW_STR_RE_SUB", {"pattern": str, "repl": str})


@dataclass(kw_only=True)
class ExprStringRegexSub(BaseAstNode[KW_STR_RE_SUB, tuple[str, str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_SUB
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringRegexSub(BaseAstNode[KW_STR_RE_SUB, tuple[str, str]]):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_REGEX_SUB
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RM_PREFIX_OR_SUFFIX = TypedDict(
    "KW_STR_RM_PREFIX_OR_SUFFIX", {"substr": str}
)
ARGS_STR_RM_PREFIX_OR_SUFFIX = tuple[str]


@dataclass(kw_only=True)
class ExprStringRmPrefix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_PREFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRmSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_SUFFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRmPrefixAndSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_PREFIX_AND_SUFFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringRmPrefix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_PREFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRmSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_SUFFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRmPrefixAndSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_PREFIX_AND_SUFFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
