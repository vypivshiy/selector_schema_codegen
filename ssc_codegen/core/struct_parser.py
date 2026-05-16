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
    Node,
    PreValidate,
    RequestConfig,
    SplitDoc,
    StartParse,
    Struct,
    StructType,
    TableConfig,
    TableMatchKey,
    TableRow,
    Value,
    VariableType,
)
from ssc_codegen.kdl import KdlArg, KdlNode

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.expressions import parse_expressions
from ssc_codegen.core.type_checking import check_pipeline_types


def parse_struct(
    kdl_nodes: Sequence[KdlNode],
    parent: Struct,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.STRUCT_BODY
    expr: Node | CheckMethod | ErrorResponse
    for node in kdl_nodes:
        if node.name == "@doc":
            parent.docstring.value = str(node.args[0].value)
        elif node.name == "@init":
            init_expr = parent.init
            _parse_init_fields(node.children, init_expr, ctx, lint)
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
            expr = TableRow(parent=parent)
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
            req = RequestConfig(parent=parent)
            req.raw_payload = raw_payload
            req.response_path = str(
                node.properties.get(
                    "response-path",
                    KdlArg(value="", span=node.span, is_identifier=False),
                ).value
            )
            req.response_join = str(
                node.properties.get(
                    "response-join",
                    KdlArg(value="", span=node.span, is_identifier=False),
                ).value
            )
            req.name = str(
                node.properties.get(
                    "name",
                    KdlArg(value="", span=node.span, is_identifier=False),
                ).value
            )
            response_schema = node.properties.get(
                "response",
                KdlArg(value="", span=node.span, is_identifier=False),
            )
            req.response_schema = str(
                ctx.property_defines.get(
                    response_schema.value, response_schema.value
                )
            )
            if req.response_schema and parent.struct_type == StructType.REST:
                lint.rest_response_refs.append((node, req.response_schema))
            doc_val = node.properties.get(
                "doc", KdlArg(value="", span=node.span, is_identifier=False)
            )
            req.doc = str(
                ctx.property_defines.get(doc_val.value, doc_val.value)
            )
            parent.body.append(req)
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
            if parent.struct_type == StructType.REST:
                lint.rest_error_refs.append((node, schema_name))
        else:
            if parent.struct_type == StructType.TABLE:
                expr = Field(
                    parent=parent, name=node.name, accept=VariableType.STRING
                )
            else:
                expr = Field(parent=parent, name=node.name)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)

    if parent.struct_type != StructType.REST:
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
        is_array = type_.startswith("(array)")
        type_ = type_.removeprefix("(array)")
        is_optional = type_.endswith("?")
        type_ = type_.rstrip("?")
        ref_name = ""
        match type_:
            case "str":
                ret_type = (
                    VariableType.LIST_STRING
                    if is_array
                    else VariableType.STRING
                )
            case "int":
                ret_type = (
                    VariableType.LIST_INT if is_array else VariableType.INT
                )
            case "float":
                ret_type = (
                    VariableType.LIST_FLOAT if is_array else VariableType.FLOAT
                )
            case "bool":
                ret_type = VariableType.BOOL
            case "null":
                ret_type = VariableType.NULL
            case _:
                ref_name = type_
                if ref_name.startswith("(array)"):
                    ref_name = ref_name.removeprefix("(array)")
                    is_array = True
                ret_type = VariableType.JSON
        may_miss = "@omitempty" in modifiers
        doc = str(
            node.properties.get(
                "doc", KdlArg(value="", span=node.span, is_identifier=False)
            ).value
        )
        parent.body.append(
            JsonDefField(
                parent=parent,
                ret=ret_type,
                name=name,
                is_optional=is_optional,
                is_array=is_array,
                ref_name=ref_name,
                alias=alias,
                skip=skip,
                may_miss=may_miss,
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
            expr.ret = expr.body[-1].ret
            ops = list(node.children)
            ret = check_pipeline_types(
                ops, ctx, lint, start_type=VariableType.DOCUMENT
            )
            lint.inferred_define_types[node.name] = (VariableType.DOCUMENT, ret)
        parent.body.append(expr)
        lint.pop()
    lint.walk_context = prev_ctx
