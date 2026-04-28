"""
Unified KDL → Module AST reader with integrated linting.

Single-pass: walks KdlNode tree, builds AST, collects diagnostics.

Usage:
    module, diagnostics = parse_module(kdl_source, source_path=Path("schema.kdl"))
"""

from __future__ import annotations

import ast as _py_ast
import difflib as _difflib
import re as _re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, TypeAlias, TypeVar

from ssc_codegen.kdl import (
    KDL2CSTParser,
    KdlArg,
    KdlNode,
    ReadDiagnostic,
    Reader,
    Severity,
    WalkContext,
    parse_into,
)
from ssc_codegen.kdl.parser import Span
from ssc_codegen.regex_utils import normalize_regex_pattern

# ── AST imports ──────────────────────────────────────────────────────────────────

from ssc_codegen.ast import Node as AstNode

# module layer
from ssc_codegen.ast import Module, Struct, TypeDef, TypeDefField

# struct layer
from ssc_codegen.ast import (
    PreValidate,
    CheckMethod,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
    Field,
    Init,
    InitField,
    Key,
    Value,
    RequestConfig,
    ErrorResponse,
    StartParse,
)

# expressions — selectors
from ssc_codegen.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
)

# expressions — extract
from ssc_codegen.ast import Text, Raw, Attr

# expressions — string
from ssc_codegen.ast import (
    Trim,
    Ltrim,
    Rtrim,
    NormalizeSpace,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    Unescape,
)

# expressions — regex
from ssc_codegen.ast import Re, ReAll, ReSub

# expressions — array
from ssc_codegen.ast import Index, Slice, Len, Unique

# expressions — casts
from ssc_codegen.ast import ToInt, ToFloat, ToBool, Jsonify, Nested

# expressions — control
from ssc_codegen.ast import (
    Self,
    Fallback,
    Return,
    FallbackStart,
    FallbackEnd,
)

# expressions — predicates
from ssc_codegen.ast import Filter, Assert, Match
from ssc_codegen.ast import LogicOr, LogicAnd, LogicNot

# predicate ops
from ssc_codegen.ast import (
    PredEq,
    PredNe,
    PredGt,
    PredLt,
    PredGe,
    PredLe,
    PredIn,
    PredStarts,
    PredEnds,
    PredContains,
    PredRe,
    PredReAny,
    PredReAll,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredAttrContains,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredRange,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
)

# json / transform
from ssc_codegen.ast import JsonDef, JsonDefField, TransformDef, TransformTarget, TransformCall

# types
from ssc_codegen.ast import StructType, VariableType

# exceptions
from ssc_codegen.exceptions import ParseError, BuildTimeError


# ── KdlNode adapter ──────────────────────────────────────────────────────────────


def _adapt(node: KdlNode) -> _NodeAdapter:
    return _NodeAdapter(node)


class _NodeAdapter:
    """Adapts KdlNode to the old TsKdlNode protocol used by handler functions."""

    __slots__ = ("name", "args", "properties", "children", "type_annotation")

    def __init__(self, kn: KdlNode) -> None:
        self.name = kn.name
        self.args = [a.value for a in kn.args]
        self.properties = {k: v.value for k, v in kn.properties.items()}
        self.children = kn.children  # KdlNode.children is tuple[KdlNode, ...]
        self.type_annotation = kn.type_annotation

    def __repr__(self) -> str:
        return f"<_NodeAdapter {self.name!r}>"


# ── Walk context enum (lint) ─────────────────────────────────────────────────────


class _WalkCtx(Enum):
    MODULE = auto()
    STRUCT_BODY = auto()
    INIT_BLOCK = auto()
    PIPELINE = auto()
    JSON_TYPEDEF = auto()
    SPECIAL_FIELD = auto()


# ── Parse context ────────────────────────────────────────────────────────────────


@dataclass
class _ParseContext:
    property_defines: dict[str, str | int | float | bool] = field(default_factory=dict)
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


# ── Lint context ─────────────────────────────────────────────────────────────────


class _ErrorCode(Enum):
    # Syntax (E000-E099)
    INVALID_SYNTAX = "E000"
    MISSING_ARGUMENT = "E001"
    INVALID_ARGUMENT = "E002"
    EMPTY_BLOCK = "E003"
    UNEXPECTED_CHILDREN = "E004"
    # Type (E100-E199)
    TYPE_MISMATCH = "E100"
    INCOMPATIBLE_OPERATION = "E101"
    # Semantic (E200-E299)
    UNKNOWN_OPERATION = "E200"
    UNKNOWN_FIELD = "E201"
    MISSING_REQUIRED_FIELD = "E202"
    INVALID_FIELD_FOR_TYPE = "E203"
    # Reference (E300-E399)
    UNDEFINED_REFERENCE = "E300"
    INIT_FIELD_NOT_FOUND = "E301"
    DEFINE_NOT_FOUND = "E302"
    # Structure (E400-E499)
    INVALID_STRUCT_TYPE = "E400"
    MISSING_SPECIAL_FIELD = "E401"
    # Warnings (W001-W999)
    DEPRECATED_SYNTAX = "W001"
    UNUSED_FIELD = "W002"


class _DefineKind(Enum):
    SCALAR = auto()
    BLOCK = auto()


@dataclass
class _RawArg:
    value: str
    is_identifier: bool
    span: Span


@dataclass
class _DefineInfo:
    name: str
    kind: _DefineKind
    value: str | None
    node: KdlNode


@dataclass
class _TransformInfo:
    name: str
    accept: str
    ret: str
    langs: list[str]
    node: KdlNode


@dataclass
class _LintContext:
    """Lint state: defines, transforms, init_fields, walk context, path, diagnostics."""

    defines: dict[str, _DefineInfo] = field(default_factory=dict)
    transforms: dict[str, _TransformInfo] = field(default_factory=dict)
    init_fields: set[str] = field(default_factory=set)
    walk_context: _WalkCtx = _WalkCtx.MODULE
    _path_segments: list[str] = field(default_factory=list)
    diagnostics: list[ReadDiagnostic] = field(default_factory=list)
    inferred_define_types: dict[str, tuple[VariableType, VariableType]] = field(
        default_factory=dict
    )
    dsl_names: set[str] = field(default_factory=set)
    _predicate_depth: int = field(default=0)
    _predicate_context: str = ""  # "filter", "assert", or "match"

    # -- error reporting -------------------------------------------------------

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

    # -- helpers ---------------------------------------------------------------

    @property
    def path(self) -> str:
        return "/".join(self._path_segments)

    def push(self, segment: str) -> None:
        self._path_segments.append(segment)

    def pop(self) -> None:
        self._path_segments.pop()

    def node_name(self, node: KdlNode) -> str:
        return node.name

    def get_args(self, node: KdlNode) -> list[str]:
        return [str(a.value) for a in node.args]

    def get_raw_args(self, node: KdlNode) -> list[_RawArg]:
        return [
            _RawArg(value=str(a.value), is_identifier=a.is_identifier, span=a.span)
            for a in node.args
        ]

    def get_arg(self, node: KdlNode, index: int) -> str | None:
        args = self.get_args(node)
        return args[index] if index < len(args) else None

    def get_prop(self, node: KdlNode, key: str) -> str | None:
        entry = node.properties.get(key)
        return str(entry.value) if entry else None

    def get_children_nodes(self, node: KdlNode) -> list[KdlNode]:
        return list(node.children)

    def has_empty_block(self, node: KdlNode) -> bool:
        return len(node.children) == 0

    def is_define_ref(self, arg: str) -> bool:
        return arg in self.defines

    def resolve_scalar_arg(self, arg: str) -> str | None:
        info = self.defines.get(arg)
        if info is not None and info.kind == _DefineKind.SCALAR:
            return info.value
        return None

    @property
    def in_predicate(self) -> bool:
        return self._predicate_depth > 0

    @property
    def in_assert(self) -> bool:
        return self._predicate_depth > 0 and self._predicate_context == "assert"


# ── Registration tables ──────────────────────────────────────────────────────────

CallbackRegModule = Callable[[KdlNode, Module, _ParseContext, _LintContext], AstNode]
CallbackRegContext = Callable[[KdlNode, _ParseContext, _LintContext], None]
CallbackRegStruct = Callable[[KdlNode, Struct, _ParseContext, _LintContext], AstNode]

FieldLikeNode: TypeAlias = (
    PreValidate | SplitDoc | TableConfig | TableRow | TableMatchKey
    | Key | Value | Field | InitField
)
CallbackReg = Callable[[KdlNode, FieldLikeNode, _ParseContext, _LintContext], AstNode]
CallbackFilter = Callable[[KdlNode, Filter, _ParseContext, _LintContext], AstNode]
CallbackAssert = Callable[[KdlNode, Assert, _ParseContext, _LintContext], AstNode]
CallbackMatch = Callable[[KdlNode, Match, _ParseContext, _LintContext], AstNode]

PredicateLikeNode: TypeAlias = LogicNot | LogicAnd | LogicOr | Filter | Assert | Match
CallbackPred = Callable[[KdlNode, PredicateLikeNode, _ParseContext, _LintContext], AstNode]


# ── AST builder ──────────────────────────────────────────────────────────────────


def _resolve_selector_arg(
    query: str | int | float | bool, ctx: _ParseContext
) -> str:
    value = ctx.property_defines.get(query, query)
    return value if isinstance(value, str) else str(value)


def _resolve_selector_child_name(name: str, ctx: _ParseContext) -> str:
    value = ctx.property_defines.get(name, _decode_scalar(name))
    return value if isinstance(value, str) else str(value)


def _decode_scalar(text: str) -> Any:
    text = text.strip()
    if text == "#true":
        return True
    if text == "#false":
        return False
    if text == "#null":
        return None
    if _looks_like_raw_string(text):
        return _decode_raw_string(text)
    if text.startswith('"""') and text.endswith('"""'):
        return text[3:-3]
    if text.startswith('"') and text.endswith('"'):
        try:
            return _py_ast.literal_eval(text)
        except Exception:
            return text[1:-1]
    if _INTEGER_RE.fullmatch(text):
        return int(text.replace("_", ""), 10)
    if _FLOAT_RE.fullmatch(text):
        return float(text.replace("_", ""))
    return text


def _looks_like_raw_string(text: str) -> bool:
    return text.startswith("#") and '"' in text and text.endswith("#")


def _decode_raw_string(text: str) -> str:
    m = _re.fullmatch(r'(#+)("""|")(.*)\2\1', text, flags=_re.DOTALL)
    if not m:
        return text
    return m.group(3)


