"""Data extraction AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsExtract
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Extract(BaseAstNode[KwargsExtract, tuple[str, str]]):
    """
    Универсальное извлечение данных из элемента.

    DSL:
        text              → mode="text"
        attr "href"       → mode="attr", key="href"
        raw               → mode="raw"
        attrs-map         → mode="attrs_map"

    Псевдоэлементы parsel-синтаксиса (::text, ::attr(src)) разворачиваются
    в Select + Extract на уровне AST-билдера.

    kwargs: mode, key (опционально для attr)

    ret_type:
        text / attr / raw → STRING
        attrs_map         → остаётся ANY (dict-подобный)
    """
    kind: ClassVar[TokenType] = TokenType.EXTRACT
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.STRING)