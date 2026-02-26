"""Filter AST nodes (STRING pipeline)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsFilterCompare, KwargsFilterString, KwargsFilterDef, KwargsFilterRe, KwargsFilterRange
from ssc_codegen.kdl.tokens import TokenType, VariableType


# TODO: remove
@dataclass(kw_only=True)
class FilterDef(BaseAstNode[KwargsFilterDef, tuple[str]]):
    """
    Именованный standalone-фильтр (define-подобный).

    DSL:
        filter F-IMAGE-PNG { ends ".png" }
        filter F-EQ-LOREM  { eq "lorem" "upsum" "dolor" }

    Не генерируется в код самостоятельно — только для inline-распаковки
    внутри DSL-выражений полей (аналог define).

    kwargs:
        name — идентификатор фильтра (напр. "F-IMAGE-PNG")

    body — список filter-операций (FilterCmp, FilterStr, FilterRe, FilterLen,
           LogicNot, FilterDoc...).
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_DEF
    accept_type: VariableType = field(default=VariableType.LIST_STRING)
    ret_type: VariableType = field(default=VariableType.LIST_STRING)


@dataclass(kw_only=True)
class Filter(BaseAstNode):
    """
    Filter-блок внутри поля.

    DSL:
        filter { ends ".png" ".jpg"; not { ends ".webp" } }

    Принимает и возвращает тот же тип (LIST_STRING или LIST_DOCUMENT).
    Конкретный тип уточняется при построении AST.
    """
    kind: ClassVar[TokenType] = TokenType.FILTER
    accept_type: VariableType = field(default=VariableType.LIST_STRING)
    ret_type: VariableType = field(default=VariableType.LIST_STRING)


ARGS_FILTER_CMP = tuple[str, str | int | float | tuple[str, ...]]
@dataclass(kw_only=True)
class FilterCmp(BaseAstNode[KwargsFilterCompare, ARGS_FILTER_CMP]):
    """
    Сравнение строки или её длины.

    DSL: eq "lorem" / ne "x" / gt 10 / lt 32 / ge 5 / le 100
    kwargs: op, value, is_len (True → сравниваем len(str))
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_CMP
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class FilterStr(BaseAstNode[KwargsFilterString, tuple[str, tuple[str, ...]]]):
    """
    Строковые фильтры (OR-семантика по нескольким значениям).

    DSL:
        starts "tel:" "email:"     → str.startswith(any of...)
        ends   ".png" ".jpg"       → str.endswith(any of...)
        contains "lorem" "upsum"   → any of in str
        in "a" "b" "c"             → str in (a, b, c)

    kwargs: op, values (tuple)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_STR
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class FilterRe(BaseAstNode[KwargsFilterRe, tuple[str, bool, bool]]):
    """
    Regex-фильтр.

    DSL: re #"\\D"#
    kwargs: pattern (str), ignore_case?, dotall?
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_RE
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class FilterRange(BaseAstNode[KwargsFilterRange, tuple[int, int]]):
    """
    Фильтр по длине строки.

    DSL: range 10 1024  (shortcut: gt 10; lt 1024)
    kwargs: op (FilterCompareOp), value (int)
    """
    kind: ClassVar[TokenType] = TokenType.FILTER_LEN
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)