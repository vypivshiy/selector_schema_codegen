"""TypeDef AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsTypeDefField, KwargsTypedef
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class TypeDef(BaseAstNode[KwargsTypedef, tuple[bool]]):
    """
    Определение пользовательского типа (type alias / enum).
    kwargs: name (str)
    body — список TypeDefField.
    """
    kind: ClassVar[TokenType] = TokenType.TYPEDEF
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class TypeDefField(BaseAstNode[KwargsTypeDefField, tuple[str, str]]):
    """
    Поле определения типа.
    kwargs: name (str)
    body — список pipeline-операций для этого поля.
    """
    kind: ClassVar[TokenType] = TokenType.TYPEDEF_FIELD
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)
    body: list = field(default_factory=list, repr=False)