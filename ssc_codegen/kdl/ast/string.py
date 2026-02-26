"""String operation AST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from .base import BaseAstNode
from .types import KwargsStringOp, KwargsFormat, KwargsMapRepl, KwargsRepl, KwargsJoin, EMPTY_KWARGS, EMTPY_ARGS
from ssc_codegen.kdl.tokens import TokenType, VariableType

@dataclass(kw_only=True)
class StringOp(BaseAstNode[KwargsStringOp, tuple[str]]):
    """
    Универсальная строковая операция.

    DSL: trim / ltrim / rtrim / rm-prefix "..." / rm-suffix "..." / rm-prefix-suffix "..."
    kwargs: op (StringOpMode), substr?
    """
    kind: ClassVar[TokenType] = TokenType.STRING
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class Format(BaseAstNode[KwargsFormat, tuple[str]]):
    """
    Форматирование строки.

    DSL: fmt FMT_URL / fmt "https://example.com/{{}}"
    kwargs: template (str) — строка с {{}} как placeholder.
    """
    kind: ClassVar[TokenType] = TokenType.FORMAT
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class Replace(BaseAstNode[KwargsRepl, tuple[str, str]]):
    """
    Замена подстроки.

    DSL: repl "old" "new"
    kwargs: old (str), new (str)
    """
    kind: ClassVar[TokenType] = TokenType.REPLACE
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class ReplaceMap(BaseAstNode[KwargsMapRepl, tuple[dict[str, str]]]):
    """
    Замена по словарю.

    DSL:
        repl {
            "One" "1"
            "Two" "2"
        }
    kwargs: replacements (dict[str, str])
    """
    kind: ClassVar[TokenType] = TokenType.REPLACE_MAP
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class Join(BaseAstNode[KwargsJoin, tuple[str]]):
    """
    Join списка строк в одну строку.

    DSL: join " " / join ","
    kwargs: sep (str)
    """
    kind: ClassVar[TokenType] = TokenType.JOIN
    accept_type: VariableType = field(default=VariableType.LIST_STRING)
    ret_type: VariableType = field(default=VariableType.STRING)


@dataclass(kw_only=True)
class Unescape(BaseAstNode[EMPTY_KWARGS, EMTPY_ARGS]):
    """
    Unescape строки (HTML entities, unicode escape и т.п.).

    DSL: unescape
    kwargs: mode? (опционально: "html", "unicode")
    """
    kind: ClassVar[TokenType] = TokenType.UNESCAPE
    accept_type: VariableType = field(default=VariableType.STRING)
    ret_type: VariableType = field(default=VariableType.STRING)