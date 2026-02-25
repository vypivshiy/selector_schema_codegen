"""Control flow AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsDefault
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Default(BaseAstNode[KwargsDefault, tuple]):
    """
    Значение по умолчанию (?? оператор / Nullish coalescing).

    DSL:
        ?? 0          → int
        ?? 0.0        → float
        ?? "none"     → str
        ?? #false     → bool
        ?? #null      → null
        ?? {}         → пустой список

    kwargs: value — само значение (Python-тип)
    ret_type определяется автоматически из типа value.
    """
    kind: ClassVar[TokenType] = TokenType.DEFAULT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)

    def __post_init__(self) -> None:
        super().__post_init__()
        value = self.kwargs.get("value")
        if value is None:
            self.ret_type = VariableType.NULL
        elif isinstance(value, bool):
            # bool перед int — bool является подклассом int в Python
            self.ret_type = VariableType.BOOL
        elif isinstance(value, int):
            self.ret_type = VariableType.INT
        elif isinstance(value, float):
            self.ret_type = VariableType.FLOAT
        elif isinstance(value, str):
            self.ret_type = VariableType.STRING
        elif isinstance(value, list):
            self.ret_type = VariableType.LIST_STRING


@dataclass(kw_only=True)
class DefaultStart(BaseAstNode[KwargsDefault, tuple]):
    """
    Начало блока default (для блочного синтаксиса).
    Используется когда default-значение требует вычисления (не литерал).
    """
    kind: ClassVar[TokenType] = TokenType.DEFAULT_START
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class DefaultEnd(BaseAstNode[KwargsDefault, tuple]):
    """Конец блока default."""
    kind: ClassVar[TokenType] = TokenType.DEFAULT_END
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class Return(BaseAstNode):
    """
    Return expression.
    Явный выход из пайплайна поля с конкретным значением.
    kwargs: value? — опциональное явное значение.
    """
    kind: ClassVar[TokenType] = TokenType.RETURN
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)