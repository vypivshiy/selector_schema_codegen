"""Parse/lint contexts, error codes, and supporting data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from ssc_codegen.ast import VariableType
from kdlquery import KdlNode, ReadDiagnostic, Severity
from kdlquery.types import Span


# ── Walk context enum ──────────────────────────────────────────────────────────


class WalkCtx(Enum):
    MODULE = auto()
    STRUCT_BODY = auto()
    INIT_BLOCK = auto()
    PIPELINE = auto()
    JSON_TYPEDEF = auto()
    SPECIAL_FIELD = auto()


# ── Error codes ────────────────────────────────────────────────────────────────


class ErrorCode(Enum):
    INVALID_SYNTAX = "E000"
    MISSING_ARGUMENT = "E001"
    INVALID_ARGUMENT = "E002"
    EMPTY_BLOCK = "E003"
    UNEXPECTED_CHILDREN = "E004"
    TYPE_MISMATCH = "E100"
    INCOMPATIBLE_OPERATION = "E101"
    UNKNOWN_OPERATION = "E200"
    UNKNOWN_FIELD = "E201"
    MISSING_REQUIRED_FIELD = "E202"
    INVALID_FIELD_FOR_TYPE = "E203"
    UNDEFINED_REFERENCE = "E300"
    INIT_FIELD_NOT_FOUND = "E301"
    DEFINE_NOT_FOUND = "E302"
    INVALID_STRUCT_TYPE = "E400"
    MISSING_SPECIAL_FIELD = "E401"
    DEPRECATED_SYNTAX = "W001"
    UNUSED_FIELD = "W002"


class DefineKind(Enum):
    SCALAR = auto()
    BLOCK = auto()


@dataclass
class RawArg:
    value: str
    span: Span


@dataclass
class DefineInfo:
    name: str
    kind: DefineKind
    value: str | None
    node: KdlNode


@dataclass
class TransformInfo:
    name: str
    accept: str
    ret: str
    langs: list[str]
    node: KdlNode


# ── Parse context ───────────────────────────────────────────────────────────────


@dataclass
class ParseContext:
    property_defines: dict[str, str | int | float | bool] = field(
        default_factory=dict
    )
    children_defines: dict[str, list[KdlNode]] = field(default_factory=dict)
    transforms: dict[str, TransformDef] = field(default_factory=dict)
    structs: dict[str, Struct] = field(default_factory=dict)
    json_defs: dict[str, JsonDef] = field(default_factory=dict)
    source_path: Path | None = None

    def all_names(self) -> set[str]:
        return (
            set(self.property_defines)
            | set(self.children_defines)
            | set(self.transforms)
            | set(self.structs)
            | set(self.json_defs)
        )


# ── Lint context ───────────────────────────────────────────────────────────────


@dataclass
class LintContext:
    """Lint state for reader-side validation (type inference, per-op checks)."""

    defines: dict[str, DefineInfo] = field(default_factory=dict)
    transforms: dict[str, TransformInfo] = field(default_factory=dict)
    init_fields: set[str] = field(default_factory=set)
    walk_context: WalkCtx = WalkCtx.MODULE
    _path_segments: list[str] = field(default_factory=list)
    diagnostics: list[ReadDiagnostic] = field(default_factory=list)
    inferred_define_types: dict[str, tuple[VariableType, VariableType]] = field(
        default_factory=dict
    )
    _predicate_depth: int = field(default=0)
    _predicate_context: str = ""

    def error(
        self,
        node: KdlNode,
        *,
        message: str,
        code: str = "",
        hint: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self.diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.ERROR,
                span=node.span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )

    def warning(
        self,
        node: KdlNode,
        *,
        message: str,
        code: str = "",
        hint: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self.diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.WARNING,
                span=node.span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )

    @property
    def path(self) -> str:
        return "/".join(self._path_segments)

    def push(self, segment: str) -> None:
        self._path_segments.append(segment)

    def pop(self) -> None:
        self._path_segments.pop()

    def resolve_scalar_arg(self, arg: str) -> str | None:
        info = self.defines.get(arg)
        if info is not None and info.kind == DefineKind.SCALAR:
            return info.value
        return None

    @property
    def in_predicate(self) -> bool:
        return self._predicate_depth > 0

    @property
    def in_assert(self) -> bool:
        return self._predicate_depth > 0 and self._predicate_context == "assert"


# lazy imports for forward refs
from ssc_codegen.ast import (  # noqa: E402
    JsonDef,
    Struct,
    TransformDef,
)
