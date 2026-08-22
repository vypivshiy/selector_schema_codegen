"""Struct and JSON field parsing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ssc_codegen.ast import (
    Attr,
    CheckMethod,
    CssRemove,
    CssSelect,
    CssSelectAll,
    ErrorResponse,
    Field,
    FunctionDef,
    InitField,
    InitFieldCall,
    JsonDef,
    JsonDefField,
    Key,
    MethodFetch,
    MethodRest,
    Node,
    PreValidate,
    Raw,
    SplitDoc,
    StartParse,
    StructBase,
    StructRest,
    Struct,
    StructType,
    TableConfig,
    TableMatchKey,
    TableRows,
    Text,
    TypeInfo,
    Value,
    VariableType,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.request_spec import parse_to_http
from kdlquery import KdlNode

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.expressions import parse_expressions
from ssc_codegen.core.type_checking import check_pipeline_types

# AST node types forbidden in (raw)struct — they require a DOM document.
_RAW_FORBIDDEN_OPS = (
    CssSelect,
    CssSelectAll,
    CssRemove,
    XpathSelect,
    XpathSelectAll,
    XpathRemove,
    Text,
    Attr,
    Raw,
)


def _struct_start_type(struct: StructBase) -> VariableType:
    """Return the pipeline start type for a struct's fields."""
    if isinstance(struct, Struct) and struct.type == StructType.RAW:
        return VariableType.STRING
    return VariableType.DOCUMENT


def _lint_raw_forbidden_ops(expr: Node, lint: LintContext) -> None:
    """Recursively check that no HTML-only ops appear in a RAW struct node."""
    for child in expr.body:
        if isinstance(child, _RAW_FORBIDDEN_OPS):
            lint.error(
                child,  # type: ignore[arg-type]
                message=(
                    f"HTML operation '{type(child).__name__}' is forbidden in"
                    " (raw)struct — the document is a plain string, not a DOM"
                ),
                code="E001",
            )
        _lint_raw_forbidden_ops(child, lint)


