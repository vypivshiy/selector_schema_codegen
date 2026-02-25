"""JSON AST nodes.

Два уровня:
  - JsonDef / JsonDefField — top-level определение маппинга (json Author { ... })
  - JsonStruct / JsonField  — JSON-структура как результат поля (output)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsJsonDef, KwargsJsonDefField, KwargsField
from ssc_codegen.kdl.tokens import TokenType, VariableType


# ── Top-level JSON mapping definition ────────────────────────────────────────

@dataclass(kw_only=True)
class JsonDef(BaseAstNode[KwargsJsonDef, tuple[str, bool]]):
    """
    Определение JSON-маппинга на уровне модуля.

    DSL:
        json Author { name str; slug str }
        json Quote array=#true { tags str {}; author Author; text str|null }

    kwargs:
        name     — идентификатор маппинга
        is_array — True если array=#true (список объектов)

    body — список JsonDefField.
    """
    kind: ClassVar[TokenType] = TokenType.JSON_DEF
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class JsonDefField(BaseAstNode[KwargsJsonDefField, tuple[str, str]]):
    """
    Поле JSON-маппинга.

    DSL:
        name str          → простой примитив
        tags str {}       → массив примитивов (body пустой блок)
        author Author     → ссылка на другой JsonDef
        text str|null     → опциональное поле

    kwargs:
        name        — имя поля
        type_name   — "str" | "int" | "float" | "bool" | "null" | "any" | "<JsonDefName>"
        is_optional — True если тип содержит "|null"
        is_array    — True если поле является массивом (body присутствует)
        ref_name    — имя другого JsonDef (если type_name — не примитив)
    """
    kind: ClassVar[TokenType] = TokenType.JSON_DEF_FIELD
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)
    body: list = field(default_factory=list, repr=False)


# ── JSON output structure (результат поля struct) ────────────────────────────

@dataclass(kw_only=True)
class JsonStruct(BaseAstNode):
    """
    JSON-структура как результирующий тип поля.
    Используется внутри StructField когда результат — вложенный JSON-объект.
    """
    kind: ClassVar[TokenType] = TokenType.JSON_STRUCT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class JsonField(BaseAstNode[KwargsField, tuple[str]]):
    """Поле JSON-структуры (output)."""
    kind: ClassVar[TokenType] = TokenType.JSON_FIELD
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)
    body: list = field(default_factory=list, repr=False)