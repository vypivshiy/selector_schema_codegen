"""Array operation AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Index(BaseAstNode):
    """
    Получение элемента по индексу.

    DSL:
        index 0      → первый элемент
        first        → index 0 (shortcut)
        last         → index -1 (shortcut)

    kwargs: i (int) — индекс (отрицательный — с конца)

    Принимает LIST_*, возвращает соответствующий скалярный тип.
    Конкретный тип уточняется при построении AST (LIST_STRING → STRING и т.п.).
    """
    kind: ClassVar[TokenType] = TokenType.INDEX
    accept_type: VariableType = field(default=VariableType.LIST_ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class Len(BaseAstNode):
    """
    Длина массива.

    DSL: to-len
    Принимает любой список, возвращает INT.
    """
    kind: ClassVar[TokenType] = TokenType.LEN
    accept_type: VariableType = field(default=VariableType.LIST_ANY)
    ret_type: VariableType = field(default=VariableType.INT)


@dataclass(kw_only=True)
class Unique(BaseAstNode):
    """
    Уникальные значения (дубликаты убираются, порядок не гарантирован).

    DSL: unique
    Сохраняет тип списка: LIST_STRING → LIST_STRING.
    """
    kind: ClassVar[TokenType] = TokenType.UNIQUE
    accept_type: VariableType = field(default=VariableType.LIST_STRING)
    ret_type: VariableType = field(default=VariableType.LIST_STRING)