def parse_struct(
    kdl_nodes: Sequence[KdlNode],
    parent: StructBase,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.STRUCT_BODY
    expr: Node | CheckMethod | ErrorResponse
    for node in kdl_nodes:
        if node.name == "@doc":
            parent.doc = str(node.args[0].value)
        elif node.name == "@init":
            if isinstance(parent, Struct):
                _parse_init_fields(node.children, parent, ctx, lint)
        elif node.name == "@pre-validate":
            expr = PreValidate(parent=parent)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                expr.accept_type_info = TypeInfo(base=VariableType.STRING)
            parse_expressions(node.children, expr, ctx, lint)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                _lint_raw_forbidden_ops(expr, lint)
            parent.body.append(expr)
        elif node.name == "@check":
            if not node.args:
                lint.error(
                    node,
                    message="@check requires a name: @check <name> { ... }",
                    code="E001",
                )
                continue
            check_name = str(node.args[0].value)
            expr = CheckMethod(parent=parent, name=check_name)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                expr.accept_type_info = TypeInfo(base=VariableType.STRING)
            parse_expressions(node.children, expr, ctx, lint)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                _lint_raw_forbidden_ops(expr, lint)
            parent.body.append(expr)
        elif node.name == "@split-doc":
            expr = SplitDoc(parent=parent)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                expr.accept_type_info = TypeInfo(base=VariableType.STRING)
                expr.ret_type_info = TypeInfo(
                    base=VariableType.STRING, is_array=True
                )
            parse_expressions(node.children, expr, ctx, lint)
            if isinstance(parent, Struct) and parent.type == StructType.RAW:
                _lint_raw_forbidden_ops(expr, lint)
            parent.body.append(expr)
        elif node.name == "@key":
            expr = Key(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@value":
            expr = Value(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@table":
            expr = TableConfig(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@rows":
            expr = TableRows(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@match":
            expr = TableMatchKey(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@request":
            if not node.args:
                lint.error(
                    node,
                    message="@request requires a multiline string argument",
                    code="E001",
                )
                continue
            raw_payload = str(
                ctx.property_defines.get(node.args[0].value, node.args[0].value)
            )
            try:
                http = parse_to_http(raw_payload)
            except ValueError as exc:
                lint.error(
                    node,
                    message=str(exc),
                    code="E002",
                    hint="use a curl command or raw HTTP request",
                )
                continue
            method_name = node.get_prop("name") or ""
            response_path_val = node.get_prop("response-path") or ""
            response_join_val = node.get_prop("response-join") or ""

            is_rest = isinstance(parent, StructRest)

            # Lint: response-path format (dot-notation, non-empty segments).
            if response_path_val:
                segments = response_path_val.split(".")
                bad = any(not seg for seg in segments) or any(
                    not seg.replace("-", "_").isidentifier() for seg in segments
                )
                if bad:
                    lint.error(
                        node,
                        message=(
                            "response-path must be dot-notation with "
                            "non-empty ASCII identifier segments "
                            '(e.g. "data.user"); got '
                            f"{response_path_val!r}"
                        ),
                        code="E001",
                    )

            # Lint: response-join only on fetch-track.
            if response_join_val and is_rest:
                lint.error(
                    node,
                    message=(
                        "response-join is forbidden on type=rest structs "
                        "(use response-path alone; Ok.value is the "
                        "extracted object)"
                    ),
                    code="E001",
                )

            # Lint: response-join without response-path is meaningless.
            if response_join_val and not response_path_val:
                lint.error(
                    node,
                    message=(
                        "response-join requires response-path (nothing to join)"
                    ),
                    code="E001",
                )

            if is_rest:
                rest_method = MethodRest(parent=parent, name=method_name)
                rest_method.response_path = response_path_val
                response_schema_val = node.get_prop("response") or ""
                rest_method.response_schema = str(
                    ctx.property_defines.get(
                        response_schema_val, response_schema_val
                    )
                )
                doc_val = node.get_prop("doc") or ""
                rest_method.doc = str(
                    ctx.property_defines.get(doc_val, doc_val)
                )
                http.parent = rest_method
                rest_method.body.append(http)
                parent.body.append(rest_method)
            else:
                fetch_method = MethodFetch(parent=parent, name=method_name)
                fetch_method.response_path = response_path_val
                fetch_method.response_join = response_join_val
                http.parent = fetch_method
                fetch_method.body.append(http)
                parent.body.append(fetch_method)
        elif node.name == "@error":
            if not node.args or len(node.args) < 2:
                lint.error(
                    node,
                    message="@error requires both status and schema name",
                    code="E001",
                )
                continue
            status_raw = node.args[0].value
            try:
                status_int = int(status_raw)
            except (TypeError, ValueError):
                lint.error(
                    node,
                    message=f"@error status must be integer, got {status_raw!r}",
                    code="E002",
                )
                continue
            schema_name = str(
                ctx.property_defines.get(node.args[1].value, node.args[1].value)
            )
            required_keys: list[str] = []
            for i in range(2, len(node.args)):
                key = str(
                    ctx.property_defines.get(
                        node.args[i].value, node.args[i].value
                    )
                )
                required_keys.append(key)
            conditions: dict[str, Any] = {}
            for k, v in node.properties.items():
                key = str(ctx.property_defines.get(k, k))
                val = ctx.property_defines.get(v.value, v.value)
                conditions[key] = val
            err = ErrorResponse(
                parent=parent,
                status=status_int,
                schema_name=schema_name,
                required_keys=required_keys,
                conditions=conditions,
            )
            parent.body.append(err)
        else:
            is_raw = (
                isinstance(parent, Struct) and parent.type == StructType.RAW
            )
            if isinstance(parent, Struct) and parent.type == StructType.TABLE:
                expr = Field(
                    parent=parent,
                    name=node.name,
                    accept_type_info=TypeInfo(base=VariableType.STRING),
                )
            elif is_raw:
                expr = Field(
                    parent=parent,
                    name=node.name,
                    accept_type_info=TypeInfo(base=VariableType.STRING),
                )
            else:
                expr = Field(parent=parent, name=node.name)
            ops = list(node.children)
            parse_expressions(ops, expr, ctx, lint)
            # Type inference for regular fields
            if ops and not (len(ops) == 1 and ops[0].name == "nested"):
                check_pipeline_types(
                    ops,
                    ctx,
                    lint,
                    start_type=_struct_start_type(parent),
                )
            if is_raw:
                _lint_raw_forbidden_ops(expr, lint)
            parent.body.append(expr)

    if not isinstance(parent, StructRest):
        parent.body.append(StartParse(parent=parent))
    lint.walk_context = prev_ctx


def parse_function(
    kdl_nodes: Sequence[KdlNode],
    fn: FunctionDef,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    """Parse the body of a ``fn`` / ``(raw)fn`` directive.

    The body is a flat pipeline (same ops as a Field), optionally preceded
    by ``@doc``. No struct-level directives (@init, @check, @split-doc, etc.)
    are accepted — those are reported by the structural linter.
    """
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.PIPELINE

    pipeline_nodes: list[KdlNode] = []
    for node in kdl_nodes:
        if node.name == "@doc":
            fn.doc = str(node.args[0].value)
        elif node.name.startswith("@"):
            continue  # structural linter already reported E203
        else:
            pipeline_nodes.append(node)

    ops = pipeline_nodes
    parse_expressions(ops, fn, ctx, lint)
    if ops:
        check_pipeline_types(
            ops,
            ctx,
            lint,
            start_type=VariableType.STRING
            if fn.is_raw
            else VariableType.DOCUMENT,
        )
    if fn.is_raw:
        _lint_raw_forbidden_ops(fn, lint)

    lint.walk_context = prev_ctx


def parse_json_fields(
    nodes: Sequence[KdlNode], parent: JsonDef, ctx: ParseContext
) -> None:
    for node in nodes:
        # Block define expansion in json context
        if not node.args and node.name in ctx.children_defines:
            parse_json_fields(ctx.children_defines[node.name], parent, ctx)
            continue
        name = node.name
        modifiers: list[str] = []
        type_ = ""
        alias = ""
        for arg in node.args:
            a = str(arg.value)
            if a.startswith("@"):
                modifiers.append(a)
            elif not type_:
                type_ = a
            else:
                alias = a
        skip = "@skip" in modifiers
        if not type_ and skip:
            type_ = "str"
        is_array = any(
            arg.type_annotation == "(array)"
            for arg in node.args
            if str(arg.value) == type_
        )
        is_optional = type_.endswith("?")
        type_ = type_.rstrip("?")
        ref_name = ""
        match type_:
            case "str":
                ret_type = VariableType.STRING
            case "int":
                ret_type = VariableType.INT
            case "float":
                ret_type = VariableType.FLOAT
            case "bool":
                ret_type = VariableType.BOOL
            case "null" | "nil":
                ret_type = VariableType.NULL
            case _:
                ref_name = type_
                is_array_ref = any(
                    arg.type_annotation == "(array)"
                    for arg in node.args
                    if str(arg.value) == ref_name
                )
                if is_array_ref:
                    is_array = True
                ret_type = VariableType.JSON
        may_miss = "@omitempty" in modifiers
        doc = node.get_prop("doc") or ""
        parent.body.append(
            JsonDefField(
                parent=parent,
                name=name,
                ret_type_info=TypeInfo(
                    base=ret_type,
                    is_array=is_array,
                    is_optional=is_optional,
                    ref=ref_name or None,
                    omitempty=may_miss,
                    skip=skip,
                ),
                alias=alias,
                doc=doc,
            )
        )


def _parse_init_fields(
    kdl_nodes: Sequence[KdlNode],
    parent: Struct,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.INIT_BLOCK
    init = parent.init
    is_raw = parent.type == StructType.RAW
    start_type = _struct_start_type(parent)
    for node in kdl_nodes:
        lint.push(node.name)
        lint.init_fields.add(node.name)
        expr = InitField(parent=parent, name=node.name)
        if is_raw:
            expr.accept_type_info = TypeInfo(base=VariableType.STRING)
        parse_expressions(node.children, expr, ctx, lint)
        if expr.body:
            expr.ret_type_info = expr.body[-1].ret_type_info
            ops = list(node.children)
            ret = check_pipeline_types(ops, ctx, lint, start_type=start_type)
            lint.inferred_define_types[node.name] = (start_type, ret)
        if is_raw:
            _lint_raw_forbidden_ops(expr, lint)
        parent.body.append(expr)
        init.body.append(InitFieldCall(parent=init, name=node.name))
        lint.pop()
    lint.walk_context = prev_ctx
