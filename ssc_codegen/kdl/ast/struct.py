"""Struct-level AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsStruct, KwargsTypeDefField
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Struct(BaseAstNode[KwargsStruct, tuple[str, str, str]]):
    """
    Парсер структуры (схемы).
    kwargs: name, struct_type ("item"|"list"|"dict"|"table"), docstring?
    """
    kind: ClassVar[TokenType] = TokenType.STRUCT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class StructField(BaseAstNode[KwargsTypeDefField, tuple[str]]):
    """
    Поле структуры.
    body — пайплайн операций (Select → Extract → StringOp → ...).
    """
    kind: ClassVar[TokenType] = TokenType.STRUCT_FIELD
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class StructSplit(BaseAstNode):
    """
    __SPLIT_DOC__ эквивалент.
    DSL: -split-doc { css-all "..." }
    body — пайплайн, возвращающий LIST_DOCUMENT.
    """
    kind: ClassVar[TokenType] = TokenType.STRUCT_SPLIT
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass(kw_only=True)
class StructPreValidate(BaseAstNode):
    """
    __PRE_VALIDATE__ эквивалент.
    DSL: -pre-validate { assert { ... } }
    Не модифицирует документ, только валидирует.
    """
    kind: ClassVar[TokenType] = TokenType.STRUCT_PRE_VALIDATE
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class StructParse(BaseAstNode):
    """Метод parse() схемы."""
    kind: ClassVar[TokenType] = TokenType.STRUCT_PARSE
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class StructInit(BaseAstNode):
    """__init__() метод схемы."""
    kind: ClassVar[TokenType] = TokenType.STRUCT_INIT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class StructNested(BaseAstNode[KwargsTypeDefField, tuple[str]]):
    """
    Вложенная схема (ссылка по имени).
    DSL: books { Book }
    kwargs: name — имя структуры-цели.
    """
    kind: ClassVar[TokenType] = TokenType.STRUCT_NESTED
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.NESTED)