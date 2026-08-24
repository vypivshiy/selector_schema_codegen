"""Module-level handlers — struct, json, define, imports."""

from __future__ import annotations

from pathlib import Path

from ssc_codegen.ast import (
    FunctionDef,
    JsonDef,
    Module,
    StructBase,
    Struct,
    StructRest,
    StructType,
    VariableType,
    TypeInfo,
)
from ssc_codegen.exceptions import BuildTimeError
from kdlquery import KdlNode
from kdlquery.reader import ReadDiagnostic

from ssc_codegen.core.contexts import (
    DefineKind,
    DefineInfo,
    LintContext,
    ParseContext,
)
from ssc_codegen.core.expressions import resolve_define_references
from ssc_codegen.core.struct_parser import (
    parse_function,
    parse_json_fields,
    parse_struct,
)


def register_node_sources(
    nodes: list[KdlNode], source_path: Path, ctx: ParseContext
) -> None:
    """Record source origin for top-level nodes and all descendants."""
    pending = list(nodes)
    while pending:
        node = pending.pop()
        ctx.node_source_paths[id(node)] = source_path
        pending.extend(node.children)


def handle_struct(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> StructBase:
    raw = node.type_annotation
    type_ = raw[1:-1] if raw else (node.get_prop("type") or "item")
    keep_order = node.get_prop("keep-order") or False
    name = str(node.args[0].value)
    struct_type_map: dict[str, StructType] = {
        "item": StructType.ITEM,
        "list": StructType.LIST,
        "flat": StructType.FLAT,
        "dict": StructType.DICT,
        "table": StructType.TABLE,
        "rest": StructType.REST,
        "raw": StructType.RAW,
    }
    st = struct_type_map.get(type_)
    if st is None:
        raise BuildTimeError(f"Unknown struct type: {type_}")
    if st is StructType.REST:
        struct: StructBase = StructRest(
            parent=module,
            name=name,
            keep_order=keep_order,
        )
    else:
        struct = Struct(
            parent=module,
            name=name,
            type=st,
            keep_order=keep_order,
        )
    ctx.structs[struct.name] = struct
    parse_struct(node.children, struct, ctx, lint)
    return struct


def handle_function(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> FunctionDef:
    raw_annotation = node.type_annotation
    is_raw = raw_annotation == "(raw)"
    if not node.args:
        raise BuildTimeError("'fn' requires a name")
    name = str(node.args[0].value)
    fn = FunctionDef(
        parent=module,
        name=name,
        is_raw=is_raw,
        accept_type_info=(
            TypeInfo(base=VariableType.STRING)
            if is_raw
            else TypeInfo(base=VariableType.DOCUMENT)
        ),
    )
    parse_function(node.children, fn, ctx, lint)
    return fn


def handle_json(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> JsonDef:
    name = str(node.args[0].value) if node.args else ""
    is_array = node.type_annotation == "(array)"
    path = node.get_prop("path") or ""
    json_def = JsonDef(parent=module, name=name, is_array=is_array, path=path)
    parse_json_fields(node.children, json_def, ctx)
    ctx.json_defs[json_def.name] = json_def
    return json_def


def handle_define(node: KdlNode, ctx: ParseContext, lint: LintContext) -> None:
    if node.children:
        ctx.children_defines[str(node.args[0].value)] = list(node.children)
        lint.defines[str(node.args[0].value)] = DefineInfo(
            name=str(node.args[0].value),
            kind=DefineKind.BLOCK,
            value=None,
            node=node,
        )
    else:
        for k, v in node.properties.items():
            value = v.value
            if isinstance(value, str):
                value = resolve_define_references(value, ctx)
            ctx.property_defines[k] = value
            lint.defines[k] = DefineInfo(
                name=k, kind=DefineKind.SCALAR, value=str(value), node=node
            )


def resolve_imports(
    top_nodes: list[KdlNode],
    source_path: Path | None,
    ctx: ParseContext,
    lint: LintContext,
    diagnostics: list[ReadDiagnostic],
) -> list[KdlNode]:
    from ssc_codegen.core.imports import resolve_explicit_imports

    return resolve_explicit_imports(top_nodes, source_path, ctx, diagnostics)
