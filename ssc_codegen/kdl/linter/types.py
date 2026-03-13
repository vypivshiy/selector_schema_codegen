"""Common types for linter"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal

from tree_sitter import Node


class ErrorCode(Enum):
    """Коды ошибок линтера"""

    # Syntax errors (E000-E099)
    INVALID_SYNTAX = "E000"
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
    hint: str = ""
    path: str = ""
    line: int = 1
    col: int = 1
    end_line: int | None = None
    end_col: int | None = None
    label: str | None = None
    notes: list[str] = field(default_factory=list)
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

    @property
    def display_label(self) -> str | None:
        """Короткая подпись для underline-строки."""
        if self.label:
            return self.label

        msg = self.message.lower()
        if "invalid syntax" in msg or "syntax error" in msg:
            return "invalid syntax"
        if "does not accept arguments" in msg:
            return "unexpected arguments"
        if "requires exactly" in msg or "requires " in msg:
            return "invalid argument count"
        if "capture group" in msg:
            return "invalid capture groups"
        if "invalid regex" in msg:
            return "invalid regex"
        if "placeholder" in msg:
            return "missing placeholder"
        if "undefined" in msg:
            return "undefined reference"
        if "unknown operation" in msg:
            return "unknown operation"
        if "unknown field" in msg:
            return "unknown field"
        if "type mismatch" in msg:
            return "type mismatch"
        if "deprecated" in msg:
            return "deprecated syntax"
        if "empty block" in msg:
            return "empty block"

        default_labels: dict[ErrorCode, str] = {
            ErrorCode.INVALID_SYNTAX: "invalid syntax",
            ErrorCode.MISSING_ARGUMENT: "missing argument",
            ErrorCode.INVALID_ARGUMENT: "invalid argument",
            ErrorCode.EMPTY_BLOCK: "empty block",
            ErrorCode.UNEXPECTED_CHILDREN: "unexpected children",
            ErrorCode.TYPE_MISMATCH: "type mismatch",
            ErrorCode.INCOMPATIBLE_OPERATION: "incompatible operation",
            ErrorCode.UNKNOWN_OPERATION: "unknown operation",
            ErrorCode.UNKNOWN_FIELD: "unknown field",
            ErrorCode.MISSING_REQUIRED_FIELD: "missing required field",
            ErrorCode.INVALID_FIELD_FOR_TYPE: "invalid field for type",
            ErrorCode.UNDEFINED_REFERENCE: "undefined reference",
            ErrorCode.INIT_FIELD_NOT_FOUND: "init field not found",
            ErrorCode.DEFINE_NOT_FOUND: "define not found",
            ErrorCode.INVALID_STRUCT_TYPE: "invalid struct type",
            ErrorCode.MISSING_SPECIAL_FIELD: "missing special field",
            ErrorCode.DEPRECATED_SYNTAX: "deprecated syntax",
            ErrorCode.UNUSED_FIELD: "unused field",
        }
        return default_labels.get(self.code)

    def __str__(self) -> str:
        sev = self.severity.upper()
        code = self.code.value
        scope = f"\n  scope: {self.path}" if self.path else ""
        return (
            f"{sev}[{code}]: {self.message}\n"
            f"  --> line {self.line}:{self.col}{scope}\n"
            f"  help: {self.hint}\n"
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
            "end_line": self.end_line,
            "end_col": self.end_col,
            "label": self.label,
            "notes": self.notes,
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
