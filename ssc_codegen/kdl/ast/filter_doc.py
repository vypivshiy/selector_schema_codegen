"""Filter AST nodes (DOCUMENT pipeline)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class FilterDoc(BaseAstNode):
    """
    Filter-блок для документов.

    DSL: filter { css ".active"; attr "href"; contains "example" }
    Принимает LIST_DOCUMENT, возвращает LIST_DOCUMENT.
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC
    accept_type: VariableType = field(default=VariableType.LIST_DOCUMENT)
    ret_type: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass(kw_only=True)
class FilterDocSelect(BaseAstNode):
    """
    Фильтр: наличие элемента по CSS/XPath.

    DSL: css ".active" / xpath "//a[@href]"
    kwargs: mode ("css"|"xpath"), query (str)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_SELECT
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class FilterDocAttr(BaseAstNode):
    """
    Фильтр по значению атрибута.

    DSL: attr "href" eq "https://..." / attr "class" contains "active"
    kwargs: attr (str), op (FilterStringOp|FilterCompareOp), value (str)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class FilterDocText(BaseAstNode):
    """
    Фильтр по текстовому содержимому.

    DSL: has_text "..." / is_regex_text #"..."#
    kwargs: mode ("has_text"|"is_regex_text"), value (str)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_TEXT
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class FilterDocRaw(BaseAstNode):
    """
    Фильтр по raw HTML содержимому.

    DSL: has_raw "..." / is_regex_raw #"..."#
    kwargs: mode ("has_raw"|"is_regex_raw"), value (str)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_RAW
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class FilterDocHasAttr(BaseAstNode):
    """
    Фильтр: наличие атрибута у элемента.

    DSL: has-attr "href"
    kwargs: attr (str)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_ATTR
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)