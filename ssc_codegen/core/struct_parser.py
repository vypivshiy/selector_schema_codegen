"""Struct and JSON field parsing."""

from __future__ import annotations

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
from ssc_codegen.exceptions import ParseError
from ssc_codegen.kdl import KdlArg, KdlNode

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.expressions import parse_expressions
from ssc_codegen.core.type_checking import check_pipeline_types


def parse_struct(
    kdl_nodes: list[KdlNode],
    parent: Struct,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.STRUCT_BODY
    for node in kdl_nodes:
        if node.name == "@doc":
            parent.docstring.value = str(node.args[0].value)
        elif node.name == "@init":
            expr = parent.init
            _parse_init_fields(node.children, expr, ctx, lint)
        elif node.name == "@pre-validate":
            expr = PreValidate(parent=parent)
            parse_expressions(node.children, expr, ctx, lint)
            parent.body.append(expr)
        elif node.name == "@check":
            if not node.args:
                raise ParseError(
                    "@check requires a name: @check <name> { ... }"
                )
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
                raise ParseError(
                    "@request requires a multiline string argument"
                )
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
            doc_val = node.properties.get(
                "doc", KdlArg(value="", span=node.span, is_identifier=False)
            )
            req.doc = str(
                ctx.property_defines.get(doc_val.value, doc_val.value)
            )
            parent.body.append(req)
        elif node.name == "@error":
            if not node.args or len(node.args) < 2:
                raise ParseError("@error requires both status and schema name")
            status_raw = node.args[0].value
            try:
                status_int = int(status_raw)
            except (TypeError, ValueError):
                raise ParseError(
                    f"@error status must be integer, got {status_raw!r}"
                )
            schema_name = str(
                ctx.property_defines.get(node.args[1].value, node.args[1].value)
            )
            conditions: dict[str, Any] = {}
            for k, v in node.properties.items():
                key = str(ctx.property_defines.get(k.value, k.value))
                val = ctx.property_defines.get(v.value, v.value)
                conditions[key] = val
            err = ErrorResponse(
                parent=parent,
                status=status_int,
                schema_name=schema_name,
                conditions=conditions,
            )
            parent.body.append(err)
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


def parse_json_fields(nodes: list[KdlNode], parent: JsonDef) -> None:
    for node in nodes:
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
        may_miss = "@missing" in modifiers
        if "@optional" in modifiers:
            is_optional = True
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
    kdl_nodes: list[KdlNode],
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
