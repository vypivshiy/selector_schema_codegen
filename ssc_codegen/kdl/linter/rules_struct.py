"""
KDL DSL linter — struct structural rules.

Context-aware: rules know whether they're at module level,
inside a struct field list, or inside a field pipeline.
"""

from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.linter.base import LINTER, LintContext, DefineKind
from ssc_codegen.kdl.linter.type_rules import check_pipeline_types
from ssc_codegen.kdl.ast.types import VariableType as VT
from ssc_codegen.kdl.linter.type_rules import PIPELINE_TYPE_RULES

# ── known ops ──────────────────────────────────────────────────────────────────

_VALID_STRUCT_TYPES = frozenset({"item", "list", "dict", "table", "flat"})

_REQUIRED_RESERVED: dict[str, frozenset[str]] = {
    "item": frozenset(),
    "list": frozenset({"-split-doc"}),
    "dict": frozenset({"-key", "-value"}),
    "table": frozenset({"-table", "-row", "-match", "-value"}),
    "flat": frozenset(),
}

_RESERVED_ALLOWED: dict[str, frozenset[str] | None] = {
    "-doc": None,
    "-pre-validate": None,
    "-init": None,
    "-split-doc": frozenset({"list"}),
    "-key": frozenset({"dict"}),
    "-value": frozenset({"dict", "table"}),
    "-table": frozenset({"table"}),
    "-row": frozenset({"table"}),
    "-match": frozenset({"table"}),
}

# all valid pipeline operation names
_KNOWN_OPS: frozenset[str] = frozenset(PIPELINE_TYPE_RULES.keys()) | frozenset(
    {
        # control
        "filter",
        "assert",
        "match",
        "fallback",
        "self",
        # logic
        "not",
        "and",
        "or",
        # predicate ops
        "eq",
        "ne",
        "starts",
        "ends",
        "contains",
        "in",
        "len-eq",
        "len-ne",
        "len-gt",
        "len-lt",
        "len-ge",
        "len-le",
        "len-range",
        "has-attr",
        "attr-eq",
        "attr-ne",
        "attr-starts",
        "attr-ends",
        "attr-re",
        "text-re",
        "text-starts",
        "text-ends",
        "text-contains",
        "re-any",
        "gt",
        "lt",
        "ge",
        "le",
    }
)


# ── wildcard rule: fires for ops inside pipelines with no specific rule ────────


@LINTER.rule("*")
def rule_unknown_or_define_op(node: Node, ctx: LintContext) -> None:
    """
    Fired (by _walk) only when _in_pipeline=True and no specific rule exists.
    Checks: is this a valid block define ref, scalar define misuse, or unknown op?

    Note: unquoted identifier *arguments* (e.g. css-all a, attr href) are valid
    KDL2 string literals and are intentionally not validated here.
    """
    op_name = ctx.node_name(node)
    if not op_name:
        return

    info = ctx.defines.get(op_name)

    if info is not None:
        if info.kind == DefineKind.SCALAR:
            ctx.error(
                node,
                message=f"'{op_name}' is a scalar define — cannot be used as a pipeline operation",
                hint=f"scalar defines substitute argument values. "
                f"Use a block define: define {op_name} {{ ... }}",
            )
        # block define — valid
    else:
        ctx.error(
            node,
            message=f"unknown operation '{op_name}'",
            hint=f"check spelling or declare it: define {op_name} {{ ... }}",
        )


# Unquoted identifier args (e.g. css-all a, attr href, re-sub PATTERN "")
# are treated as plain strings per KDL2 semantics — no validation needed.
# Only ops that strictly require integers (index, slice, len-*) will naturally
# error via _require_int_args when int() fails on an identifier value.


# ── struct ─────────────────────────────────────────────────────────────────────