_INTEGER_RE = _re.compile(r"[+-]?\d(?:[\d_])*\Z")
_FLOAT_RE = _re.compile(
    r"[+-]?(?:\d(?:[\d_])*\.\d(?:[\d_])*|\d(?:[\d_])*[eE][+-]?\d(?:[\d_])*|\d(?:[\d_]*)\.\d(?:[\d_]*)[eE][+-]?\d(?:[\d_])*)\Z"
)


_DEFINE_REF_RE = _re.compile(r"\{\{([A-Za-z][A-Za-z0-9_-]*)\}\}")


def _resolve_define_references(value: str, ctx: _ParseContext) -> str:
    def _replacer(m: _re.Match) -> str:
        name = m.group(1)
        resolved = ctx.property_defines.get(name)
        if resolved is None:
            raise ParseError(f"define references undefined name {name!r}")
        return str(resolved)

    return _DEFINE_REF_RE.sub(_replacer, value)


_VAR_TYPE_MAP: dict[str, VariableType] = {
    "STRING": VariableType.STRING,
    "OPT_STRING": VariableType.OPT_STRING,
    "LIST_STRING": VariableType.LIST_STRING,
    "INT": VariableType.INT,
    "OPT_INT": VariableType.OPT_INT,
    "LIST_INT": VariableType.LIST_INT,
    "FLOAT": VariableType.FLOAT,
    "OPT_FLOAT": VariableType.OPT_FLOAT,
    "LIST_FLOAT": VariableType.LIST_FLOAT,
    "BOOL": VariableType.BOOL,
    "NULL": VariableType.NULL,
    "DOCUMENT": VariableType.DOCUMENT,
    "LIST_DOCUMENT": VariableType.LIST_DOCUMENT,
    "NESTED": VariableType.NESTED,
    "JSON": VariableType.JSON,
}


def _resolve_index_types(
    parent: FieldLikeNode,
) -> tuple[VariableType, VariableType]:
    if parent.body:
        prev_type = parent.body[-1].ret
        accept = prev_type
        ret = prev_type.scalar if prev_type.is_list else prev_type
    else:
        accept = VariableType.LIST_AUTO
        ret = VariableType.AUTO
    return accept, ret


def _resolve_jsonify_type(
    json_def: JsonDef, path: str, ctx: _ParseContext
) -> tuple[VariableType, bool]:
    if not path:
        return VariableType.JSON, json_def.is_array
    segments = path.split(".")
    current_def = json_def
    current_is_array = json_def.is_array
    for i, segment in enumerate(segments):
        if current_is_array and segment.isdigit():
            current_is_array = False
            continue
        field = None
        for f in current_def.body:
            if isinstance(f, JsonDefField) and (f.name == segment or f.alias == segment):
                field = f
                break
        if field is None:
            return VariableType.JSON, False
        if i == len(segments) - 1:
            return field.ret, field.is_array
        if field.ret != VariableType.JSON:
            return VariableType.JSON, False
        if not field.ref_name:
            return VariableType.JSON, False
        nested_def = ctx.json_defs.get(field.ref_name)
        if not nested_def:
            return VariableType.JSON, False
        current_def = nested_def
        current_is_array = field.is_array
    return VariableType.JSON, current_is_array


# ── Typedef builder ──────────────────────────────────────────────────────────────


def _typedef_from_struct(struct: Struct, parent: Module) -> TypeDef:
    typedef = TypeDef(parent=parent, name=struct.name, struct_type=struct.struct_type)
    for item in struct.body:
        if isinstance(item, Field):
            nested_ref = ""
            json_ref = ""
            is_array = False
            if item.ret == VariableType.NESTED:
                nested_expr = [i for i in item.body if isinstance(i, Nested)][0]
                nested_ref = nested_expr.struct_name
                is_array = nested_expr.is_array
            elif item.ret == VariableType.JSON:
                jsonify_expr = [i for i in item.body if isinstance(i, Jsonify)][0]
                json_ref = jsonify_expr.schema_name
                is_array = jsonify_expr.is_array
            typedef.body.append(
                TypeDefField(
                    parent=typedef, ret=item.ret, name=item.name,
                    nested_ref=nested_ref, json_ref=json_ref, is_array=is_array,
                )
            )
        elif isinstance(item, (Key, Value)):
            field_name = "key" if isinstance(item, Key) else "value"
            nested_ref = ""
            json_ref = ""
            is_array = False
            if item.ret == VariableType.NESTED:
                nested_expr = [i for i in item.body if isinstance(i, Nested)][0]
                nested_ref = nested_expr.struct_name
                is_array = nested_expr.is_array
            elif item.ret == VariableType.JSON:
                jsonify_expr = [i for i in item.body if isinstance(i, Jsonify)][0]
                json_ref = jsonify_expr.schema_name
                is_array = jsonify_expr.is_array
            typedef.body.append(
                TypeDefField(
                    parent=typedef, ret=item.ret, name=field_name,
                    nested_ref=nested_ref, json_ref=json_ref, is_array=is_array,
                )
            )
    return typedef


# ── JSON fields parser ───────────────────────────────────────────────────────────


def _parse_json_fields(nodes: list[KdlNode], parent: JsonDef) -> None:
    for node in nodes:
        name = node.name
        type_ = str(node.args[0].value) if node.args else ""
        is_array = type_.startswith("(array)")
        type_ = type_.removeprefix("(array)")
        is_optional = type_.endswith("?")
        type_ = type_.rstrip("?")
        ref_name = ""
        match type_:
            case "str":
                ret_type = VariableType.OPT_STRING if is_optional else (VariableType.LIST_STRING if is_array else VariableType.STRING)
            case "int":
                ret_type = VariableType.OPT_INT if is_optional else (VariableType.LIST_INT if is_array else VariableType.INT)
            case "float":
                ret_type = VariableType.OPT_FLOAT if is_optional else (VariableType.LIST_FLOAT if is_array else VariableType.FLOAT)
            case "bool":
                ret_type = VariableType.BOOL
            case "null":
                ret_type = VariableType.NULL
            case _:
                ref_name = str(node.args[0].value) if node.args else ""
                if ref_name.startswith("(array)"):
                    ref_name = ref_name.removeprefix("(array)")
                    is_array = True
                ret_type = VariableType.JSON
        alias = str(node.args[1].value) if len(node.args) > 1 else ""
        skip = False
        may_miss = False
        for arg in node.args[2:]:
            arg_s = str(arg.value)
            if arg_s == "@skip":
                skip = True
            elif arg_s == "@missing":
                may_miss = True
            elif arg_s == "@optional":
                is_optional = True
        if alias.startswith("@"):
            if alias == "@skip":
                skip = True
            elif alias == "@missing":
                may_miss = True
            elif alias == "@optional":
                is_optional = True
            alias = ""
        doc = str(node.properties.get("doc", KdlArg(value="", span=node.span, is_identifier=False)).value)
        parent.body.append(
            JsonDefField(
                parent=parent, ret=ret_type, name=name,
                is_optional=is_optional, is_array=is_array,
                ref_name=ref_name, alias=alias, skip=skip,
                may_miss=may_miss, doc=doc,
            )
        )


# ── Struct parsing ───────────────────────────────────────────────────────────────


