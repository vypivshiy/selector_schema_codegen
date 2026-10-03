"""Module-level node handlers for struct, json, define, function, and import resolution."""

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
    _parse_dict_type_directives,
    parse_function,
    parse_json_fields,
    parse_struct,
)


def register_node_sources(
    nodes: list[KdlNode], source_path: Path, ctx: ParseContext
) -> None:
    """Recursively map KDL node object IDs to their originating file path.

    Args:
        nodes: Sequence of top-level KDL nodes.
        source_path: Filesystem path to the KDL file containing `nodes`.
        ctx: Parse context storing the `node_source_paths` lookup table.
    """
    pending = list(nodes)
    while pending:
        node = pending.pop()
        ctx.node_source_paths[id(node)] = source_path
        pending.extend(node.children)


def handle_struct(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> StructBase:
    """Parse a top-level KDL `struct` node into a `Struct` or `StructRest` AST node.

    Args:
        node: The KDL `struct` node.
        module: The root `Module` AST node owning the struct.
        ctx: Global parse context for storing the parsed struct.
        lint: Lint context for recording structural validation diagnostics.

    Returns:
        The instantiated and populated `Struct` or `StructRest` AST node.

    Raises:
        BuildTimeError: If the struct type annotation is unrecognized.
    """
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
    """Parse a top-level KDL `fn` or `(raw)fn` node into a `FunctionDef` AST node.

    Args:
        node: The KDL function node.
        module: The root `Module` AST node owning the function.
        ctx: Global parse context.
        lint: Lint context for recording validation diagnostics.

    Returns:
        The instantiated and populated `FunctionDef` AST node.

    Raises:
        BuildTimeError: If the function name argument is missing.
    """
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
    """Parse a top-level KDL `json` schema declaration into a `JsonDef` AST node.

    Args:
        node: The KDL `json` declaration node.
        module: The root `Module` AST node owning the schema.
        ctx: Global parse context for storing the schema definition.
        lint: Lint context for recording diagnostics.

    Returns:
        The instantiated and populated `JsonDef` AST node.
    """
    name = str(node.args[0].value) if node.args else ""
    raw_ann = node.type_annotation or ""
    type_prop = node.get_prop("type") or ""
    is_array = raw_ann.strip("()") == "array" or type_prop == "array"
    is_dict = raw_ann.strip("()") == "dict" or type_prop == "dict"
    path = node.get_prop("path") or ""
    json_def = JsonDef(
        parent=module,
        name=name,
        is_array=is_array,
        is_dict=is_dict,
        path=path,
    )
    if is_dict:
        key_info, val_info = _parse_dict_type_directives(
            node.children,
            ctx,
            lint,
            parent_def=json_def,
            field_name="",
            explicit_dict_name=json_def.name,
        )
        json_def.key_type_info = key_info
        json_def.value_type_info = val_info
    else:
        parse_json_fields(node.children, json_def, ctx, lint)
    ctx.json_defs[json_def.name] = json_def
    return json_def


def handle_define(node: KdlNode, ctx: ParseContext, lint: LintContext) -> None:
    """Parse a top-level KDL `define` into scalar constants or pipeline blocks.

    Args:
        node: The KDL `define` node.
        ctx: Global parse context receiving the registered define values.
        lint: Lint context storing define metadata for validation passes.
    """
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
    """Resolve cross-file imports and return a flattened dependency-ordered node list.

    Args:
        top_nodes: Initial top-level KDL nodes from the root document.
        source_path: Path to the root document on disk.
        ctx: Global parse context for node provenance tracking.
        lint: Lint context.
        diagnostics: List receiving import validation diagnostics.

    Returns:
        Flattened list of all required KDL nodes in topological dependency order.
    """
    from ssc_codegen.core.imports import resolve_explicit_imports

    return resolve_explicit_imports(top_nodes, source_path, ctx, diagnostics)
