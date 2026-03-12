"""
KDL DSL linter — struct structural rules.

Context-aware: rules know whether they're at module level,
inside a struct field list, or inside a field pipeline.
"""

from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.linter.base import LINTER, LintContext
from ssc_codegen.kdl.linter.types import ErrorCode, DefineKind
from ssc_codegen.kdl.linter.type_rules import check_pipeline_types, _parse_vt
from ssc_codegen.kdl.ast.types import VariableType as VT
from ssc_codegen.kdl.linter.type_rules import PIPELINE_TYPE_RULES

_VALID_TRANSFORM_TYPES = frozenset({t.name for t in VT if t.name not in ("AUTO", "LIST_AUTO")})

# ── known ops ──────────────────────────────────────────────────────────────────

_VALID_STRUCT_TYPES = frozenset({"item", "list", "dict", "table", "flat"})

_REQUIRED_RESERVED: dict[str, frozenset[str]] = {
    "item": frozenset(),
    "list": frozenset({"@split-doc"}),
    "dict": frozenset({"@split-doc", "@key", "@value"}),
    "table": frozenset({"@table", "@rows", "@match", "@value"}),
    "flat": frozenset(),
}

_RESERVED_ALLOWED: dict[str, frozenset[str] | None] = {
    "@doc": None,
    "@pre-validate": None,
    "@init": None,
    "@split-doc": frozenset({"list", "dict"}),  # dict can also use @split-doc
    "@key": frozenset({"dict"}),
    "@value": frozenset({"dict", "table"}),
    "@table": frozenset({"table"}),
    "@rows": frozenset({"table"}),
    "@match": frozenset({"table"}),
}

