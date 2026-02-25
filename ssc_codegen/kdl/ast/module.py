"""Module-level AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from ssc_codegen.kdl.tokens import TokenType, VariableType
from .types import KwargsDocstirng

@dataclass(kw_only=True)
class Module(BaseAstNode):
    """Корневой узел модуля. Содержит все top-level определения."""
    kind: ClassVar[TokenType] = TokenType.MODULE
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class Define(BaseAstNode):
    """
    Константа / text substitution.
    DSL: define NAME="value" / define RE_PAT=#"..."#
    Заменяет устаревший `const`.
    """
    kind: ClassVar[TokenType] = TokenType.DEFINE
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class Docstring(BaseAstNode[KwargsDocstirng, tuple[str]]):
    """Документация (doc \"\"\"...\"\"\")."""
    kind: ClassVar[TokenType] = TokenType.DOCSTRING
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)
    body: list = field(default_factory=list, repr=False)


@dataclass(kw_only=True)
class Imports(BaseAstNode):
    """Импорты модуля."""
    kind: ClassVar[TokenType] = TokenType.IMPORTS
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class Utilities(BaseAstNode):
    """Utility-функции (хелперы для codegen)."""
    kind: ClassVar[TokenType] = TokenType.UTILITIES
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)