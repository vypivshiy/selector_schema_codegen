"""Cast operation AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsCast
from ssc_codegen.kdl.tokens import TokenType, VariableType

_CAST_TYPE_MAP: dict[str, VariableType] = {
    "int":        VariableType.INT,
    "float":      VariableType.FLOAT,
    "bool":       VariableType.BOOL,
    "list_int":   VariableType.LIST_INT,
    "list_float": VariableType.LIST_FLOAT,
}


@dataclass(kw_only=True)
class Cast(BaseAstNode[KwargsCast, tuple[str]]):
    """
    Каст типов.

    DSL: to-int / to-float / to-bool / to-list-int / to-list-float
    kwargs: target ("int"|"float"|"bool"|"list_int"|"list_float")

    ret_type определяется автоматически из kwargs['target'].
    accept_type = ANY (кастануть можно любой тип, ошибка — в рантайме).
    """
    kind: ClassVar[TokenType] = TokenType.CAST
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)

    def __post_init__(self) -> None:
        super().__post_init__()
        target = self.kwargs.get("target", "")
        if target in _CAST_TYPE_MAP:
            self.ret_type = _CAST_TYPE_MAP[target]


@dataclass(kw_only=True)
class Jsonify(BaseAstNode):
    """
    Десериализация JSON-строки по схеме JsonDef.

    DSL:
        jsonify Quote
        jsonify Quote path="0"
        jsonify Quote path="1.text"

    kwargs:
        schema_name (str) — имя JsonDef
        path?       (str) — gjson-подобный путь внутри структуры
    """
    kind: ClassVar[TokenType] = TokenType.JSONIFY
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.JSON)


@dataclass(kw_only=True)
class JsonifyDynamic(BaseAstNode):
    """
    Динамический JSON (без привязки к схеме).

    DSL: jsonify
    kwargs: path? (str)
    """
    kind: ClassVar[TokenType] = TokenType.JSONIFY_DYNAMIC
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class Nested(BaseAstNode):
    """
    Вложенная схема как cast-операция.

    DSL: { Book }  (имя структуры в теле поля)
    kwargs: schema_name (str) — имя целевой Struct.
    """
    kind: ClassVar[TokenType] = TokenType.NESTED
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.NESTED)