"""Validate / Assert AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsAssert
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Assert(BaseAstNode):
    """
    Assert-блок.

    DSL:
        assert { css "title" }
        assert { re #"."# ; ne "404" }

    Не изменяет тип данных — pass-through.
    body — список assert-операций (AssertCmp, AssertRe, AssertSelect, ...).
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class AssertCmp(BaseAstNode[KwargsAssert, tuple]):
    """
    Сравнение значения.

    DSL: eq "test123" / ne "404" / ne 100
    kwargs: op ("eq"|"ne"), value, msg?
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT_CMP
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)


@dataclass(kw_only=True)
class AssertRe(BaseAstNode):
    """
    Regex-валидация.

    DSL:
        re      #"..."#   → строка соответствует паттерну
        re-any  #"..."#   → хотя бы один элемент списка соответствует
        re-all  #"..."#   → все элементы списка соответствуют

    kwargs: mode ("re"|"re_any"|"re_all"), pattern (str)
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT_RE
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class AssertSelect(BaseAstNode):
    """
    Валидация наличия элемента в документе.

    DSL: css ".col-lg-3 .thumbnail" / xpath "//title"
    kwargs: mode ("css"|"xpath"), query (str)
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT_SELECT
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class AssertHasAttr(BaseAstNode):
    """
    Валидация наличия атрибута.

    DSL: has-attr "href"
    kwargs: attr (str)
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT_HAS_ATTR
    accept_type: VariableType = field(default=VariableType.DOCUMENT)
    ret_type: VariableType = field(default=VariableType.DOCUMENT)


@dataclass(kw_only=True)
class AssertContains(BaseAstNode):
    """
    Валидация наличия подстроки / элемента.

    DSL: contains "In stock" / contains "example.com"
    kwargs: value (str)
    """
    kind: ClassVar[TokenType] = TokenType.ASSERT_CONTAINS
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)