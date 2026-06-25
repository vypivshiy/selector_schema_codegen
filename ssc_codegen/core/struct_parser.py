"""Struct and JSON field parsing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ssc_codegen.ast import (
    CheckMethod,
    ErrorResponse,
    Field,
    Init,
    InitField,
    JsonDef,
    JsonDefField,
    Key,
    MethodFetch,
    MethodRest,
    Node,
    PreValidate,
    RequestHttp,
    SplitDoc,
    StartParse,
    StructBase,
    StructRest,
    Struct,
    StructType,
    TableConfig,
    TableMatchKey,
    TableRows,
    TypeInfo,
    Value,
    VariableType,
)
from ssc_codegen.request_spec import parse_to_spec
from kdlquery import KdlNode

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.expressions import parse_expressions
from ssc_codegen.core.type_checking import check_pipeline_types


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
                _parse_init_fields(node.children, parent.init, ctx, lint)
        elif node.name == "@pre-validate":
            expr = PreValidate(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
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
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@split-doc":
            expr = SplitDoc(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
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
            spec = parse_to_spec(raw_payload)
            http = RequestHttp(
                method=spec.method,
                url=spec.url,
                headers=spec.headers,
                cookies=spec.cookies,
                params=spec.params,
                body_kind=spec.body_kind,
                body=spec.body,
            )
            method_name = node.get_prop("name") or ""
            if isinstance(parent, StructRest):
                rest_method = MethodRest(parent=parent, name=method_name)
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
                fetch_method.response_path = (
                    node.get_prop("response-path") or ""
                )
                fetch_method.response_join = (
                    node.get_prop("response-join") or ""
                )
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
            if isinstance(parent, Struct) and parent.type == StructType.TABLE:
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
                    ops, ctx, lint, start_type=VariableType.DOCUMENT
                )
            parent.body.append(expr)

    if not isinstance(parent, StructRest):
        parent.body.append(StartParse(parent=parent))
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
    parent: Init,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.INIT_BLOCK
    for node in kdl_nodes:
        lint.push(node.name)
        lint.init_fields.add(node.name)
        expr = InitField(parent=parent, name=node.name)
        parse_expressions(node.children, expr, ctx, lint)
        if expr.body:
            expr.ret_type_info = expr.body[-1].ret_type_info
            ops = list(node.children)
            ret = check_pipeline_types(
                ops, ctx, lint, start_type=VariableType.DOCUMENT
            )
            lint.inferred_define_types[node.name] = (VariableType.DOCUMENT, ret)
        parent.body.append(expr)
        lint.pop()
    lint.walk_context = prev_ctx