@LINTER.rule("struct")
def rule_struct(node: Node, ctx: LintContext) -> None:
    struct_name = ctx.get_arg(node, 0)
    if not struct_name:
        ctx.error(
            node,
            message="'struct' requires a name",
            hint="example: struct MyStruct { ... }",
        )
        return

    struct_type = ctx.get_prop(node, "type") or "item"
    if struct_type not in _VALID_STRUCT_TYPES:
        ctx.error(
            node,
            message=f"unknown struct type '{struct_type}'",
            hint=f"valid types: {', '.join(sorted(_VALID_STRUCT_TYPES))}",
        )
        return

    ctx.push(f"struct {struct_name}")

    fields = ctx.get_children_nodes(node)
    reserved_present = {
        ctx.node_name(f) for f in fields if ctx.node_name(f).startswith("-")
    }

    for req in _REQUIRED_RESERVED[struct_type]:
        if req not in reserved_present:
            ctx.error(
                node,
                message=f"struct type='{struct_type}' is missing required field '{req}'",
                hint=f"add '{req} {{ ... }}' inside the struct",
            )

    for field_node in fields:
        field_name = ctx.node_name(field_node)
        if not field_name:
            continue
        if field_name.startswith("-"):
            _check_reserved_field(field_node, field_name, struct_type, ctx)
        else:
            _check_regular_field(field_node, field_name, ctx)

    ctx.pop()


# ── reserved field checks ──────────────────────────────────────────────────────


def _check_reserved_field(
    node: Node,
    field_name: str,
    struct_type: str,
    ctx: LintContext,
) -> None:
    allowed = _RESERVED_ALLOWED.get(field_name)
    if allowed is not None and struct_type not in allowed:
        ctx.error(
            node,
            message=f"'{field_name}' is not allowed in struct type='{struct_type}'",
            hint=f"'{field_name}' is only valid in: {', '.join(sorted(allowed))}",
        )
        return

    if field_name == "-doc":
        if not ctx.get_arg(node, 0):
            ctx.error(
                node,
                message="'-doc' requires a description string",
                hint='example: -doc "description of this struct"',
            )
        return

    if field_name == "-init":
        sub_pipelines = ctx.get_children_nodes(node)
        if not sub_pipelines:
            ctx.error(
                node,
                message="'-init' block must contain at least one named pipeline",
                hint='-init {\n    my-field { css ".x"; text }\n}',
            )
        else:
            # type-check each named sub-pipeline and cache its ret type
            for sub in sub_pipelines:
                sub_name = ctx.node_name(sub)
                if not sub_name:
                    continue
                sub_ops = ctx.get_children_nodes(sub)
                if sub_ops:
                    ret = check_pipeline_types(
                        sub_ops, ctx, start_type=VT.DOCUMENT
                    )
                    ctx.inferred_define_types[sub_name] = (VT.DOCUMENT, ret)
        return

    ops = ctx.get_children_nodes(node)
    if not ops:
        ctx.error(
            node,
            message=f"'{field_name}' block must contain at least one operation",
            hint=f'example: {field_name} {{ css ".item" }}',
        )
    else:
        check_pipeline_types(ops, ctx, start_type=VT.DOCUMENT)


# ── regular field checks ───────────────────────────────────────────────────────


def _check_regular_field(node: Node, field_name: str, ctx: LintContext) -> None:
    ctx.push(field_name)
    ops = ctx.get_children_nodes(node)
    if not ops:
        ctx.error(
            node,
            message=f"field '{field_name}' has no operations",
            hint=f'add at least one operation: {field_name} {{ css ".item"; text }}',
        )
    else:
        # determine start type: DOCUMENT, or self-ref type from -init
        start = VT.DOCUMENT
        if ops and ctx.node_name(ops[0]) == "self":
            init_name = ctx.get_arg(ops[0], 0)
            if init_name and init_name in ctx.inferred_define_types:
                _, start = ctx.inferred_define_types[init_name]
        check_pipeline_types(ops, ctx, start_type=start)
    ctx.pop()


# ── define ─────────────────────────────────────────────────────────────────────


@LINTER.rule("define")
def rule_define(node: Node, ctx: LintContext) -> None:
    children = ctx.get_children_nodes(node)
    has_prop = any(
        sub.type == "prop"
        for child in node.children
        if child.type == "node_field"
        for sub in child.children
    )
    args = ctx.get_args(node)

    if children:
        if not args:
            ctx.error(
                node,
                message="block 'define' requires a name",
                hint='example: define EXTRACT-HREF { css "a"; attr "href" }',
            )
    elif not has_prop:
        ctx.error(
            node,
            message="'define' must be scalar (NAME=value) or block (NAME { ... })",
            hint="examples:\n"
            '  define MY_URL="https://example.com"\n'
            '  define EXTRACT { css "a"; attr "href" }',
        )