def _parse_struct(
    kdl_nodes: list[KdlNode],
    parent: Struct,
    ctx: _ParseContext,
    lint: _LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = _WalkCtx.STRUCT_BODY
    for node in kdl_nodes:
        if node.name == "@doc":
            parent.docstring.value = str(node.args[0].value)
        elif node.name == "@init":
            expr = parent.init
            _parse_init_fields(node.children, expr, ctx, lint)
        elif node.name == "@pre-validate":
            expr = PreValidate(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@check":
            if not node.args:
                raise ParseError("@check requires a name: @check <name> { ... }")
            check_name = str(node.args[0].value)
            expr = CheckMethod(parent=parent, name=check_name)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@split-doc":
            expr = SplitDoc(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@key":
            expr = Key(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@value":
            expr = Value(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@table":
            expr = TableConfig(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@rows":
            expr = TableRow(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@match":
            expr = TableMatchKey(parent=parent)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@request":
            if not node.args:
                raise ParseError("@request requires a multiline string argument")
            raw_payload = str(
                ctx.property_defines.get(node.args[0].value, node.args[0].value)
            )
            req = RequestConfig(parent=parent)
            req.raw_payload = raw_payload
            req.response_path = str(
                node.properties.get("response-path", KdlArg(value="", span=node.span, is_identifier=False)).value
            )
            req.response_join = str(
                node.properties.get("response-join", KdlArg(value="", span=node.span, is_identifier=False)).value
            )
            req.name = str(
                node.properties.get("name", KdlArg(value="", span=node.span, is_identifier=False)).value
            )
            response_schema = node.properties.get("response", KdlArg(value="", span=node.span, is_identifier=False))
            req.response_schema = str(
                ctx.property_defines.get(response_schema.value, response_schema.value)
            )
            doc_val = node.properties.get("doc", KdlArg(value="", span=node.span, is_identifier=False))
            req.doc = str(ctx.property_defines.get(doc_val.value, doc_val.value))
            parent.body.append(req)
        elif node.name == "@error":
            if not node.args or len(node.args) < 2:
                raise ParseError("@error requires both status and schema name")
            status_raw = node.args[0].value
            try:
                status_int = int(status_raw)
            except (TypeError, ValueError):
                raise ParseError(f"@error status must be integer, got {status_raw!r}")
            schema_name = str(
                ctx.property_defines.get(node.args[1].value, node.args[1].value)
            )
            conditions: dict[str, Any] = {}
            for k, v in node.properties.items():
                key = str(ctx.property_defines.get(k.value, k.value))
                val = ctx.property_defines.get(v.value, v.value)
                conditions[key] = val
            err = ErrorResponse(
                parent=parent, status=status_int,
                schema_name=schema_name, conditions=conditions,
            )
            parent.body.append(err)
        else:
            if parent.struct_type == StructType.TABLE:
                expr = Field(parent=parent, name=node.name, accept=VariableType.STRING)
            else:
                expr = Field(parent=parent, name=node.name)
            _parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)

    if parent.struct_type != StructType.REST:
        parent.body.append(StartParse(parent=parent))
    lint.walk_context = prev_ctx


def _parse_init_fields(
    kdl_nodes: list[KdlNode],
    parent: Init,
    ctx: _ParseContext,
    lint: _LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = _WalkCtx.INIT_BLOCK
    for node in kdl_nodes:
        lint.push(node.name)
        lint.init_fields.add(node.name)
        expr = InitField(parent=parent, name=node.name)
        _parse_expressions(node.children, expr, ctx, lint)
        if expr.body:
            expr.ret = expr.body[-1].ret
            # type-check init sub-pipeline for self-reference inference
            ops = list(node.children)
            ret = _check_pipeline_types(ops, ctx, lint, start_type=VariableType.DOCUMENT)
            lint.inferred_define_types[node.name] = (VariableType.DOCUMENT, ret)
        parent.body.append(expr)
        lint.pop()
    lint.walk_context = prev_ctx


# ── Filter / Assert / Match expression parsing ───────────────────────────────────


def _parse_filter_expr(
    kdl_nodes: list[KdlNode],
    parent: Filter | LogicAnd | LogicNot | LogicOr,
    ctx: _ParseContext,
    lint: _LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "filter"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            _parse_filter_expr(ctx.children_defines[node.name], parent, ctx, lint)
            continue
        _lint_predicate_op(node, lint)
        expr = _build_filter_predicate(node, parent, ctx, lint)
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            _parse_filter_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


def _parse_assert_expr(
    kdl_nodes: list[KdlNode],
    parent: Assert | LogicAnd | LogicNot | LogicOr,
    ctx: _ParseContext,
    lint: _LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "assert"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            _parse_assert_expr(ctx.children_defines[node.name], parent, ctx, lint)
            continue
        _lint_predicate_op(node, lint)
        expr = _build_assert_predicate(node, parent, ctx, lint)
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            _parse_assert_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


def _parse_match_expr(
    kdl_nodes: list[KdlNode],
    parent: Match | LogicAnd | LogicNot | LogicOr,
    ctx: _ParseContext,
    lint: _LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "match"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            _parse_match_expr(ctx.children_defines[node.name], parent, ctx, lint)
            continue
        _lint_predicate_op(node, lint)
        expr = _build_match_predicate(node, parent, ctx, lint)
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            _parse_match_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


# ── Expression dispatch ──────────────────────────────────────────────────────────


def _build_expression(
    node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext
) -> AstNode:
    name = node.name

    # block define inlining
    if name in ctx.children_defines:
        for child in ctx.children_defines[name]:
            _build_expression(child, parent, ctx, lint)
        return parent.body[-1] if parent.body else parent

    # @<name> references
    if name.startswith("@") and name not in {
        "@doc", "@init", "@pre-validate", "@split-doc",
        "@key", "@value", "@table", "@rows", "@match",
    }:
        field_name = name[1:]
        struct = parent.parent
        if not isinstance(struct, Struct):
            raise BuildTimeError(f"@{field_name} outside of struct context")
        init_field = next(
            (i for i in struct.init.body if isinstance(i, InitField) and i.name == field_name),
            None,
        )
        if init_field is None:
            raise BuildTimeError(
                f"Unknown @init reference '@{field_name}' in {type(parent).__name__}"
            )
        prev_type = init_field.ret
        return Self(parent=parent, accept=prev_type, ret=prev_type, name=field_name)

    if name == "self":
        ref_name = str(node.args[0].value) if node.args else "<name>"
        raise BuildTimeError(f"'self {ref_name}' syntax is no longer supported; use '@{ref_name}' instead")

    # dispatch
    handler = _EXPRESSION_HANDLERS.get(name)
    if handler is None:
        raise BuildTimeError(f"Unknown expression: {name}")
    return handler(node, parent, ctx, lint)


def _parse_expressions(
    kdl_nodes: list[KdlNode],
    parent: FieldLikeNode,
    ctx: _ParseContext,
    lint: _LintContext,
    *,
    _add_return: bool = True,
) -> None:
    if not kdl_nodes:
        return
    prev_ctx = lint.walk_context
    lint.walk_context = _WalkCtx.PIPELINE
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            lint.push(node.name)
            _parse_expressions(ctx.children_defines[node.name], parent, ctx, lint, _add_return=False)
            lint.pop()
            continue
        if node.name.startswith("@") and node.name not in {
            "@doc", "@init", "@pre-validate", "@split-doc",
            "@key", "@value", "@table", "@rows", "@match",
        }:
            field_name = node.name[1:]
            struct = parent.parent
            if not isinstance(struct, Struct):
                raise BuildTimeError(f"@{field_name} outside of struct context")
            init_field = next(
                (i for i in struct.init.body if isinstance(i, InitField) and i.name == field_name),
                None,
            )
            if init_field is None:
                raise BuildTimeError(
                    f"Unknown @init reference '@{field_name}' in {type(parent).__name__}"
                )
            prev_type = init_field.ret
            expr = Self(parent=parent, accept=prev_type, ret=prev_type, name=field_name)
            parent.body.append(expr)
            continue
        if node.name == "self":
            ref_name = str(node.args[0].value) if node.args else "<name>"
            raise BuildTimeError(f"'self {ref_name}' syntax is no longer supported; use '@{ref_name}' instead")
        handler = _EXPRESSION_HANDLERS.get(node.name)
        if handler is None:
            _lint_wildcard_op(node, ctx, lint)
            raise BuildTimeError(f"Unknown expression: {node.name}")
        lint.push(node.name)
        _lint_pipeline_op(node, lint)
        expr = handler(node, parent, ctx, lint)
        if isinstance(expr, Fallback):
            lint.pop()
            continue
        elif isinstance(expr, Filter):
            _parse_filter_expr(node.children, expr, ctx, lint)
        elif isinstance(expr, Assert):
            _parse_assert_expr(node.children, expr, ctx, lint)
        elif isinstance(expr, Match):
            _parse_match_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
        lint.pop()

    if _add_return and parent.body:
        last_ret = parent.body[-1].ret
        parent.body.append(Return(parent=parent, ret=last_ret, accept=last_ret))
        parent.ret = last_ret
    lint.walk_context = prev_ctx


# ── Expression handlers ─────────────────────────────────────────────────────────

_ExpressionHandler = Callable[[KdlNode, FieldLikeNode, _ParseContext, _LintContext], AstNode]
_EXPRESSION_HANDLERS: dict[str, _ExpressionHandler] = {}


def _reg_expr(name: str):
    def decorator(fn: _ExpressionHandler) -> _ExpressionHandler:
        _EXPRESSION_HANDLERS[name] = fn
        return fn
    return decorator


# -- selectors ----------------------------------------------------------------


@_reg_expr("css")
def _expr_css(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if node.children:
        queries = [_resolve_selector_child_name(c.name, ctx) for c in node.children]
        return CssSelect(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0].value, ctx)
    _lint_validate_css(node, lint, query)
    return CssSelect(parent=parent, query=query)


@_reg_expr("css-all")
def _expr_css_all(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if node.children:
        queries = [_resolve_selector_child_name(c.name, ctx) for c in node.children]
        return CssSelectAll(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0].value, ctx)
    _lint_validate_css(node, lint, query)
    return CssSelectAll(parent=parent, query=query)


@_reg_expr("xpath")
def _expr_xpath(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if node.children:
        queries = [_resolve_selector_child_name(c.name, ctx) for c in node.children]
        return XpathSelect(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0].value, ctx)
    _lint_validate_xpath(node, lint, query)
    return XpathSelect(parent=parent, query=query)


@_reg_expr("xpath-all")
def _expr_xpath_all(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if node.children:
        queries = [_resolve_selector_child_name(c.name, ctx) for c in node.children]
        return XpathSelectAll(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0].value, ctx)
    _lint_validate_xpath(node, lint, query)
    return XpathSelectAll(parent=parent, query=query)


@_reg_expr("css-remove")
def _expr_css_remove(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    _lint_validate_css(node, lint, cast(str, query))
    return CssRemove(parent=parent, query=cast(str, query))


@_reg_expr("xpath-remove")
def _expr_xpath_remove(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    _lint_validate_xpath(node, lint, cast(str, query))
    return XpathRemove(parent=parent, query=cast(str, query))


# -- extract --------------------------------------------------------------------


@_reg_expr("text")
def _expr_text(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret if parent.body else VariableType.DOCUMENT
    ret_type = VariableType.LIST_STRING if prev_type == VariableType.LIST_DOCUMENT else VariableType.STRING
    return Text(parent=parent, accept=prev_type, ret=ret_type)


@_reg_expr("raw")
def _expr_raw(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret if parent.body else VariableType.DOCUMENT
    ret_type = VariableType.LIST_STRING if prev_type == VariableType.LIST_DOCUMENT else VariableType.STRING
    return Raw(parent=parent, accept=prev_type, ret=ret_type)


@_reg_expr("attr")
def _expr_attr(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret if parent.body else VariableType.DOCUMENT
    ret_type = VariableType.LIST_STRING if prev_type == VariableType.LIST_DOCUMENT else VariableType.STRING
    return Attr(parent=parent, accept=prev_type, ret=ret_type, keys=tuple(a.value for a in node.args))


# -- string ---------------------------------------------------------------------


@_reg_expr("trim")
def _expr_trim(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value)) if node.args else ""
    prev_type = parent.body[-1].ret
    return Trim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@_reg_expr("ltrim")
def _expr_ltrim(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value)) if node.args else ""
    prev_type = parent.body[-1].ret
    return Ltrim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@_reg_expr("rtrim")
def _expr_rtrim(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value)) if node.args else ""
    prev_type = parent.body[-1].ret
    return Rtrim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@_reg_expr("normalize-space")
def _expr_norm_space(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    return NormalizeSpace(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("rm-prefix")
def _expr_rm_prefix(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev_type = parent.body[-1].ret
    return RmPrefix(parent=parent, accept=prev_type, ret=prev_type, substr=cast(str, substr))


@_reg_expr("rm-suffix")
def _expr_rm_suffix(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev_type = parent.body[-1].ret
    return RmSuffix(parent=parent, accept=prev_type, ret=prev_type, substr=cast(str, substr))


@_reg_expr("rm-prefix-suffix")
def _expr_rm_prefix_suffix(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev_type = parent.body[-1].ret
    return RmPrefixSuffix(parent=parent, accept=prev_type, ret=prev_type, substr=cast(str, substr))


@_reg_expr("fmt")
def _expr_fmt(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    tmpl = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev_type = parent.body[-1].ret
    return Fmt(parent=parent, accept=prev_type, ret=prev_type, template=cast(str, tmpl))


@_reg_expr("repl")
def _expr_repl(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    if node.children:
        items = {str(child.name): str(child.args[0].value) for child in node.children}
        return ReplMap(parent=parent, accept=prev_type, ret=prev_type, replacements=items)
    old = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value))
    new = cast(str, ctx.property_defines.get(node.args[1].value, node.args[1].value))
    return Repl(parent=parent, accept=prev_type, ret=prev_type, old=old, new=new)


@_reg_expr("lower")
def _expr_lower(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    return Lower(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("upper")
def _expr_upper(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    return Upper(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("split")
def _expr_split(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    sep = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value))
    return Split(parent=parent, sep=sep)


@_reg_expr("join")
def _expr_join(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    sep = cast(str, ctx.property_defines.get(node.args[0].value, node.args[0].value))
    return Join(parent=parent, sep=sep)


@_reg_expr("unescape")
def _expr_unescape(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    return Unescape(parent=parent, accept=prev_type, ret=prev_type)


# -- regex ----------------------------------------------------------------------


@_reg_expr("re")
def _expr_re(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.body[-1].ret
    return Re(parent=parent, pattern=pattern, accept=prev_type, ret=prev_type)


@_reg_expr("re-all")
def _expr_re_all(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    return ReAll(parent=parent, pattern=pattern)


@_reg_expr("re-sub")
def _expr_re_sub(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    repl = cast(str, ctx.property_defines.get(node.args[1].value, node.args[1].value))
    return ReSub(parent=parent, accept=prev_type, ret=prev_type, pattern=pattern, repl=repl)


# -- array ----------------------------------------------------------------------


@_reg_expr("index")
def _expr_index(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=int(node.args[0].value), accept=accept, ret=ret)


@_reg_expr("first")
def _expr_first(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=0, accept=accept, ret=ret)


@_reg_expr("last")
def _expr_last(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=-1, accept=accept, ret=ret)


@_reg_expr("slice")
def _expr_slice(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    start, end = int(node.args[0].value), int(node.args[1].value)
    if parent.body:
        prev_type = parent.body[-1].ret
        return Slice(parent=parent, start=start, end=end, accept=prev_type, ret=prev_type)
    return Slice(parent=parent, start=start, end=end)


@_reg_expr("len")
def _expr_len(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    return Len(parent=parent)


@_reg_expr("unique")
def _expr_unique(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    keep_order = bool(node.properties.get("keep-order", KdlArg(value=False, span=node.span, is_identifier=False)).value)
    return Unique(parent=parent, keep_order=keep_order)


# -- casts ----------------------------------------------------------------------


@_reg_expr("to-int")
def _expr_to_int(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    ret_type = VariableType.LIST_INT if prev_type == VariableType.LIST_STRING else VariableType.INT
    return ToInt(parent=parent, accept=prev_type, ret=ret_type)


@_reg_expr("to-float")
def _expr_to_float(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    ret_type = VariableType.LIST_FLOAT if prev_type == VariableType.LIST_STRING else VariableType.FLOAT
    return ToFloat(parent=parent, accept=prev_type, ret=ret_type)


@_reg_expr("to-bool")
def _expr_to_bool(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    prev_type = parent.body[-1].ret
    return ToBool(parent=parent, accept=prev_type)


@_reg_expr("jsonify")
def _expr_jsonify(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    schema_name = str(node.args[0].value)
    path = str(node.properties.get("path", KdlArg(value="", span=node.span, is_identifier=False)).value)
    json_def = ctx.json_defs.get(schema_name)
    if json_def is None:
        raise ParseError(f"jsonify: JSON schema '{schema_name}' not found")
    ret_type, is_array = _resolve_jsonify_type(json_def, path, ctx)
    return Jsonify(parent=parent, schema_name=schema_name, path=path, ret=ret_type, is_array=is_array)


@_reg_expr("nested")
def _expr_nested(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    struct_name = str(node.args[0].value)
    struct = ctx.structs.get(struct_name)
    if struct is None:
        raise ParseError(f"nested: struct '{struct_name}' not found")
    is_array = struct.struct_type in (StructType.FLAT, StructType.LIST)
    return Nested(parent=parent, struct_name=struct_name, is_array=is_array)


# -- control --------------------------------------------------------------------


@_reg_expr("fallback")
def _expr_fallback(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    value = [] if not node.args else node.args[0].value
    prev_type = parent.body[-1].ret
    if value is None:
        prev_type = prev_type.optional
    start_default = FallbackStart(parent=parent, value=value)
    end_default = FallbackEnd(parent=parent, value=value, accept=prev_type, ret=prev_type)
    parent.body.insert(0, start_default)
    parent.body.append(end_default)
    return Fallback(parent=parent, value=value)


@_reg_expr("filter")
def _expr_filter(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if not parent.body:
        return Filter(parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.DOCUMENT)
    prev_type = parent.body[-1].ret
    return Filter(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("assert")
def _expr_assert(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    if isinstance(parent, PreValidate) and not parent.body:
        return Assert(parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.NULL)
    if not parent.body:
        return Assert(parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.DOCUMENT)
    prev_type = parent.body[-1].ret
    return Assert(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("match")
def _expr_match(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    return Match(parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.STRING)


@_reg_expr("transform")
def _expr_transform(node: KdlNode, parent: FieldLikeNode, ctx: _ParseContext, lint: _LintContext):
    name = str(node.args[0].value)
    if name not in ctx.transforms:
        raise BuildTimeError(f"transform '{name}' is not defined")
    transform_def = ctx.transforms[name]
    prev_type = parent.body[-1].ret
    if prev_type != transform_def.accept:
        raise BuildTimeError(
            f"transform '{name}': pipeline type {prev_type.name!r} "
            f"does not match accept type {transform_def.accept.name!r}"
        )
    current = parent
    while current and not isinstance(current, Module):
        current = current.parent
    if current and isinstance(current, Module):
        for target in transform_def.body:
            if target.lang not in current.imports.transform_imports:
                current.imports.transform_imports[target.lang] = set()
            current.imports.transform_imports[target.lang].update(target.imports)
    return TransformCall(
        parent=parent, name=name,
        accept=transform_def.accept, ret=transform_def.ret,
        transform_def=transform_def,
    )


# -- predicate helpers -----------------------------------------------------------

def _build_filter_predicate(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext) -> AstNode:
    return _FILTER_DISPATCH.get(node.name, _unknown_pred)(node, parent, ctx, lint)


def _build_assert_predicate(node: KdlNode, parent: Assert, ctx: _ParseContext, lint: _LintContext) -> AstNode:
    return _ASSERT_DISPATCH.get(node.name, _unknown_pred)(node, parent, ctx, lint)


def _build_match_predicate(node: KdlNode, parent: Match, ctx: _ParseContext, lint: _LintContext) -> AstNode:
    return _MATCH_DISPATCH.get(node.name, _unknown_pred)(node, parent, ctx, lint)


def _unknown_pred(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext) -> AstNode:
    raise BuildTimeError(f"Unknown predicate: {node.name}")


def _pred_prev(node: KdlNode, parent: Any) -> VariableType:
    return parent.ret


# -- filter predicates ----------------------------------------------------------

def _p_eq(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredEq(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_ne(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredNe(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_gt(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredGt(parent=parent, value=node.args[0].value, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_lt(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredLt(parent=parent, value=node.args[0].value, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_ge(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredGe(parent=parent, value=node.args[0].value, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_le(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredLe(parent=parent, value=node.args[0].value, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_range(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredRange(parent=parent, start=int(node.args[0].value), end=int(node.args[1].value), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_starts(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredStarts(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_ends(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredEnds(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_contains(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredContains(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_in(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredIn(parent=parent, values=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_re(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredRe(parent=parent, pattern=normalize_regex_pattern(raw), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_re_all(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredReAll(parent=parent, pattern=normalize_regex_pattern(raw), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_re_any(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredReAny(parent=parent, pattern=normalize_regex_pattern(raw), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_css(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredCss(parent=parent, query=cast(str, query), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_xpath(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredXpath(parent=parent, query=cast(str, query), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_has_attr(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredHasAttr(parent=parent, attrs=tuple(a.value for a in node.args), accept=_pred_prev(node, parent), ret=parent.ret)

def _p_attr_eq(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredAttrEq(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args[1:]), name=node.args[0].value)

def _p_attr_ne(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredAttrNe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args[1:]), name=node.args[0].value)

def _p_attr_contains(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredAttrContains(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args[1:]), name=node.args[0].value)

def _p_attr_re(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[1].value, node.args[1].value)
    return PredAttrRe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, pattern=normalize_regex_pattern(raw), name=node.args[0].value)

def _p_attr_starts(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredAttrStarts(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args[1:]), name=node.args[0].value)

def _p_attr_ends(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredAttrEnds(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args[1:]), name=node.args[0].value)

def _p_text_contains(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredTextContains(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args))

def _p_text_ends(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredTextEnds(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args))

def _p_text_starts(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    return PredTextStarts(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, values=tuple(a.value for a in node.args))

def _p_text_re(node: KdlNode, parent: Filter, ctx: _ParseContext, lint: _LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredTextRe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, pattern=normalize_regex_pattern(raw))

# len-* predicates (assert scope)
def _p_len_eq(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountEq(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_gt(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountGt(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_lt(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountLt(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_ne(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountNe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_ge(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountGe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_le(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountLe(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, value=int(node.args[0].value))

def _p_len_range(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return PredCountRange(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret, start=int(node.args[0].value), end=int(node.args[1].value))

def _p_and(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return LogicAnd(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_not(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return LogicNot(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret)

def _p_or(node: KdlNode, parent: Any, ctx: _ParseContext, lint: _LintContext):
    return LogicOr(parent=parent, accept=_pred_prev(node, parent), ret=parent.ret)


# predicate dispatch tables
_COMMON_PREDS = {
    "eq": _p_eq, "ne": _p_ne, "gt": _p_gt, "lt": _p_lt, "ge": _p_ge, "le": _p_le,
    "range": _p_range, "starts": _p_starts, "ends": _p_ends, "contains": _p_contains,
    "in": _p_in, "and": _p_and, "or": _p_or, "not": _p_not,
}

_FILTER_DISPATCH: dict[str, Callable] = {
    **_COMMON_PREDS,
    "re": _p_re, "css": _p_css, "xpath": _p_xpath, "has-attr": _p_has_attr,
    "attr-eq": _p_attr_eq, "attr-ne": _p_attr_ne, "attr-contains": _p_attr_contains,
    "attr-re": _p_attr_re, "attr-starts": _p_attr_starts, "attr-ends": _p_attr_ends,
    "text-contains": _p_text_contains, "text-ends": _p_text_ends,
    "text-starts": _p_text_starts, "text-re": _p_text_re,
}

_ASSERT_DISPATCH: dict[str, Callable] = {
    **_FILTER_DISPATCH,
    "re-all": _p_re_all, "re-any": _p_re_any,
    "len-eq": _p_len_eq, "len-gt": _p_len_gt, "len-lt": _p_len_lt,
    "len-ne": _p_len_ne, "len-ge": _p_len_ge, "len-le": _p_len_le,
    "len-range": _p_len_range,
}

_MATCH_DISPATCH: dict[str, Callable] = {
    "eq": _p_eq, "ne": _p_ne, "starts": _p_starts, "ends": _p_ends,
    "contains": _p_contains, "in": _p_in, "re": _p_re,
    "and": _p_and, "or": _p_or, "not": _p_not,
}


# ── Lint helpers ──────────────────────────────────────────────────────────────────


def _lint_require_args(
    node: KdlNode,
    lint: _LintContext,
    *,
    exact: int | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    example: str = "",
) -> list[str] | None:
    args = lint.get_args(node)
    name = lint.node_name(node)
    count = len(args)

    if exact is not None and count != exact:
        noun = "argument" if exact == 1 else "arguments"
        lint.error(
            node,
            message=f"'{name}' requires exactly {exact} {noun}, got {count}",
            code="E001",
            hint=example,
        )
        return None

    if min_count is not None and count < min_count:
        noun = "argument" if min_count == 1 else "arguments"
        lint.error(
            node,
            message=f"'{name}' requires at least {min_count} {noun}, got {count}",
            code="E001",
            hint=example,
        )
        return None

    if max_count is not None and count > max_count:
        lint.error(
            node,
            message=f"'{name}' allows at most {max_count} argument(s), got {count}",
            code="E001",
            hint=example,
        )
        return None

    return args


def _lint_require_int_args(
    node: KdlNode, lint: _LintContext, args: list[str]
) -> bool:
    name = lint.node_name(node)
    for arg in args:
        try:
            int(arg)
        except ValueError:
            lint.error(
                node,
                message=f"'{name}' arguments must be integers, got '{arg}'",
                code="E001",
                hint=f"example: {name} 0",
            )
            return False
    return True


def _lint_validate_regex(node: KdlNode, lint: _LintContext, pattern: str) -> bool:
    try:
        _re.compile(pattern.lstrip())
        return True
    except _re.error as e:
        lint.error(
            node,
            message=f"invalid regex pattern: {e.msg}",
            code="E002",
            hint="check regex syntax",
        )
        return False


def _lint_validate_css(node: KdlNode, lint: _LintContext, selector: str) -> bool:
    try:
        import soupsieve
        soupsieve.compile(selector)
        return True
    except Exception as e:
        msg = str(e).split("\n")[0] if str(e) else "invalid selector"
        lint.error(
            node,
            message=f"invalid CSS selector: {msg}",
            code="E002",
            hint="check selector syntax",
        )
        return False


def _lint_validate_xpath(node: KdlNode, lint: _LintContext, expr: str) -> bool:
    try:
        from lxml import etree
        etree.XPath(expr)
        return True
    except Exception as e:
        msg = str(e).split("\n")[0] if str(e) else "invalid expression"
        lint.error(
            node,
            message=f"invalid XPath expression: {msg}",
            code="E002",
            hint="check XPath syntax",
        )
        return False


_NO_ARGS_OPS: frozenset[str] = frozenset(
    {
        "text", "raw", "normalize-space", "lower", "upper", "unescape",
        "first", "last", "len", "unique",
        "to-int", "to-float", "to-bool",
    }
)

_TRIM_OPS: frozenset[str] = frozenset({"trim", "ltrim", "rtrim"})
_RM_OPS: frozenset[str] = frozenset({"rm-prefix", "rm-suffix", "rm-prefix-suffix"})
_PREDICATE_BLOCKS: frozenset[str] = frozenset(
    {"filter", "assert", "match", "not", "and", "or"}
)


def _lint_require_predicate_ctx(node: KdlNode, lint: _LintContext) -> bool:
    if lint.in_predicate:
        return True
    name = lint.node_name(node)
    blocks = ", ".join(sorted(_PREDICATE_BLOCKS))
    lint.error(
        node,
        message=f"'{name}' is only valid inside a predicate block",
        code="E203",
        hint=f"wrap it in one of: {blocks}. Example: filter {{ {name} ... }}",
    )
    return False


def _lint_require_assert_ctx(node: KdlNode, lint: _LintContext) -> bool:
    if lint.in_assert:
        return True
    name = lint.node_name(node)
    lint.error(
        node,
        message=f"'{name}' is only valid inside an assert block",
        code="E203",
        hint=f"example: assert {{ {name} ... }}",
    )
    return False


def _lint_pipeline_op(node: KdlNode, lint: _LintContext) -> None:
    """Validate a single pipeline operation node."""
    name = lint.node_name(node)

    # no-args ops
    if name in _NO_ARGS_OPS:
        if lint.get_args(node):
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"remove arguments: use just '{name}'",
            )
        return

    if name == "attr":
        _lint_require_args(node, lint, min_count=1, example='attr "href"')

    elif name in _TRIM_OPS:
        args = lint.get_args(node)
        if len(args) > 1:
            lint.error(
                node,
                message=f"'{name}' accepts at most 1 argument",
                code="E001",
                hint=f'example: {name}  or  {name} "chars"',
            )

    elif name in _RM_OPS:
        _lint_require_args(node, lint, exact=1, example=f'{name} "substring"')

    elif name == "fmt":
        args = _lint_require_args(node, lint, exact=1, example='fmt "prefix-{{}}-suffix"')
        if args and not (args[0].isupper() or "{{}}" in args[0]):
            lint.error(
                node,
                message="'fmt' template is missing the '{{}}' placeholder",
                code="E001",
                hint=f'add placeholder to template, example: fmt "{args[0]}{{}}"',
            )

    elif name == "repl":
        children = lint.get_children_nodes(node)
        args = lint.get_args(node)
        if not args and not children:
            lint.error(
                node,
                message="'repl' requires 2 arguments or a children block",
                code="E001",
                hint='example: repl "old" "new"  or  repl { "old" "new"; "foo" "bar" }',
            )
        elif args:
            _lint_require_args(node, lint, exact=2, example='repl "old" "new"')

    elif name in ("split", "join"):
        _lint_require_args(node, lint, exact=1, example=f'{name} " "')

    elif name == "re":
        raw_args = lint.get_raw_args(node)
        args = _lint_require_args(node, lint, exact=1, example=f'{name} #"(\\d+)"#')
        if args:
            pattern = args[0]
            if raw_args and raw_args[0].is_identifier:
                resolved = lint.resolve_scalar_arg(pattern)
                if resolved is not None:
                    pattern = resolved
            normalized = pattern.lstrip()
            if _lint_validate_regex(node, lint, normalized) and not lint.in_predicate:
                groups = _re.compile(normalized).groups
                if groups == 0:
                    lint.error(
                        node,
                        message=f"'{name}' pattern must have exactly one capture group",
                        code="E001",
                        hint=f'wrap the match in a group: {name} #"({pattern})"#',
                    )
                elif groups > 1:
                    lint.error(
                        node,
                        message=f"'{name}' pattern must have exactly one capture group, got {groups}",
                        code="E001",
                        hint="use a non-capturing group (?:...) for grouping without capturing",
                    )

    elif name == "re-all":
        if lint.in_predicate and not _lint_require_assert_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=1, example='re-all #"(\\d+)"#')
        if args:
            _lint_validate_regex(node, lint, args[0])

    elif name == "re-sub":
        args = _lint_require_args(node, lint, exact=2, example='re-sub #"\\D"# ""')
        if args:
            _lint_validate_regex(node, lint, args[0])

    elif name == "index":
        args = _lint_require_args(node, lint, exact=1, example="index 0")
        if args:
            _lint_require_int_args(node, lint, args)

    elif name == "slice":
        args = _lint_require_args(node, lint, exact=2, example="slice 0 10")
        if args:
            _lint_require_int_args(node, lint, args)

    elif name == "jsonify":
        _lint_require_args(node, lint, exact=1, example="jsonify MySchema")

    elif name == "nested":
        _lint_require_args(node, lint, exact=1, example="nested MyStruct")

    elif name == "self":
        args = _lint_require_args(node, lint, exact=1, example="self field-name")
        if args and args[0] not in lint.init_fields:
            lint.error(
                node,
                message=f"'self {args[0]}': field '{args[0]}' not found in @init block (deprecated syntax)",
                code="E301",
                hint=f"declare it in @init: @init {{ {args[0]} {{ ... }} }} or use new syntax: @{args[0]}",
            )

    elif name == "fallback":
        children = lint.get_children_nodes(node)
        args = lint.get_args(node)
        if not args and not children and lint.has_empty_block(node):
            pass  # empty block fallback is ok (for lists)
        elif not args and not children:
            lint.error(
                node,
                message="'fallback' requires exactly 1 argument or a block",
                code="E001",
                hint='example: fallback ""  or  fallback 0  or  fallback #null  or  fallback {}',
            )

    elif name in ("filter", "assert", "match"):
        if lint.get_args(node):
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"move expressions into the children block: {name} {{ ... }}",
            )
        if not lint.get_children_nodes(node) and lint.has_empty_block(node):
            lint.error(
                node,
                message=f"'{name}' block must contain at least one predicate expression",
                code="E001",
                hint=f'example: {name} {{ css ".item"; has-attr href }}',
            )

    elif name in ("not", "and", "or"):
        if lint.get_args(node):
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"move expressions into the children block: {name} {{ ... }}",
            )
        if not lint.get_children_nodes(node) and lint.has_empty_block(node):
            lint.error(
                node,
                message=f"'{name}' block must contain at least one predicate expression",
                code="E001",
                hint=f'example: {name} {{ starts "foo" }}',
            )

    # @init reference validation
    elif name.startswith("@") and name not in {
        "@doc", "@init", "@pre-validate", "@split-doc",
        "@key", "@value", "@table", "@rows", "@match",
    }:
        field_name = name[1:]
        if field_name not in lint.init_fields:
            lint.error(
                node,
                message=f"'@{field_name}': field '{field_name}' not found in @init block",
                code="E301",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
            )


def _lint_predicate_op(
    node: KdlNode, lint: _LintContext
) -> None:
    """Validate a predicate operation node inside filter/assert/match."""
    name = lint.node_name(node)

    # string predicates
    if name in ("eq", "ne"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        _lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("starts", "ends", "contains", "in"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        _lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("len-eq", "len-ne"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, min_count=1, example=f"{name} 5")
        if args:
            for arg in args:
                try:
                    val = int(arg)
                    if val < 0:
                        lint.error(
                            node,
                            message=f"'{name}' argument must be non-negative, got {val}",
                            code="E001",
                            hint=f"example: {name} 5",
                        )
                        return
                except ValueError:
                    lint.error(
                        node,
                        message=f"'{name}' argument must be integer, got '{arg}'",
                        code="E001",
                        hint=f"example: {name} 5",
                    )
                    return

    elif name in ("len-gt", "len-lt", "len-ge", "len-le"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=1, example=f"{name} 10")
        if args:
            _lint_require_int_args(node, lint, args)

    elif name == "len-range":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=2, example="len-range 1 100")
        if args:
            _lint_require_int_args(node, lint, args)

    elif name == "has-attr":
        if not _lint_require_predicate_ctx(node, lint):
            return
        _lint_require_args(node, lint, min_count=1, example='has-attr "href"')

    elif name in ("attr-eq", "attr-ne", "attr-starts", "attr-ends", "attr-contains"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        _lint_require_args(node, lint, min_count=2, example=f'{name} "href" "value"')

    elif name == "attr-re":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=2, example='attr-re "href" #".*\\.com$"#')
        if args:
            _lint_validate_regex(node, lint, args[1])

    elif name == "text-re":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=1, example='text-re #"\\d+"#')
        if args:
            _lint_validate_regex(node, lint, args[0])

    elif name in ("text-starts", "text-ends", "text-contains"):
        if not _lint_require_predicate_ctx(node, lint):
            return
        _lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name == "re-any":
        if not _lint_require_assert_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=1, example='re-any #"\\d+"#')
        if args:
            _lint_validate_regex(node, lint, args[0])

    elif name in ("gt", "lt", "ge", "le"):
        if not _lint_require_assert_ctx(node, lint):
            return
        _lint_require_args(node, lint, exact=1, example=f"{name} 42")

    elif name == "re":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=1, example='re #"(\\d+)"#')
        if args:
            _lint_validate_regex(node, lint, args[0])

    elif name == "css":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = lint.get_args(node)
        if args:
            selector = args[0]
            _lint_validate_css(node, lint, selector)

    elif name == "xpath":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = lint.get_args(node)
        if args:
            _lint_validate_xpath(node, lint, args[0])

    elif name == "range":
        if not _lint_require_predicate_ctx(node, lint):
            return
        args = _lint_require_args(node, lint, exact=2, example="range 1 100")
        if args:
            _lint_require_int_args(node, lint, args)


# ── Pipeline type checking ──────────────────────────────────────────────────────


_OP_TYPES: dict[str, list[tuple[VariableType | None, VariableType | None]]] = {
    "css": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "css-all": [(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)],
    "xpath": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "xpath-all": [(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)],
    "css-remove": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "xpath-remove": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "text": [(VariableType.DOCUMENT, VariableType.STRING), (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING)],
    "raw": [(VariableType.DOCUMENT, VariableType.STRING), (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING)],
    "attr": [(VariableType.DOCUMENT, VariableType.STRING), (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING)],
    "trim": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "ltrim": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "rtrim": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "normalize-space": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "fmt": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "repl": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "lower": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "upper": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "rm-prefix": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "rm-suffix": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "rm-prefix-suffix": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "unescape": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "split": [(VariableType.STRING, VariableType.LIST_STRING)],
    "join": [(VariableType.LIST_STRING, VariableType.STRING)],
    "re": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "re-all": [(VariableType.STRING, VariableType.LIST_STRING)],
    "re-sub": [(VariableType.STRING, VariableType.STRING), (VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "index": [(None, None)],
    "first": [(None, None)],
    "last": [(None, None)],
    "slice": [(None, None)],
    "len": [(None, VariableType.INT)],
    "unique": [(VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "to-int": [(VariableType.STRING, VariableType.INT), (VariableType.LIST_STRING, VariableType.LIST_INT)],
    "to-float": [(VariableType.STRING, VariableType.FLOAT), (VariableType.LIST_STRING, VariableType.LIST_FLOAT)],
    "to-bool": [(None, VariableType.BOOL)],
    "jsonify": [(VariableType.STRING, VariableType.JSON)],
    "nested": [(VariableType.DOCUMENT, VariableType.NESTED)],
    "match": [(VariableType.DOCUMENT, VariableType.STRING)],
}

_LIST_TO_SCALAR: frozenset[str] = frozenset({"index", "first", "last"})
_LIST_PRESERVE: frozenset[str] = frozenset({"slice"})


def _is_list_type(t: VariableType) -> bool:
    return t in (
        VariableType.LIST_AUTO, VariableType.LIST_DOCUMENT,
        VariableType.LIST_STRING, VariableType.LIST_INT, VariableType.LIST_FLOAT,
    )


def _vt_compatible(got: VariableType, expected: VariableType) -> bool:
    if got == expected:
        return True
    if got == VariableType.AUTO or expected == VariableType.AUTO:
        return not _is_list_type(got) and not _is_list_type(expected)
    if got == VariableType.LIST_AUTO or expected == VariableType.LIST_AUTO:
        return _is_list_type(got) or _is_list_type(expected)
    return False


def _resolve_op_ret(op: str, accept: VariableType) -> VariableType:
    pairs = _OP_TYPES.get(op)
    if not pairs:
        return VariableType.AUTO
    for pair_accept, pair_ret in pairs:
        if pair_accept is None or _vt_compatible(accept, pair_accept):
            if pair_ret is not None:
                return pair_ret
            if op in _LIST_TO_SCALAR:
                return accept.scalar
            if op in _LIST_PRESERVE:
                return accept
            return accept
    return VariableType.AUTO


def _type_mismatch_hint(op_name: str, got: VariableType) -> str:
    _needs_text = {
        "fmt", "trim", "ltrim", "rtrim", "lower", "upper", "re", "re-sub",
        "re-all", "to-int", "to-float", "split", "join", "normalize-space",
        "unescape", "rm-prefix", "rm-suffix", "rm-prefix-suffix",
    }
    if got in (VariableType.DOCUMENT, VariableType.LIST_DOCUMENT) and op_name in _needs_text:
        return "add 'text', 'raw', or 'attr' before this operation to extract a string"
    if _is_list_type(got) and op_name in ("css", "xpath", "css-all", "xpath-all"):
        return "selectors work on a single DOCUMENT, not a list"
    if op_name in ("index", "first", "last", "slice") and not _is_list_type(got):
        return f"'{op_name}' requires a LIST type, got {got.name}"
    if op_name in ("unique", "join") and got != VariableType.LIST_STRING:
        return f"'{op_name}' requires LIST_STRING, got {got.name}"
    if not _is_list_type(got) and op_name == "len":
        return "'len' counts elements of any list — produce a list first"
    if op_name == "split" and got != VariableType.STRING:
        return f"'split' requires STRING, got {got.name}"
    pairs = _OP_TYPES.get(op_name, [])
    valid = [a for a, _ in pairs if a is not None]
    if valid:
        return f"'{op_name}' accepts: {' | '.join(t.name for t in valid)}"
    return f"unexpected type {got.name} for '{op_name}'"


def _get_define_ops(define_name: str, ctx: _ParseContext, lint: _LintContext, _visiting: set[str] | None = None) -> list[KdlNode] | None:
    info = lint.defines.get(define_name)
    if info is None or info.kind != _DefineKind.BLOCK:
        return None
    if _visiting is None:
        _visiting = set()
    if define_name in _visiting:
        return None
    _visiting.add(define_name)
    result: list[KdlNode] = []
    for op_node in lint.get_children_nodes(info.node):
        op_nm = lint.node_name(op_node)
        if not op_nm:
            continue
        if op_nm in ctx.children_defines:
            nested = _get_define_ops(op_nm, ctx, lint, _visiting)
            if nested is None:
                _visiting.discard(define_name)
                return None
            result.extend(nested)
        else:
            result.append(op_node)
    _visiting.discard(define_name)
    return result


def _fallback_literal_type(node: KdlNode, lint: _LintContext) -> VariableType | None:
    if lint.get_children_nodes(node):
        return VariableType.LIST_AUTO
    raw_args = lint.get_raw_args(node)
    if not raw_args:
        return None
    raw = raw_args[0]
    val = raw.value
    if val in ("#true", "#false"):
        return VariableType.BOOL
    if val == "#null":
        return VariableType.NULL
    if not raw.is_identifier:
        if "." in val or "e" in val.lower():
            try:
                float(val)
                return VariableType.FLOAT
            except ValueError:
                return VariableType.STRING
        try:
            int(val)
            return VariableType.INT
        except ValueError:
            pass
        return VariableType.STRING
    return VariableType.STRING


def _check_pipeline_types(
    ops: list[KdlNode], ctx: _ParseContext, lint: _LintContext,
    start_type: VariableType = VariableType.DOCUMENT,
) -> VariableType:
    current = start_type
    for node in ops:
        op_name = lint.node_name(node)
        if not op_name:
            continue

        if op_name == "self":
            continue

        if op_name == "fallback":
            fb_type = _fallback_literal_type(node, lint)
            if fb_type is None:
                continue
            if fb_type == VariableType.LIST_AUTO:
                if not _is_list_type(current) and current != VariableType.LIST_AUTO:
                    lint.error(
                        node,
                        message=f"'fallback {{}}' is only valid for list types, got {current.name}",
                        code="E100",
                        hint="use 'css-all' or 'xpath-all' to produce a list",
                    )
                continue
            if fb_type == VariableType.NULL:
                if current not in (
                    VariableType.STRING, VariableType.INT, VariableType.FLOAT,
                    VariableType.AUTO, VariableType.OPT_STRING, VariableType.OPT_INT,
                    VariableType.OPT_FLOAT,
                ):
                    lint.error(
                        node,
                        message=f"'fallback #null' only valid for STRING/INT/FLOAT, got {current.name}",
                        code="E100",
                    )
                else:
                    current = current.optional
                continue
            if not _vt_compatible(current, fb_type) and current not in (VariableType.AUTO, VariableType.LIST_AUTO):
                lint.error(
                    node,
                    message=f"'fallback' type {fb_type.name} does not match pipeline {current.name}",
                    code="E100",
                    hint=f"use a {current.name.lower()} literal or #null",
                )
                continue
            current = fb_type
            continue

        if op_name == "transform":
            args = lint.get_args(node)
            t_name = args[0] if args else None
            if not t_name:
                lint.error(node, message="'transform' call requires a name", code="E100")
                current = VariableType.AUTO
                continue
            t_info = lint.transforms.get(t_name)
            if t_info is None:
                current = VariableType.AUTO
                continue
            t_accept = _VAR_TYPE_MAP.get(t_info.accept)
            t_ret = _VAR_TYPE_MAP.get(t_info.ret)
            if t_accept is not None and not _vt_compatible(current, t_accept):
                lint.error(
                    node,
                    message=f"'transform {t_name}' expects {t_accept.name}, got {current.name}",
                    code="E100",
                )
            current = t_ret if t_ret is not None else VariableType.AUTO
            continue

        if op_name == "filter":
            if not _is_list_type(current) and current not in (VariableType.AUTO, VariableType.LIST_AUTO):
                lint.error(
                    node,
                    message=f"'filter' requires a list type, got {current.name}",
                    code="E100",
                    hint="use 'css-all', 'xpath-all', 're-all', or 'split' first",
                )
            continue

        if op_name == "assert":
            continue

        if op_name == "match":
            if current != start_type:
                lint.error(
                    node,
                    message="'match' must be the first operation in the field pipeline",
                    code="E100",
                )
            elif not _vt_compatible(current, VariableType.DOCUMENT):
                lint.error(
                    node,
                    message=f"'match' requires DOCUMENT, got {current.name}",
                    code="E100",
                )
            current = _resolve_op_ret("match", current)
            continue

        # block define — inline expansion
        if op_name in ctx.children_defines or op_name in lint.defines:
            define_ops = _get_define_ops(op_name, ctx, lint)
            if define_ops:
                current = _check_pipeline_types(define_ops, ctx, lint, start_type=current)
            # scalar define as op — already reported by _lint_wildcard_op
            continue

        # regular op
        pairs = _OP_TYPES.get(op_name)
        if pairs is None:
            current = VariableType.AUTO
            continue
        accepted = [a for a, _ in pairs if a is not None]
        if accepted and not any(_vt_compatible(current, a) for a in accepted):
            lint.error(
                node,
                message=f"'{op_name}' does not accept {current.name}; expected {' | '.join(t.name for t in accepted)}",
                code="E100",
                hint=_type_mismatch_hint(op_name, current),
            )
            current = VariableType.AUTO
            continue
        current = _resolve_op_ret(op_name, current)
    return current


# ── Struct lint ──────────────────────────────────────────────────────────────────

_VALID_STRUCT_TYPES = frozenset({"item", "list", "dict", "table", "flat", "rest"})

_REQUIRED_RESERVED: dict[str, frozenset[str]] = {
    "item": frozenset(),
    "list": frozenset({"@split-doc"}),
    "dict": frozenset({"@split-doc", "@key", "@value"}),
    "table": frozenset({"@table", "@rows", "@match", "@value"}),
    "flat": frozenset(),
    "rest": frozenset({"@request"}),
}

_RESERVED_ALLOWED: dict[str, frozenset[str] | None] = {
    "@request": None,
    "@doc": None,
    "@pre-validate": frozenset({"item", "list", "dict", "table", "flat"}),
    "@check": frozenset({"item", "list", "dict", "table", "flat"}),
    "@init": frozenset({"item", "list", "dict", "table", "flat"}),
    "@split-doc": frozenset({"list", "dict"}),
    "@key": frozenset({"dict"}),
    "@value": frozenset({"dict", "table"}),
    "@table": frozenset({"table"}),
    "@rows": frozenset({"table"}),
    "@match": frozenset({"table"}),
    "@error": frozenset({"rest"}),
}

_VALID_TRANSFORM_TYPES = frozenset(
    {t.name for t in VariableType if t.name not in ("AUTO", "LIST_AUTO")}
)

_EXTRA_PIPELINE_OPS: frozenset[str] = frozenset(
    {"transform", "filter", "assert", "match", "fallback", "self", "not", "and", "or"}
)

_PREDICATE_OPS: frozenset[str] = frozenset(
    {
        "eq", "ne", "starts", "ends", "contains", "in",
        "len-eq", "len-ne", "len-gt", "len-lt", "len-ge", "len-le", "len-range",
        "has-attr", "attr-eq", "attr-ne", "attr-starts", "attr-ends",
        "attr-contains", "attr-re", "text-re", "text-starts", "text-ends",
        "text-contains", "re-any", "gt", "lt", "ge", "le",
    }
)

_KNOWN_OPS: frozenset[str] = (
    frozenset(_OP_TYPES.keys()) | _EXTRA_PIPELINE_OPS | _PREDICATE_OPS
)


def _lint_wildcard_op(node: KdlNode, ctx: _ParseContext, lint: _LintContext) -> None:
    """Validate unknown ops in pipeline context."""
    op_name = lint.node_name(node)
    if not op_name:
        return

    if op_name.startswith("@"):
        field_name = op_name[1:]
        if field_name not in lint.init_fields:
            lint.error(
                node,
                message=f"'@{field_name}': field '{field_name}' not found in @init block",
                code="E301",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
            )
        return

    info = lint.defines.get(op_name)
    if info is not None:
        if info.kind == _DefineKind.SCALAR:
            lint.error(
                node,
                message=f"'{op_name}' is a scalar define — cannot be used as a pipeline operation",
                code="E001",
                hint=f"use a block define: define {op_name} {{ ... }}",
            )
        return

    candidates = sorted(
        _KNOWN_OPS
        | {k for k, v in lint.defines.items() if v.kind == _DefineKind.BLOCK}
        | set(lint.transforms)
    )
    suggestions = _difflib.get_close_matches(op_name, candidates, n=3, cutoff=0.6)
    if suggestions:
        hint = "did you mean " + " or ".join(f"'{s}'" for s in suggestions) + "?"
    else:
        hint = f"check spelling or declare it: define {op_name} {{ ... }}"
    lint.error(
        node,
        message=f"unknown operation '{op_name}'",
        code="E200",
        hint=hint,
    )


def _lint_struct_node(
    node: KdlNode, module: Module, ctx: _ParseContext, lint: _LintContext
) -> None:
    """Validate struct-level rules."""
    struct_name = lint.get_arg(node, 0)
    if not struct_name:
        lint.error(node, message="'struct' requires a name", code="E001",
                   hint="example: struct MyStruct { ... }")
        return

    struct_type = lint.get_prop(node, "type") or "item"
    if struct_type not in _VALID_STRUCT_TYPES:
        lint.error(
            node,
            message=f"unknown struct type '{struct_type}'",
            code="E400",
            hint=f"valid types: {', '.join(sorted(_VALID_STRUCT_TYPES))}",
        )
        return

    fields = lint.get_children_nodes(node)
    reserved_present = {
        lint.node_name(f) for f in fields if lint.node_name(f).startswith("@")
    }

    missing = sorted(_REQUIRED_RESERVED[struct_type] - reserved_present)
    if missing:
        lint.error(
            node,
            message=f"struct type='{struct_type}' missing required field(s) " + ', '.join(missing),
            code="E401",
            hint=f"add: {', '.join(missing)}",
        )

    for field_node in fields:
        field_name = lint.node_name(field_node)
        if not field_name:
            continue
        if field_name.startswith("@"):
            _lint_reserved_field(field_node, field_name, struct_type, lint)
        else:
            if struct_type == "rest":
                lint.error(
                    field_node,
                    message=f"regular field '{field_name}' not allowed in struct type='rest'",
                    code="E203",
                )
            else:
                _lint_regular_field(field_node, field_name, ctx, lint, struct_type=struct_type)


def _lint_reserved_field(
    node: KdlNode, field_name: str, struct_type: str, lint: _LintContext
) -> None:
    allowed = _RESERVED_ALLOWED.get(field_name)
    if allowed is not None and struct_type not in allowed:
        lint.error(
            node,
            message=f"'{field_name}' not allowed in struct type='{struct_type}'",
            code="E203",
            hint=f"'{field_name}' only valid in: {', '.join(sorted(allowed))}",
        )
        return

    if field_name == "@doc":
        if not lint.get_arg(node, 0):
            lint.error(node, message="'@doc' requires a description string", code="E001")
    elif field_name == "@request":
        if not lint.get_arg(node, 0):
            lint.error(node, message="'@request' requires a raw HTTP string", code="E001")
    elif field_name == "@init":
        sub_pipelines = lint.get_children_nodes(node)
        if not sub_pipelines:
            lint.error(
                node,
                message="'@init' block must contain at least one named pipeline",
                code="E001",
                hint='@init {\n    my-field { css ".x"; text }\n}',
            )
    elif field_name == "@check":
        check_name = lint.get_args(node)
        check_name = check_name[0] if check_name else None
        ops = lint.get_children_nodes(node)
        if not ops:
            lint.error(
                node,
                message=f"@check {check_name or ''}block must contain at least one operation",
                code="E001",
            )
        elif not any(lint.node_name(o) == "to-bool" for o in ops):
            lint.error(
                node,
                message=f"@check {check_name or ''}must contain 'to-bool' to guarantee BOOL return type",
                code="E100",
            )


def _lint_regular_field(
    node: KdlNode, field_name: str, ctx: _ParseContext,
    lint: _LintContext, *, struct_type: str = "item",
) -> None:
    ops = lint.get_children_nodes(node)
    if len(ops) == 1 and lint.node_name(ops[0]) == "nested":
        return
    if not ops:
        lint.error(
            node,
            message=f"field '{field_name}' has no operations",
            code="E001",
            hint=f'add at least one operation: {field_name} {{ css ".item"; text }}',
        )
        return
    if struct_type == "table":
        if lint.node_name(ops[0]) != "match":
            lint.error(
                node,
                message=f"table field '{field_name}' must start with 'match {{ ... }}'",
                code="E001",
            )
    _check_pipeline_types(ops, ctx, lint, start_type=VariableType.DOCUMENT)


def _lint_transform_node(node: KdlNode, ctx: _ParseContext, lint: _LintContext) -> None:
    """Validate module-level transform definition."""
    accept_str = lint.get_prop(node, "accept")
    ret_str = lint.get_prop(node, "return")
    lang_nodes = lint.get_children_nodes(node)
    is_definition = bool(accept_str or ret_str or lang_nodes)
    if not is_definition:
        return

    args = lint.get_args(node)
    if not args:
        lint.error(node, message="'transform' requires a name", code="E001")
        return
    name = args[0]

    if not accept_str:
        lint.error(
            node,
            message=f"'transform {name}' missing required property 'accept'",
            code="E001",
        )
    elif accept_str not in _VALID_TRANSFORM_TYPES:
        lint.error(
            node,
            message=f"'transform {name}': invalid accept type '{accept_str}' (AUTO not allowed)",
            code="E001",
        )

    if not ret_str:
        lint.error(
            node,
            message=f"'transform {name}' missing required property 'return'",
            code="E001",
        )
    elif ret_str not in _VALID_TRANSFORM_TYPES:
        lint.error(
            node,
            message=f"'transform {name}': invalid return type '{ret_str}' (AUTO not allowed)",
            code="E001",
        )

    if not lang_nodes:
        lint.error(
            node,
            message=f"'transform {name}' has no language implementations",
            code="E001",
        )
        return

    for lang_node in lang_nodes:
        lang = lint.node_name(lang_node)
        if not lang:
            continue
        impl_nodes = lint.get_children_nodes(lang_node)
        has_code = any(lint.node_name(n) == "code" for n in impl_nodes)
        for impl_node in impl_nodes:
            impl_name = lint.node_name(impl_node)
            if impl_name == "code" and not lint.get_args(impl_node):
                lint.error(
                    impl_node,
                    message=f"'transform {name}' > '{lang}' > 'code' requires a string argument",
                    code="E001",
                )
            elif impl_name == "import" and not lint.get_args(impl_node):
                lint.error(
                    impl_node,
                    message=f"'transform {name}' > '{lang}' > 'import' requires a string argument",
                    code="E001",
                )
            elif impl_name and impl_name not in ("code", "import"):
                lint.error(
                    impl_node,
                    message=f"'transform {name}' > '{lang}': unknown keyword '{impl_name}'",
                    code="E200",
                )
        if not has_code:
            lint.error(
                lang_node,
                message=f"'transform {name}' > '{lang}' has no 'code' statement",
                code="E001",
            )


def _lint_define_node(node: KdlNode, ctx: _ParseContext, lint: _LintContext) -> None:
    """Validate module-level define."""
    children = lint.get_children_nodes(node)
    args = lint.get_args(node)
    if children:
        if not args:
            lint.error(
                node,
                message="block 'define' requires a name",
                code="E001",
                hint='example: define EXTRACT-HREF { css "a"; attr "href" }',
            )
    elif not node.properties:
        lint.error(
            node,
            message="'define' must be scalar (NAME=value) or block (NAME { ... })",
            code="E001",
        )


# ── Module-level handlers ────────────────────────────────────────────────────────


def _handle_struct(node: KdlNode, module: Module, ctx: _ParseContext, lint: _LintContext) -> Struct:
    _lint_struct_node(node, module, ctx, lint)
    type_ = node.properties.get("type", KdlArg(value="item", span=node.span, is_identifier=True)).value
    keep_order = node.properties.get("keep-order", KdlArg(value=False, span=node.span, is_identifier=False)).value
    match type_:
        case "item": st_type = StructType.ITEM
        case "list": st_type = StructType.LIST
        case "table": st_type = StructType.TABLE
        case "dict": st_type = StructType.DICT
        case "flat": st_type = StructType.FLAT
        case "rest": st_type = StructType.REST
        case _: raise BuildTimeError(f"Unknown struct type: {type_}")
    struct = Struct(parent=module, name=str(node.args[0].value), struct_type=st_type, keep_order=keep_order)
    ctx.structs[struct.name] = struct
    _parse_struct(node.children, struct, ctx, lint)
    return struct


def _handle_json(node: KdlNode, module: Module, ctx: _ParseContext, lint: _LintContext) -> JsonDef:
    name = str(node.args[0].value) if node.args else ""
    is_array = node.properties.get("array", KdlArg(value=False, span=node.span, is_identifier=False)).value
    path = str(node.properties.get("path", KdlArg(value="", span=node.span, is_identifier=False)).value)
    json_def = JsonDef(parent=module, name=name, is_array=is_array, path=path)
    _parse_json_fields(node.children, json_def)
    ctx.json_defs[json_def.name] = json_def
    return json_def


def _handle_define(node: KdlNode, ctx: _ParseContext, lint: _LintContext) -> None:
    _lint_define_node(node, ctx, lint)
    if node.children:
        ctx.children_defines[str(node.args[0].value)] = node.children
        lint.defines[str(node.args[0].value)] = _DefineInfo(
            name=str(node.args[0].value), kind=_DefineKind.BLOCK, value=None, node=node,
        )
    else:
        for k, v in node.properties.items():
            value = v.value
            if isinstance(value, str):
                value = _resolve_define_references(value, ctx)
            ctx.property_defines[k] = value
            lint.defines[k] = _DefineInfo(name=k, kind=_DefineKind.SCALAR, value=str(value), node=node)


def _handle_transform(node: KdlNode, ctx: _ParseContext, lint: _LintContext) -> None:
    _lint_transform_node(node, ctx, lint)
    name = str(node.args[0].value) if node.args else ""
    accept_str = str(node.properties.get("accept", KdlArg(value="", span=node.span, is_identifier=True)).value)
    ret_str = str(node.properties.get("return", KdlArg(value="", span=node.span, is_identifier=True)).value)
    if accept_str not in _VAR_TYPE_MAP:
        raise ParseError(f"transform '{name}': invalid accept type '{accept_str}' (AUTO not allowed)")
    if ret_str not in _VAR_TYPE_MAP:
        raise ParseError(f"transform '{name}': invalid return type '{ret_str}' (AUTO not allowed)")
    accept_type = _VAR_TYPE_MAP[accept_str]
    ret_type = _VAR_TYPE_MAP[ret_str]
    transform_def = TransformDef(name=name, accept=accept_type, ret=ret_type)
    for lang_node in node.children:
        lang = lang_node.name
        imports: list[str] = []
        code: list[str] = []
        for item in lang_node.children:
            if item.name == "import":
                imports.extend(str(a.value) for a in item.args)
            elif item.name == "code":
                code.extend(str(a.value) for a in item.args)
        transform_def.body.append(TransformTarget(parent=transform_def, lang=lang, imports=tuple(imports), code=tuple(code)))
    ctx.transforms[name] = transform_def
    lang_nodes = node.children
    lint.transforms[name] = _TransformInfo(
        name=name, accept=accept_str, ret=ret_str,
        langs=[n.name for n in lang_nodes], node=node,
    )


# ── Import resolution ────────────────────────────────────────────────────────────

_KDL_TEXT_ENCODING = "utf-8-sig"


def _resolve_imports(
    top_nodes: list[KdlNode],
    source_path: Path | None,
    ctx: _ParseContext,
    lint: _LintContext,
    diagnostics: list[ReadDiagnostic],
    visited: set[str] | None = None,
) -> list[KdlNode]:
    if visited is None:
        visited = set()
    if source_path is not None:
        visited.add(str(source_path.resolve()))

    result: list[KdlNode] = []
    for node in top_nodes:
        if node.name != "import":
            result.append(node)
            continue
        if not node.args:
            result.append(node)
            continue
        if source_path is None:
            diagnostics.append(ReadDiagnostic(
                message="Cannot use 'import' when parsing from string without a file path",
                severity=Severity.ERROR, span=node.span, path=lint.path,
                code="E003",
            ))
            continue
        raw_path = str(node.args[0].value)
        import_path = (source_path.parent / raw_path).resolve()
        import_key = str(import_path)
        if import_key in visited:
            diagnostics.append(ReadDiagnostic(
                message=f"Circular import detected: {import_path}",
                severity=Severity.ERROR, span=node.span, path=lint.path,
                code="E003",
            ))
            continue
        if not import_path.is_file():
            diagnostics.append(ReadDiagnostic(
                message=f"import: file not found: {import_path}",
                severity=Severity.ERROR, span=node.span, path=lint.path,
                code="E003",
            ))
            continue
        visited.add(import_key)
        try:
            src = import_path.read_text(encoding=_KDL_TEXT_ENCODING)
        except OSError as e:
            diagnostics.append(ReadDiagnostic(
                message=f"import: cannot read file: {e}",
                severity=Severity.ERROR, span=node.span, path=lint.path,
                code="E003",
            ))
            continue
        try:
            parser = KDL2CSTParser()
            doc = parser.parse(src)
        except Exception as e:
            diagnostics.append(ReadDiagnostic(
                message=f"import: parse error in {import_path}: {e}",
                severity=Severity.ERROR, span=node.span, path=lint.path,
                code="E000",
            ))
            continue

        imported_nodes = tuple(KdlNode.from_cst(n) for n in doc.nodes)
        imported_nodes = _resolve_imports(list(imported_nodes), import_path, ctx, lint, diagnostics, visited)
        # conflict detection
        imported_names: set[str] = set()
        for n in imported_nodes:
            if n.name == "struct":
                imported_names.add(str(n.args[0].value))
            elif n.name in ("json", "define", "transform"):
                imported_names.add(str(n.args[0].value) if n.args else "")
        for n in result:
            if n.name == "struct" and str(n.args[0].value) in imported_names:
                diagnostics.append(ReadDiagnostic(
                    message=f"Name conflict: struct '{n.args[0].value}' conflicts with imported name",
                    severity=Severity.ERROR, span=n.span, path=lint.path,
                    code="E003",
                ))
        result.extend(imported_nodes)
    return result


# ── Reader ──────────────────────────────────────────────────────────────────────


from typing import cast


class SscReader(Reader[KdlNode, Module]):
    """Unified KDL → Module AST reader with integrated linting."""

    def __init__(self, *, source_path: Path | None = None) -> None:
        self._source_path = source_path
        self._ctx = _ParseContext(source_path=source_path)
        self._lint = _LintContext()

    def on_node(
        self,
        name: str,
        args: tuple[KdlArg, ...],
        properties: Mapping[str, KdlArg],
        children: tuple[KdlNode, ...],
        ctx: WalkContext[KdlNode],
    ) -> KdlNode:
        return ctx.node

    def error_node(self, message: str, ctx: WalkContext[KdlNode]) -> KdlNode:
        return ctx.node

    def finalize(
        self,
        nodes: list[KdlNode],
        diagnostics: list[ReadDiagnostic],
    ) -> Module:
        ctx = self._ctx
        lint = self._lint
        top_nodes = nodes

        # pass 1 — resolve imports
        top_nodes = _resolve_imports(top_nodes, self._source_path, ctx, lint, diagnostics)

        # pass 2 — collect defines and transforms
        for node in top_nodes:
            if node.name == "define":
                _handle_define(node, ctx, lint)
            elif node.name == "transform":
                _handle_transform(node, ctx, lint)

        # pass 3 — build module
        module = Module()
        structs: list[Struct] = []
        typedefs: list[TypeDef] = []

        for node in top_nodes:
            lint.push(node.name)
            if node.name == "@doc":
                module.docstring.value = str(node.args[0].value)
            elif node.name == "json":
                expr = _handle_json(node, module, ctx, lint)
                module.body.append(expr)
            elif node.name == "struct":
                struct = _handle_struct(node, module, ctx, lint)
                typedefs.append(_typedef_from_struct(struct, module))
                structs.append(struct)
            elif node.name in ("define", "transform", "import"):
                pass  # already handled
            else:
                diagnostics.append(ReadDiagnostic(
                    message=f"Unknown node: {node.name}",
                    severity=Severity.ERROR, span=node.span, path=lint.path,
                    code="E200",
                ))
            lint.pop()

        # wire transforms
        for td in ctx.transforms.values():
            td.parent = module

        # wire module body
        module.body.extend(
            list(ctx.json_defs.values())
            + list(ctx.transforms.values())
            + typedefs
            + structs
        )

        # merge lint diagnostics into walker diagnostics
        diagnostics.extend(lint.diagnostics)

        return module


# ── Public API ────────────────────────────────────────────────────────────────────


def parse_module(
    src: str, *, source_path: Path | None = None
) -> tuple[Module, list[ReadDiagnostic]]:
    """Parse KDL source → Module AST + diagnostics."""
    parser = KDL2CSTParser()
    doc = parser.parse(src)
    reader = SscReader(source_path=source_path)
    return parse_into(doc, reader)
