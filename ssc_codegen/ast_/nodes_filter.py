from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType


# TODO: static analyzer for filter operations
# TODO: implement operators for DOCUMENT, INT, FLOAT


@dataclass(kw_only=True)
class FilterOr(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_OR
    # cast for reuse in Elements filters
    # real accept: VariableType.STRING, VariableType.DOCUMENT
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    # TODO: typing body accept Filter-like nodes


@dataclass(kw_only=True)
class FilterAnd(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_AND
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    # TODO: typing body accept Filter-like nodes


@dataclass(kw_only=True)
class FilterNot(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.FILTER_NOT
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    # TODO: typing body accept Filter-like nodes


KW_STR_IN = TypedDict("KW_STR_IN", {"substr": tuple[str, ...]})
ARGS_STR_IN = tuple[tuple[str, ...]]

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


KW_STR_LEN = TypedDict("KW_STR_LEN", {"length": int})
ARGS_STR_LEN = tuple[int]


@dataclass(kw_only=True)
class FilterStrLenEq(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenNe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_NE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenLt(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_LT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenLe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_LE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenGt(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_GT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenGe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_GE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


# TODO: provide API for int, float, etc
KW_STR_EQ_OR_NE = TypedDict("KW_STR_EQ_OR_NE", {"values": tuple[str, ...]})
ARGS_STR_EQ_OR_NE = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterNotEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_NE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprFilter(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_FILTER
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    # TODO: typing body accept Filter-like nodes


# Elements filters
@dataclass(kw_only=True)
class ExprDocumentFilter(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_DOC_FILTER
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


KW_FILTER_CSS_OR_XPATH = TypedDict("KW_FILTER_CSS", {"query": str})
ARGS_FILTER_CSS_OR_XPATH = tuple[str]


@dataclass(kw_only=True)
class FilterDocCss(
    BaseAstNode[KW_FILTER_CSS_OR_XPATH, ARGS_FILTER_CSS_OR_XPATH]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocXpath(
    BaseAstNode[KW_FILTER_CSS_OR_XPATH, ARGS_FILTER_CSS_OR_XPATH]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_HAS_TEXT = TypedDict(
    "KW_FILTER_HAS_TEXT", {"values": tuple[str, ...]}
)
ARGS_FILTER_HAS_TEXT = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocHasText(BaseAstNode[KW_FILTER_HAS_TEXT, ARGS_FILTER_HAS_TEXT]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocHasRaw(BaseAstNode[KW_FILTER_HAS_TEXT, ARGS_FILTER_HAS_TEXT]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_HAS_ATTR = TypedDict("KW_FILTER_HAS_ATTR", {"keys": tuple[str, ...]})
ARGS_FILTER_HAS_ATTR = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocHasAttr(BaseAstNode[KW_FILTER_HAS_ATTR, ARGS_FILTER_HAS_ATTR]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_ATTR = TypedDict(
    "KW_FILTER_ATTR", {"key": str, "values": tuple[str, ...]}
)
ARGS_FILTER_ATTR = tuple[str, tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocAttrEqual(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_EQ
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrStarts(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_STARTS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrEnds(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_ENDS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrContains(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_CONTAINS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_ATTR_RE = TypedDict(
    "KW_FILTER_ATTR", {"key": str, "pattern": str, "ignore_case": bool}
)
ARGS_FILTER_ATTR_RE = tuple[str, str, bool]


@dataclass(kw_only=True)
class FilterDocAttrRegex(BaseAstNode[KW_FILTER_ATTR_RE, ARGS_FILTER_ATTR_RE]):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_RE_MATCH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_IS_REGEX = TypedDict(
    "KW_FILTER_IS_REGEX", {"pattern": str, "ignore_case": bool}
)
ARGS_FILTER_IS_REGEX = tuple[str, bool]


@dataclass(kw_only=True)
class FilterDocIsRegexText(
    BaseAstNode[KW_FILTER_IS_REGEX, ARGS_FILTER_IS_REGEX]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_IS_RE_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocIsRegexRaw(
    BaseAstNode[KW_FILTER_IS_REGEX, ARGS_FILTER_IS_REGEX]
):
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_IS_RE_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
