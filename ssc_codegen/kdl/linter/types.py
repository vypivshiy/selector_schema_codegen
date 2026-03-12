"""Common types for linter"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from tree_sitter import Node


class ErrorCode(Enum):
    """Коды ошибок линтера"""
    
    # Syntax errors (E001-E099)
    MISSING_ARGUMENT = "E001"
    INVALID_ARGUMENT = "E002"
    EMPTY_BLOCK = "E003"
    UNEXPECTED_CHILDREN = "E004"
    
    # Type errors (E100-E199)
    TYPE_MISMATCH = "E100"
    INCOMPATIBLE_OPERATION = "E101"
    
    # Semantic errors (E200-E299)
    UNKNOWN_OPERATION = "E200"
    UNKNOWN_FIELD = "E201"
    MISSING_REQUIRED_FIELD = "E202"
    INVALID_FIELD_FOR_TYPE = "E203"
    
    # Reference errors (E300-E399)
    UNDEFINED_REFERENCE = "E300"
    INIT_FIELD_NOT_FOUND = "E301"
    DEFINE_NOT_FOUND = "E302"
    
    # Structure errors (E400-E499)
    INVALID_STRUCT_TYPE = "E400"
    MISSING_SPECIAL_FIELD = "E401"
    
    # Warnings (W001-W999)
    DEPRECATED_SYNTAX = "W001"
    UNUSED_FIELD = "W002"


@dataclass
class LintError:
    code: ErrorCode
    message: str
    hint: str
    path: str
    line: int
    col: int
    severity: Literal["error", "warning"] = "error"
    
    @property
    def category(self) -> str:
        """Категория ошибки из кода"""
        code_num = int(self.code.value[1:])
        if code_num < 100:
            return "syntax"
        elif code_num < 200:
            return "type"
        elif code_num < 300:
            return "semantic"
        elif code_num < 400:
            return "reference"
        elif code_num < 500:
            return "structure"
        else:
            return "warning"

    def __str__(self) -> str:
        sev = self.severity.upper()
        return (
            f"{sev}: {self.message}\n"
            f"  --> {self.path}  line {self.line}:{self.col}\n"
            f"   |\n"
            f"   | hint: {self.hint}\n"
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
            "path": self.path,
            "line": self.line,
            "col": self.col,
        }


@dataclass
class RawArg:
    """Аргумент с типом (identifier vs literal)"""
    value: str
    is_identifier: bool
    node: Node


class DefineKind(Enum):
    SCALAR = auto()  # define FOO="value"
    BLOCK = auto()  # define FOO { ops... }


@dataclass
class DefineInfo:
    name: str
    kind: DefineKind
    value: str | None  # SCALAR value; None for BLOCK
    node: Node


@dataclass
class TransformInfo:
    """Metadata collected from a module-level 'transform' block."""
    name: str
    accept: str  # raw type string, e.g. "STRING"
    ret: str     # raw type string, e.g. "LIST_STRING"
    langs: list[str]  # language identifiers present, e.g. ["py", "js"]
    node: Node