# all valid pipeline operation names
_KNOWN_OPS: frozenset[str] = frozenset(PIPELINE_TYPE_RULES.keys()) | frozenset(
    {
        # transform call (pipeline op — references a module-level transform)
        "transform",
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
    Checks: is this a valid block define ref, scalar define misuse, @init reference, or unknown op?

    Note: unquoted identifier *arguments* (e.g. css-all a, attr href) are valid
    KDL2 string literals and are intentionally not validated here.
    """
    op_name = ctx.node_name(node)
    if not op_name:
        return

    # Check if it's a reference to @init field: @field-name
    if op_name.startswith("@"):
        field_name = op_name[1:]  # Remove @ prefix
        if field_name not in ctx.init_fields:
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'@{field_name}': field '{field_name}' not found in @init block",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}"
            )
        return

    info = ctx.defines.get(op_name)

    if info is not None:
        if info.kind == DefineKind.SCALAR:
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'{op_name}' is a scalar define — cannot be used as a pipeline operation",
                hint=f"scalar defines substitute argument values. "
                f"Use a block define: define {op_name} {{ ... }}",
            )
        # block define — valid
    else:
        ctx.error(
            node,
            ErrorCode.UNKNOWN_OPERATION,
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
            ErrorCode.MISSING_ARGUMENT,
            message="'struct' requires a name",
            hint="example: struct MyStruct { ... }",
        )
        return

    struct_type = ctx.get_prop(node, "type") or "item"
    if struct_type not in _VALID_STRUCT_TYPES:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"unknown struct type '{struct_type}'",
            hint=f"valid types: {', '.join(sorted(_VALID_STRUCT_TYPES))}",
        )
        return

    ctx.push(f"struct {struct_name}")

    fields = ctx.get_children_nodes(node)
    reserved_present = {
        ctx.node_name(f) for f in fields if ctx.node_name(f).startswith("@")
    }

    for req in _REQUIRED_RESERVED[struct_type]:
        if req not in reserved_present:
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"struct type='{struct_type}' is missing required field '{req}'",
                hint=f"add '{req} {{ ... }}' inside the struct",
            )

    for field_node in fields:
        field_name = ctx.node_name(field_node)
        if not field_name:
            continue
        if field_name.startswith("@"):
            _check_reserved_field(field_node, field_name, struct_type, ctx)
        else:
            _check_regular_field(field_node, field_name, ctx, struct_type=struct_type)

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
            ErrorCode.MISSING_ARGUMENT,
            message=f"'{field_name}' is not allowed in struct type='{struct_type}'",
            hint=f"'{field_name}' is only valid in: {', '.join(sorted(allowed))}",
        )
        return

    if field_name == "@doc":
        if not ctx.get_arg(node, 0):
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@doc' requires a description string",
                hint='example: @doc "description of this struct"',
            )
        return

    if field_name == "@init":
        sub_pipelines = ctx.get_children_nodes(node)
        if not sub_pipelines:
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@init' block must contain at least one named pipeline",
                hint='@init {\n    my-field { css ".x"; text }\n}',
            )
        else:
            # type-check each named sub-pipeline and cache its ret type
            for sub in sub_pipelines:
                sub_name = ctx.node_name(sub)
                if not sub_name:
                    continue
                # Register InitField name for 'self' validation
                ctx.init_fields.add(sub_name)
                sub_ops = ctx.get_children_nodes(sub)
                
                # Check for single-line define reference (e.g., { CSS-ALL-ATTRS })
                if not sub_ops:
                    # Look for a single identifier in node_children (define reference)
                    for child in sub.children:
                        if child.type == "node_children":
                            identifiers = [c for c in child.children if c.type == "identifier"]
                            if len(identifiers) == 1:
                                define_name = identifiers[0].text.decode()
                                if define_name in ctx.defines and ctx.defines[define_name].kind == DefineKind.BLOCK:
                                    # Expand the define block and get its operations
                                    from ssc_codegen.kdl.linter.type_rules import _get_define_ops
                                    expanded_ops = _get_define_ops(define_name, ctx)
                                    if expanded_ops:
                                        sub_ops = expanded_ops
                            break
                
                if sub_ops:
                    ret = check_pipeline_types(
                        sub_ops, ctx, start_type=VT.DOCUMENT
                    )
                    ctx.inferred_define_types[sub_name] = (VT.DOCUMENT, ret)
        return

    ops = ctx.get_children_nodes(node)
    
    # Check for single-line operations (e.g., { css-all ".item" } or { attr "name" })
    # These appear as identifiers directly in node_children, not as wrapped nodes
    has_single_line = False
    if not ops:
        # Check if there's at least one identifier (operation) in the node_children
        for child in node.children:
            if child.type == "node_children":
                identifiers = [c for c in child.children if c.type == "identifier"]
                if identifiers:
                    has_single_line = True
                break
    
    if not ops and not has_single_line:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'{field_name}' block must contain at least one operation",
            hint=f'example: {field_name} {{ css ".item" }}',
        )
    else:
        # For @key and @value in dict, allow 'attr' and other selector operations
        # For @split-doc, allow css-all and other selector operations  
        # Skip type checking for single-line ops (they're not in standard node format)
        if ops:
            check_pipeline_types(ops, ctx, start_type=VT.DOCUMENT)


# ── regular field checks ───────────────────────────────────────────────────────


def _check_regular_field(
    node: Node,
    field_name: str,
    ctx: LintContext,
    *,
    struct_type: str = "item",
) -> None:
    ctx.push(field_name)
    ops = ctx.get_children_nodes(node)
    
    # Check if field has only 'nested' - this is valid, skip type checking
    # Handle both multiline (nested as a node) and single-line ({ nested MyStruct })
    if len(ops) == 1 and ctx.node_name(ops[0]) == "nested":
        ctx.pop()
        return
    if len(ops) == 0 and ctx.has_single_line_op(node, "nested"):
        ctx.pop()
        return
    
    if not ops:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"field '{field_name}' has no operations",
            hint=f'add at least one operation: {field_name} {{ css ".item"; text }}',
        )
        ctx.pop()
        return
    
    # For table fields the pipeline starts with 'match { ... }' which
    # accepts DOCUMENT and returns STRING (the value cell from @value).
    # So start_type is always DOCUMENT here — match handles the transition.
    # For regular fields: DOCUMENT, unless self-ref from @init.
    start = VT.DOCUMENT
    if struct_type == "table":
        # table fields MUST start with match { ... }
        if not ops or ctx.node_name(ops[0]) != "match":
            ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"table field '{field_name}' must start with 'match {{ ... }}'",
                hint=f"example: {field_name} {{ match {{ eq \"value\" }} }}",
            )
    elif ops and ctx.node_name(ops[0]) == "self":
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
            ErrorCode.MISSING_ARGUMENT,
            message="block 'define' requires a name",
                hint='example: define EXTRACT-HREF { css "a"; attr "href" }',
            )
    elif not has_prop:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'define' must be scalar (NAME=value) or block (NAME { ... })",
            hint="examples:\n"
            '  define MY_URL="https://example.com"\n'
            '  define EXTRACT { css "a"; attr "href" }',
        )


# ── transform (module-level) ───────────────────────────────────────────────────


@LINTER.rule("transform")
def rule_transform(node: Node, ctx: LintContext) -> None:
    """
    Validate module-level transform definition:
      transform NAME accept=TYPE return=TYPE { lang { import "..."; code "..." } ... }

    Pipeline calls (transform <name> inside a field) are handled by type_rules
    and have no accept=/return= props — skip them here.
    """
    # distinguish module-level definition from pipeline call:
    # a definition always has accept= or return= properties; a call does not.
    accept_str = ctx.get_prop(node, "accept")
    ret_str = ctx.get_prop(node, "return")
    lang_nodes = ctx.get_children_nodes(node)
    is_definition = bool(accept_str or ret_str or lang_nodes)
    if not is_definition:
        # pipeline call — handled by type_rules; nothing to validate here
        return

    args = ctx.get_args(node)
    if not args:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'transform' requires a name",
            hint='example: transform to-base64 accept=STRING return=STRING { py { code "..." } }',
        )
        return

    name = args[0]

    # validate accept= and return= properties
    accept_str = ctx.get_prop(node, "accept")
    ret_str = ctx.get_prop(node, "return")

    if not accept_str:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}' missing required property 'accept'",
            hint=f"example: transform {name} accept=STRING return=STRING {{ ... }}",
        )
    elif accept_str not in _VALID_TRANSFORM_TYPES:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}': invalid accept type '{accept_str}' (AUTO is not allowed)",
            hint=f"valid types: {', '.join(sorted(_VALID_TRANSFORM_TYPES))}",
        )

    if not ret_str:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}' missing required property 'return'",
            hint=f"example: transform {name} accept=STRING return=STRING {{ ... }}",
        )
    elif ret_str not in _VALID_TRANSFORM_TYPES:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}': invalid return type '{ret_str}' (AUTO is not allowed)",
            hint=f"valid types: {', '.join(sorted(_VALID_TRANSFORM_TYPES))}",
        )

    # validate language blocks
    lang_nodes = ctx.get_children_nodes(node)
    if not lang_nodes:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}' has no language implementations",
            hint="add at least one language block, e.g.: py { code \"{{NXT}} = {{PRV}}\" }",
        )
        return

    for lang_node in lang_nodes:
        lang = ctx.node_name(lang_node)
        if not lang:
            continue
        # get impl nodes: support both multiline (proper [node] children)
        # and single-line (bare [identifier] + [node_field] directly under [node_children])
        impl_nodes = ctx.get_children_nodes(lang_node)
        has_code = False

        if impl_nodes:
            # multiline format: code/import are proper child nodes
            for impl_node in impl_nodes:
                impl_name = ctx.node_name(impl_node)
                if impl_name == "code":
                    has_code = True
                    if not ctx.get_args(impl_node):
                        ctx.error(
                            impl_node,
                            message=f"'transform {name}' > '{lang}' > 'code' requires a string argument",
                            hint='example: code "{{NXT}} = {{PRV}}"',
                        )
                elif impl_name == "import":
                    if not ctx.get_args(impl_node):
                        ctx.error(
                            impl_node,
                            message=f"'transform {name}' > '{lang}' > 'import' requires a string argument",
                            hint='example: import "from base64 import b64decode"',
                        )
                elif impl_name:
                    ctx.error(
                        impl_node,
                        message=f"'transform {name}' > '{lang}': unknown keyword '{impl_name}'",
                        hint="only 'import' and 'code' are allowed inside language blocks",
                    )
        else:
            # single-line format: code/import appear as bare identifiers
            # directly under node_children of the lang node
            for child in lang_node.children:
                if child.type == "node_children":
                    bare_names = [
                        c.text.decode()
                        for c in child.children
                        if c.type == "identifier"
                    ]
                    if "code" in bare_names:
                        has_code = True
                    break

        if not has_code:
            ctx.error(
                lang_node,
                message=f"'transform {name}' > '{lang}' has no 'code' statement",
                hint='add: code "{{NXT}} = {{PRV}}"',
            )
