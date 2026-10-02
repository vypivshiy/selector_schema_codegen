"""Parsing logic for Struct, FunctionDef, and JsonDef declaration bodies."""

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
from ssc_codegen.naming import to_pascal_case
from ssc_codegen.request_spec import parse_to_http
from kdlquery import KdlNode

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.expressions import parse_expressions
from ssc_codegen.core.linter import is_http_status
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
    """Parse children of a KDL struct node into the corresponding AST representation.

    Handles `@doc`, `@init`, `@pre-validate`, `@check`, `@split-doc`, `@key`,
    `@value`, `@table`, `@rows`, `@match`, `@request`, `@error`, regular fields,
    and appends a `StartParse` lifecycle anchor for non-REST structs.

    Args:
        kdl_nodes: Children nodes of the KDL struct declaration.
        parent: The parent `Struct` or `StructRest` AST node to populate.
        ctx: Global parse context for resolving defines and type references.
        lint: Lint context for recording validation diagnostics.
    """
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
            if expr.ret_type_info.base != VariableType.BOOL:
                lint.error(
                    node,
                    message=(
                        f"@check {check_name} must return BOOL, got "
                        f"{expr.ret_type_info.base.name}"
                    ),
                    code="E100",
                    hint="finish the pipeline with 'to-bool' or a BOOL extension",
                )
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
            if not is_http_status(status_int):
                # Structural lint owns the diagnostic. This only prevents
                # malformed statuses from producing a partial AST.
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
    """Parse the body of a standalone `fn` or `(raw)fn` function.

    The body represents a single transformation pipeline optionally preceded
    by `@doc`. Struct-level directives (@init, @check, etc.) are rejected.

    Args:
        kdl_nodes: Children nodes of the KDL function declaration.
        fn: The `FunctionDef` AST node to populate.
        ctx: Global parse context for resolving defines.
        lint: Lint context for recording validation diagnostics.
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


def _parse_dict_type_directives(
    children: Sequence[KdlNode],
    ctx: ParseContext,
    lint: LintContext | None = None,
) -> tuple[TypeInfo, TypeInfo]:
    """Parse '@key' and '@value' directives from a dict JSON schema block."""
    key_info: TypeInfo | None = None
    val_info: TypeInfo | None = None

    for child in children:
        if child.name == "@key":
            key_arg = str(child.args[0].value) if child.args else "str"
            is_opt = key_arg.endswith("?")
            key_arg = key_arg.rstrip("?")
            match key_arg:
                case "int":
                    base = VariableType.INT
                case "float":
                    base = VariableType.FLOAT
                case "bool":
                    base = VariableType.BOOL
                case _:
                    base = VariableType.STRING
            key_info = TypeInfo(base=base, is_optional=is_opt)
        elif child.name == "@value":
            val_arg = str(child.args[0].value) if child.args else "str"
            is_arr = any(
                (arg.type_annotation or "").strip("()") == "array"
                for arg in child.args
            )
            is_opt = val_arg.endswith("?")
            val_arg = val_arg.rstrip("?")
            ref_name: str | None = None
            match val_arg:
                case "str":
                    base = VariableType.STRING
                case "int":
                    base = VariableType.INT
                case "float":
                    base = VariableType.FLOAT
                case "bool":
                    base = VariableType.BOOL
                case "null" | "nil":
                    base = VariableType.NULL
                case _:
                    base = VariableType.JSON
                    ref_name = val_arg
            val_info = TypeInfo(
                base=base,
                is_array=is_arr,
                is_optional=is_opt,
                ref=ref_name,
            )

    if key_info is None:
        key_info = TypeInfo(base=VariableType.STRING)
    if val_info is None:
        val_info = TypeInfo(base=VariableType.STRING)

    return key_info, val_info


def parse_json_fields(
    nodes: Sequence[KdlNode],
    parent: JsonDef,
    ctx: ParseContext,
    lint: LintContext | None = None,
) -> None:
    """Parse field declarations inside a `json` schema definition.

    Expands block defines, parses field modifiers (`@skip`, `@omitempty`),
    resolves primitive types, array annotations, optionality (`?`), and
    key remapping (`from="..."` or positional aliases). Also hoists inline
    anonymous and explicitly named child `JsonDef` blocks.

    Args:
        nodes: Children nodes of the KDL json declaration.
        parent: The `JsonDef` AST node to populate with `JsonDefField` children.
        ctx: Global parse context containing defines and registered schemas.
        lint: Optional lint context for diagnostics.
    """
    for node in nodes:
        # Block define expansion in json context
        if not node.args and node.name in ctx.children_defines:
            parse_json_fields(
                ctx.children_defines[node.name], parent, ctx, lint
            )
            continue

        raw_ann = node.type_annotation or ""
        type_prop = node.get_prop("type") or ""
        is_dict_field = (
            raw_ann.strip("()") == "dict"
            or type_prop == "dict"
            or any(
                (arg.type_annotation or "").strip("()") == "dict"
                or str(arg.value) == "(dict)"
                for arg in node.args
            )
        )

        # Inline (dict) field
        if is_dict_field:
            name = node.name
            is_optional = name.endswith("?")
            name = name.rstrip("?")
            modifiers: list[str] = []
            for arg in node.args:
                a = str(arg.value)
                raw = (
                    ctx.source_text[arg.span.start.offset : arg.span.end.offset]
                    if ctx.source_text
                    else ""
                )
                quoted = raw.startswith(('"', "'"))
                if a in {"@skip", "@omitempty"} and not quoted:
                    modifiers.append(a)
            skip = "@skip" in modifiers
            may_miss = "@omitempty" in modifiers
            from_prop = node.get_prop("from")
            path_prop = node.get_prop("path")
            alias = ""
            if from_prop is not None:
                resolved = str(ctx.property_defines.get(from_prop, from_prop))
                if resolved:
                    alias = resolved
            elif path_prop is not None:
                resolved = str(ctx.property_defines.get(path_prop, path_prop))
                if resolved:
                    alias = resolved
            doc = node.get_prop("doc") or ""
            key_info, val_info = _parse_dict_type_directives(
                node.children, ctx, lint
            )
            parent.body.append(
                JsonDefField(
                    parent=parent,
                    name=name,
                    alias=alias,
                    doc=doc,
                    is_dict=True,
                    key_type_info=key_info,
                    value_type_info=val_info,
                    ret_type_info=TypeInfo(
                        base=VariableType.JSON,
                        is_array=False,
                        is_optional=is_optional,
                        is_dict=True,
                        key_type_info=key_info,
                        value_type_info=val_info,
                        omitempty=may_miss,
                        skip=skip,
                    ),
                )
            )
            continue

        # Inline object / array block
        if node.children:
            name = node.name
            is_optional = name.endswith("?")
            name = name.rstrip("?")
            modifiers = []
            type_ = ""
            for arg in node.args:
                a = str(arg.value)
                raw = (
                    ctx.source_text[arg.span.start.offset : arg.span.end.offset]
                    if ctx.source_text
                    else ""
                )
                quoted = raw.startswith(('"', "'"))
                if a in {"@skip", "@omitempty"} and not quoted:
                    modifiers.append(a)
                elif a.startswith("@") and not quoted:
                    continue
                elif not type_:
                    type_ = a
            skip = "@skip" in modifiers
            may_miss = "@omitempty" in modifiers
            from_prop = node.get_prop("from")
            path_prop = node.get_prop("path")
            alias = ""
            if from_prop is not None:
                resolved = str(ctx.property_defines.get(from_prop, from_prop))
                if resolved:
                    alias = resolved
            elif path_prop is not None:
                resolved = str(ctx.property_defines.get(path_prop, path_prop))
                if resolved:
                    alias = resolved
            doc = node.get_prop("doc") or ""

            is_array = any(
                (arg.type_annotation or "").strip("()") == "array"
                for arg in node.args
            )
            if type_.endswith("?"):
                is_optional = True
                type_ = type_.rstrip("?")

            # Synthesize or use explicit name
            if type_:
                child_schema_name = type_
            else:
                child_schema_name = f"{parent.name}{to_pascal_case(name)}"

            # Find module ancestor for parent
            module_owner = parent.parent
            while module_owner is not None and not hasattr(
                module_owner, "body"
            ):
                module_owner = module_owner.parent

            sub_json_def = JsonDef(
                parent=module_owner or parent.parent,
                name=child_schema_name,
                is_array=False,
            )
            # Recursively parse inline fields
            parse_json_fields(node.children, sub_json_def, ctx, lint)
            # Register in ctx.json_defs ahead of parent
            ctx.json_defs[sub_json_def.name] = sub_json_def

            parent.body.append(
                JsonDefField(
                    parent=parent,
                    name=name,
                    ret_type_info=TypeInfo(
                        base=VariableType.JSON,
                        is_array=is_array,
                        is_optional=is_optional,
                        ref=child_schema_name,
                        omitempty=may_miss,
                        skip=skip,
                    ),
                    alias=alias,
                    doc=doc,
                )
            )
            continue

        name = node.name
        modifiers = []
        type_ = ""
        alias = ""
        for arg in node.args:
            a = str(arg.value)
            raw = (
                ctx.source_text[arg.span.start.offset : arg.span.end.offset]
                if ctx.source_text
                else ""
            )
            quoted = raw.startswith(('"', "'"))
            if a in {"@skip", "@omitempty"} and not quoted:
                modifiers.append(a)
            elif a.startswith("@") and not quoted:
                continue
            elif not type_:
                type_ = a
            else:
                alias = a
        skip = "@skip" in modifiers
        if not type_ and skip:
            type_ = "str"
        from_prop = node.get_prop("from")
        path_prop = node.get_prop("path")
        if from_prop is not None:
            resolved = str(ctx.property_defines.get(from_prop, from_prop))
            if resolved:
                alias = resolved
        elif path_prop is not None:
            resolved = str(ctx.property_defines.get(path_prop, path_prop))
            if resolved:
                alias = resolved
        is_array = any(
            (arg.type_annotation or "").strip("()") == "array"
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
                    (arg.type_annotation or "").strip("()") == "array"
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
