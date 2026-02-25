"""Logic operator AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class LogicAnd(BaseAstNode):
    """
    Логическое И — все условия должны выполняться.
    Используется неявно: несколько узлов в блоке filter/assert объединяются AND.
    """
    kind: ClassVar[TokenType] = TokenType.LOGIC_AND
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class LogicOr(BaseAstNode):
    """
    Логическое ИЛИ — достаточно одного выполненного условия.
    Используется когда FilterStr/FilterCmp получают несколько values.
    """
    kind: ClassVar[TokenType] = TokenType.LOGIC_OR
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class LogicNot(BaseAstNode):
    """
    Инверсия условия.

    DSL:
        not { css "p[unreal-attr]" }
        not { ends ".webp" }

    body — список узлов-условий (инвертируется результат всего блока).
    """
    kind: ClassVar[TokenType] = TokenType.LOGIC_NOT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)