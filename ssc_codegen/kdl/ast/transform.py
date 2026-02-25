"""Transform AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Transform(BaseAstNode):
    """
    Кастомная трансформация (вызов пользовательской функции).

    DSL: transform "my_func"
    kwargs: name (str) — имя функции из TransformImports.
    """
    kind: ClassVar[TokenType] = TokenType.TRANSFORM
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class TransformImports(BaseAstNode):
    """
    Импорты кастомных трансформаций.

    DSL: transform-imports { ... }
    body — список импортируемых функций/модулей.
    """
    kind: ClassVar[TokenType] = TokenType.TRANSFORM_IMPORTS
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)