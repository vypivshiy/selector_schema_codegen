"""Regex AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseAstNode
from .types import KwargsRegex
from ssc_codegen.kdl.tokens import TokenType, VariableType


@dataclass(kw_only=True)
class Regex(BaseAstNode[KwargsRegex, tuple]):
    """
    Универсальная regex-операция.

    DSL:
        re #"(\\d+)"#               → mode="re",     group=1
        re-all #"(\\w+)"#           → mode="re_all"  → LIST_STRING
        re-sub #"\\s+"# repl=" "   → mode="re_sub"

    kwargs: mode, pattern, group?, repl?, ignore_case?, dotall?

    ret_type:
        re     → STRING
        re_all → LIST_STRING
        re_sub → STRING
    """
    kind: ClassVar[TokenType] = TokenType.REGEX
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)