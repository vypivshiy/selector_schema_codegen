"""Parse/lint contexts, error codes, and supporting data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from ssc_codegen.ast import ExtensionDef, StructBase, VariableType
from kdlquery import KdlNode, ReadDiagnostic, Severity


# ── Walk context enum ──────────────────────────────────────────────────────────


class WalkCtx(Enum):
    """Scope context indicating the current AST traversal location during parsing."""

    MODULE = auto()
    """Top-level module scope."""

    STRUCT_BODY = auto()
    """Inside a struct declaration body."""

    INIT_BLOCK = auto()
    """Inside an `@init` initialization block."""

    PIPELINE = auto()
    """Inside a field transformation pipeline."""

    JSON_TYPEDEF = auto()
    """Inside a JSON schema definition body."""

    SPECIAL_FIELD = auto()
    """Inside a special directive field (@split-doc, @key, @value, etc.)."""


# ── Error codes ────────────────────────────────────────────────────────────────


class ErrorCode(str, Enum):
    """Canonical compiler error and warning diagnostic codes.

    Attributes:
        SYNTAX_ERROR: KDL syntax parsing error (`E000`).
        INVALID_ARGUMENT_COUNT: Missing or excess arguments on directive/op (`E001`).
        INVALID_ARGUMENT_VALUE: Invalid argument type, regex, or selector syntax (`E002`).
        INVALID_IMPORT: Missing, invalid, or duplicate import path/symbols (`E003`).
        MALFORMED_DOTPATH: Malformed dot-notation path in json/jsonify (`E040`).
        DUPLICATE_JSON_KEY: Duplicate source or output key in JSON schema (`E041`).
        TYPE_MISMATCH: Incompatible input/output types in pipeline or fallback (`E100`).
        UNKNOWN_NODE: Unknown top-level node or pipeline operation (`E200`).
        DISALLOWED_DIRECTIVE: Directive not permitted in the current struct/fn context (`E203`).
        UNDEFINED_SYMBOL: Reference to undefined struct, json, or extension (`E300`).
        UNDEFINED_INIT_FIELD: Reference to undeclared `@init` field in pipeline (`E301`).
        INVALID_DECLARATION_ORDER: Helper struct/json declared below caller (`E302`).
        INVALID_TYPE_DECLARATION: Unknown struct type or invalid extension signature (`E400`).
        MISSING_REQUIRED_FIELD: Struct missing required structural directives (`E401`).
        DUPLICATE_DECLARATION: Duplicate struct, json, or symbol collision across targets (`E402`).
        INVALID_IDENTIFIER: Symbol name produces invalid target language identifier (`E403`).
        DEPRECATED_JSON_ALIAS: Positional JSON key alias warning (`W011`).
        WHITESPACE_IN_PATH: Leading or trailing whitespace in `from` path (`W040`).
    """

    # E0xx: Syntax, Arguments & Core Structure
    SYNTAX_ERROR = "E000"
    INVALID_ARGUMENT_COUNT = "E001"
    INVALID_ARGUMENT_VALUE = "E002"
    INVALID_IMPORT = "E003"
    MALFORMED_DOTPATH = "E040"
    DUPLICATE_JSON_KEY = "E041"

    # E1xx: Type System & Pipeline Compatibility
    TYPE_MISMATCH = "E100"

    # E2xx: Grammar, Placement & Unknown Elements
    UNKNOWN_NODE = "E200"
    DISALLOWED_DIRECTIVE = "E203"

    # E3xx: Symbol Resolution & Declaration Order
    UNDEFINED_SYMBOL = "E300"
    UNDEFINED_INIT_FIELD = "E301"
    INVALID_DECLARATION_ORDER = "E302"

    # E4xx: Declarations, Struct Types & Target Symbols
    INVALID_TYPE_DECLARATION = "E400"
    MISSING_REQUIRED_FIELD = "E401"
    DUPLICATE_DECLARATION = "E402"
    INVALID_IDENTIFIER = "E403"

    # W0xx: Compiler Warnings
    DEPRECATED_JSON_ALIAS = "W011"
    WHITESPACE_IN_PATH = "W040"


class DefineKind(Enum):
    """Categorization of `define` declarations."""

    SCALAR = auto()
    """Scalar constant replacement (`define NAME=value`)."""

    BLOCK = auto()
    """Reusable pipeline block expansion (`define NAME { ... }`)."""


@dataclass
class DefineInfo:
    """Metadata for a registered `define` symbol.

    Attributes:
        name: Name of the define constant or block.
        kind: Whether this define is a scalar value or a pipeline block.
        value: Resolved string value if scalar, or `None` if block.
        node: Originating KDL node AST element.
    """

    name: str
    kind: DefineKind
    value: str | None
    node: KdlNode


# ── Parse context ───────────────────────────────────────────────────────────────


@dataclass
class ParseContext:
    """Global symbol table and environment state accumulated during parsing.

    Attributes:
        property_defines: Resolved scalar define constants (`NAME: value`).
        children_defines: Reusable pipeline block AST nodes (`NAME: [KdlNode, ...]`).
        structs: Map of parsed struct AST nodes by struct name.
        json_defs: Map of parsed JSON schema definitions by schema name.
        extensions: Map of parsed extension definitions by qualified name (`Namespace.op`).
        source_path: Filesystem path to the root schema being parsed, if available.
        source_text: Full raw text of the root KDL document.
        node_source_paths: Mapping of KDL node object IDs to their originating file paths.
    """

    property_defines: dict[str, str | int | float | bool] = field(
        default_factory=dict
    )
    children_defines: dict[str, list[KdlNode]] = field(default_factory=dict)
    structs: dict[str, StructBase] = field(default_factory=dict)
    json_defs: dict[str, JsonDef] = field(default_factory=dict)
    extensions: dict[str, ExtensionDef] = field(default_factory=dict)
    source_path: Path | None = None
    source_text: str = ""
    node_source_paths: dict[int, Path] = field(default_factory=dict)

    def all_names(self) -> set[str]:
        """Return the set of all declared symbol names across all categories."""
        return (
            set(self.property_defines)
            | set(self.children_defines)
            | set(self.structs)
            | set(self.json_defs)
            | set(self.extensions)
        )


# ── Lint context ───────────────────────────────────────────────────────────────


@dataclass
class LintContext:
    """State tracking for reader-side semantic validation and diagnostic reporting.

    Attributes:
        defines: Map of define metadata registered during pre-passes.
        init_fields: Set of field names declared in the current struct's `@init` block.
        walk_context: Current structural scope enum (`WalkCtx`).
        diagnostics: Collected list of `ReadDiagnostic` warnings and errors.
        inferred_define_types: Inferred `(input_type, output_type)` for block defines.
        node_source_paths: Mapping of KDL node object IDs to their originating file paths.
    """

    defines: dict[str, DefineInfo] = field(default_factory=dict)
    init_fields: set[str] = field(default_factory=set)
    walk_context: WalkCtx = WalkCtx.MODULE
    _path_segments: list[str] = field(default_factory=list)
    diagnostics: list[ReadDiagnostic] = field(default_factory=list)
    inferred_define_types: dict[str, tuple[VariableType, VariableType]] = field(
        default_factory=dict
    )
    _predicate_depth: int = field(default=0)
    _predicate_context: str = ""
    node_source_paths: dict[int, Path] = field(default_factory=dict)

    def error(
        self,
        node: KdlNode,
        *,
        message: str,
        code: str | ErrorCode = "",
        hint: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record an error diagnostic at the span of the given KDL node.

        Args:
            node: Originating KDL node AST element.
            message: Human-readable error description.
            code: Standard diagnostic error code (e.g. `ErrorCode.INVALID_ARGUMENT_COUNT` or `"E001"`).
            hint: Actionable suggestion on how to resolve the error.
            label: Short label under the underlined source span.
            notes: Optional list of additional informational notes.
        """
        scope = self.path
        source_path = self.node_source_paths.get(id(node))
        diagnostic_notes = tuple(notes) if notes else ()
        if source_path is not None and scope:
            diagnostic_notes = (*diagnostic_notes, f"scope: {scope}")
        diagnostic = ReadDiagnostic(
            message=message,
            severity=Severity.ERROR,
            span=node.span,
            path=str(source_path) if source_path is not None else scope,
            hint=hint,
            code=str(code.value if isinstance(code, ErrorCode) else code),
            label=label,
            notes=diagnostic_notes,
        )
        self.diagnostics.append(diagnostic)

    def warning(
        self,
        node: KdlNode,
        *,
        message: str,
        code: str | ErrorCode = "",
        hint: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record a warning diagnostic at the span of the given KDL node.

        Args:
            node: Originating KDL node AST element.
            message: Human-readable warning description.
            code: Standard diagnostic warning code (e.g. `ErrorCode.DEPRECATED_JSON_ALIAS` or `"W011"`).
            hint: Actionable suggestion on how to resolve the warning.
            label: Short label under the underlined source span.
            notes: Optional list of additional informational notes.
        """
        scope = self.path
        source_path = self.node_source_paths.get(id(node))
        diagnostic_notes = tuple(notes) if notes else ()
        if source_path is not None and scope:
            diagnostic_notes = (*diagnostic_notes, f"scope: {scope}")
        diagnostic = ReadDiagnostic(
            message=message,
            severity=Severity.WARNING,
            span=node.span,
            path=str(source_path) if source_path is not None else scope,
            hint=hint,
            code=str(code.value if isinstance(code, ErrorCode) else code),
            label=label,
            notes=diagnostic_notes,
        )
        self.diagnostics.append(diagnostic)

    @property
    def path(self) -> str:
        """Slash-delimited path representing the current AST navigation scope."""
        return "/".join(self._path_segments)

    def push(self, segment: str) -> None:
        """Push a scope segment onto the path stack."""
        self._path_segments.append(segment)

    def pop(self) -> None:
        """Pop the topmost scope segment from the path stack."""
        self._path_segments.pop()

    def resolve_scalar_arg(self, arg: str) -> str | None:
        """Resolve an argument string against registered scalar defines.

        Args:
            arg: Name of the define to resolve.

        Returns:
            The resolved string value if defined as a scalar, or `None`.
        """
        info = self.defines.get(arg)
        if info is not None and info.kind == DefineKind.SCALAR:
            return info.value
        return None

    @property
    def in_predicate(self) -> bool:
        """Whether the traversal cursor is currently inside a predicate block."""
        return self._predicate_depth > 0

    @property
    def in_assert(self) -> bool:
        """Whether the traversal cursor is currently inside an `assert` block."""
        return self._predicate_depth > 0 and self._predicate_context == "assert"


# lazy imports for forward refs
from ssc_codegen.ast import (  # noqa: E402
    JsonDef,
)
