"""Selector AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsSelect
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Select(BaseAstNode[KwargsSelect, tuple[str, str, bool]]):
    """
    Универсальный селектор CSS/XPath.

    DSL:
        css ".thumbnail"          → mode="css",  is_all=False
        css-all ".col-lg-3"       → mode="css",  is_all=True
        xpath "//a"               → mode="xpath", is_all=False
        xpath-all "//tr"          → mode="xpath", is_all=True

    Псевдоэлементы (::text, ::attr(...)) разворачиваются в Select + Extract
    на уровне AST-билдера.

    kwargs: mode, query, is_all
    """
    kind: ClassVar[TokenType] = TokenType.SELECT
    # одиночный → DOCUMENT, all → LIST_DOCUMENT (уточняется при построении)
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class Remove(BaseAstNode[KwargsSelect, tuple[str, str, bool]]):
    """
    Удаление элементов из документа.

    DSL: rm-css ".ads" / rm-xpath "//script"
    kwargs: mode, query, is_all
    Не меняет тип: DOCUMENT → DOCUMENT.
    """
    kind: ClassVar[TokenType] = TokenType.REMOVE
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)