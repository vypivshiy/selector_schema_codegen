"""Table parser AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsTable, KwargsTableMatchKey, KwargsTableMatchValue, KwargsTableMatch
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class TableConfig(BaseAstNode[KwargsTable, tuple[str]]):
    """
    Конфигурация таблицы.
    DSL: -table { css "table.table-striped" }
    kwargs: selector — CSS/XPath строка для выбора элемента таблицы.
    """
    kind: ClassVar[TokenType] = TokenType.TABLE_CONFIG
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class TableRow(BaseAstNode):
    """
    Селектор строк таблицы.
    DSL: -row { css "tr" }
    body — пайплайн, возвращающий LIST_DOCUMENT (строки таблицы).
    """
    kind: ClassVar[TokenType] = TokenType.TABLE_ROW
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass(kw_only=True)
class TableMatchKey(BaseAstNode[KwargsTableMatchKey, tuple]):
    """
    Критерий поиска нужной строки таблицы (-match).
    DSL: -match { css "th"; text; trim }
    body — пайплайн: извлекаем текст из ячейки-ключа и сравниваем.
    Результат используется для фильтрации строк, не попадает в ret.
    """
    kind: ClassVar[TokenType] = TokenType.TABLE_MATCH_KEY
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class TableMatchValue(BaseAstNode[KwargsTableMatchValue, tuple]):
    """
    Пайплайн извлечения значения из найденной строки (-value).
    DSL: -value { css "td"; text; trim }
    body — пайплайн обработки ячейки-значения.
    """
    kind: ClassVar[TokenType] = TokenType.TABLE_MATCH_VALUE
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class TableMatch(BaseAstNode[KwargsTableMatch, tuple[list[str]]]):
    """
    Match-блок внутри поля таблицы.
    DSL: match { eq "UPC" } / match { starts "Price (excl." }
    kwargs: conditions — список строк-условий.
    """
    kind: ClassVar[TokenType] = TokenType.TABLE_MATCH
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)