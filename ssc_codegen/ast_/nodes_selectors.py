from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.tokens import TokenType, VariableType
from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS

KW_EXPR_SELECTOR_LIKE = TypedDict("KW_EXPR_SELECTOR_LIKE", {"query": str})
ARGS_EXPR_SELECTOR_LIKE = tuple[str]


@dataclass(kw_only=True)
class ExprCss(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    kind: ClassVar[TokenType] = TokenType.EXPR_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprCssAll(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    kind: ClassVar[TokenType] = TokenType.EXPR_CSS_ALL
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class ExprXpath(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprXpathAll(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH_ALL
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


KW_EXPR_ATTR = TypedDict("KW_EXPR_ATTR", {"key": str})
ARGS_EXPR_ATTR = tuple[str]


@dataclass(kw_only=True)
class ExprGetHtmlAttr(BaseAstNode[KW_EXPR_ATTR, ARGS_EXPR_ATTR]):
    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlAttrAll(BaseAstNode[KW_EXPR_ATTR, ARGS_EXPR_ATTR]):
    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprGetHtmlText(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlTextAll(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprGetHtmlRaw(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlRawAll(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_RAW_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING
