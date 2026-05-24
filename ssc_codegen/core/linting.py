"""Lint helpers — argument validation, CSS/XPath/regex validation, pipeline/predicate linting."""

from __future__ import annotations

import difflib as _difflib
import re as _re

from ssc_codegen.ast import JsonDefField, Module, VariableType
from ssc_codegen.ast.struct import PLACEHOLDER_RE, PLACEHOLDER_WIDE_RE
from ssc_codegen.kdl import KdlNode
from ssc_codegen.core.contexts import (
    DefineKind,
    LintContext,
    ParseContext,
)


# ── Argument validation ────────────────────────────────────────────────────────


def lint_require_args(
    node: KdlNode,
    lint: LintContext,
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


def lint_require_int_args(
    node: KdlNode, lint: LintContext, args: list[str]
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


# ── Pattern validation ─────────────────────────────────────────────────────────


def lint_validate_regex(node: KdlNode, lint: LintContext, pattern: str) -> bool:
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


def lint_validate_css(node: KdlNode, lint: LintContext, selector: str) -> bool:
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


def lint_validate_xpath(node: KdlNode, lint: LintContext, expr: str) -> bool:
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


# ── Pipeline op constants ──────────────────────────────────────────────────────


_NO_ARGS_OPS: frozenset[str] = frozenset(
    {
        "text",
        "raw",
        "normalize-space",
        "lower",
        "upper",
        "unescape",
        "first",
        "last",
        "len",
        "unique",
        "to-int",
        "to-float",
        "to-bool",
    }
)

_TRIM_OPS: frozenset[str] = frozenset({"trim", "ltrim", "rtrim"})
_RM_OPS: frozenset[str] = frozenset(
    {"rm-prefix", "rm-suffix", "rm-prefix-suffix"}
)
_PREDICATE_BLOCKS: frozenset[str] = frozenset(
    {"filter", "assert", "match", "not", "and", "or"}
)


def lint_require_predicate_ctx(node: KdlNode, lint: LintContext) -> bool:
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


def lint_require_assert_ctx(node: KdlNode, lint: LintContext) -> bool:
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


def lint_pipeline_op(node: KdlNode, lint: LintContext) -> None:
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
        lint_require_args(node, lint, min_count=1, example='attr "href"')

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
        lint_require_args(node, lint, exact=1, example=f'{name} "substring"')

    elif name == "fmt":
        args = lint_require_args(  # type: ignore[no-redef,assignment]
            node, lint, exact=1, example='fmt "prefix-{{}}-suffix"'
        )
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
            lint_require_args(node, lint, exact=2, example='repl "old" "new"')

    elif name in ("split", "join"):
        lint_require_args(node, lint, exact=1, example=f'{name} " "')

    elif name == "re":
        raw_args = lint.get_raw_args(node)
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example=f'{name} #"(\\d+)"#'
        )
        if args:
            pattern = args[0]
            if raw_args and raw_args[0].is_identifier:
                resolved = lint.resolve_scalar_arg(pattern)
                if resolved is not None:
                    pattern = resolved
            normalized = pattern.lstrip()
            if (
                lint_validate_regex(node, lint, normalized)
                and not lint.in_predicate
            ):
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
        if lint.in_predicate and not lint_require_assert_ctx(node, lint):
            return
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example='re-all #"(\\d+)"#'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "re-sub":
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=2, example='re-sub #"\\D"# ""'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "index":
        args = lint_require_args(node, lint, exact=1, example="index 0")  # type: ignore[assignment]
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "slice":
        args = lint_require_args(node, lint, exact=2, example="slice 0 10")  # type: ignore[assignment]
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "jsonify":
        lint_require_args(node, lint, exact=1, example="jsonify MySchema")

    elif name == "nested":
        lint_require_args(node, lint, exact=1, example="nested MyStruct")

    elif name == "self":
        args = lint_require_args(node, lint, exact=1, example="self field-name")  # type: ignore[assignment]
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
        "@doc",
        "@init",
        "@pre-validate",
        "@split-doc",
        "@key",
        "@value",
        "@table",
        "@rows",
        "@match",
    }:
        field_name = name[1:]
        if field_name not in lint.init_fields:
            lint.error(
                node,
                message=f"'@{field_name}': field '{field_name}' not found in @init block",
                code="E301",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
            )


def lint_predicate_op(node: KdlNode, lint: LintContext) -> None:
    """Validate a predicate operation node inside filter/assert/match."""
    name = lint.node_name(node)

    # string predicates
    if name in ("eq", "ne"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("starts", "ends", "contains", "in"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("len-eq", "len-ne"):
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, min_count=1, example=f"{name} 5")
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
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example=f"{name} 10")
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "len-range":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=2, example="len-range 1 100")
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "has-attr":
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example='has-attr "href"')

    elif name in (
        "attr-eq",
        "attr-ne",
        "attr-starts",
        "attr-ends",
        "attr-contains",
    ):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(
            node, lint, min_count=2, example=f'{name} "href" "value"'
        )

    elif name == "attr-re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(
            node, lint, exact=2, example='attr-re "href" #".*\\.com$"#'
        )
        if args:
            lint_validate_regex(node, lint, args[1])

    elif name == "text-re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(
            node, lint, exact=1, example='text-re #"\\d+"#'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name in ("text-starts", "text-ends", "text-contains"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name == "re-any":
        if not lint_require_assert_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example='re-any #"\\d+"#')
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name in ("gt", "lt", "ge", "le"):
        if not lint_require_assert_ctx(node, lint):
            return
        lint_require_args(node, lint, exact=1, example=f"{name} 42")

    elif name == "re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example='re #"(\\d+)"#')
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "css":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint.get_args(node)
        if args:
            selector = args[0]
            lint_validate_css(node, lint, selector)

    elif name == "xpath":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint.get_args(node)
        if args:
            lint_validate_xpath(node, lint, args[0])

    elif name == "range":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=2, example="range 1 100")
        if args:
            lint_require_int_args(node, lint, args)


# ── Wildcard op ────────────────────────────────────────────────────────────────

_EXTRA_PIPELINE_OPS: frozenset[str] = frozenset(
    {
        "transform",
        "filter",
        "assert",
        "match",
        "fallback",
        "self",
        "not",
        "and",
        "or",
    }
)

_PREDICATE_OPS: frozenset[str] = frozenset(
    {
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
        "attr-contains",
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


def lint_wildcard_op(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
    """Validate unknown ops in pipeline context."""
    from ssc_codegen.core.type_checking import _OP_TYPES

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
        if info.kind == DefineKind.SCALAR:
            lint.error(
                node,
                message=f"'{op_name}' is a scalar define — cannot be used as a pipeline operation",
                code="E001",
                hint=f"use a block define: define {op_name} {{ ... }}",
            )
        return

    _KNOWN_OPS: frozenset[str] = (
        frozenset(_OP_TYPES.keys()) | _EXTRA_PIPELINE_OPS | _PREDICATE_OPS
    )
    candidates = sorted(
        _KNOWN_OPS
        | {k for k, v in lint.defines.items() if v.kind == DefineKind.BLOCK}
        | set(lint.transforms)
    )
    suggestions = _difflib.get_close_matches(
        op_name, candidates, n=3, cutoff=0.6
    )
    if suggestions:
        hint = (
            "did you mean " + " or ".join(f"'{s}'" for s in suggestions) + "?"
        )
    else:
        hint = f"check spelling or declare it: define {op_name} {{ ... }}"
    lint.error(
        node,
        message=f"unknown operation '{op_name}'",
        code="E200",
        hint=hint,
    )


# ── Struct-level lint ──────────────────────────────────────────────────────────


_VALID_STRUCT_TYPES = frozenset(
    {"item", "list", "dict", "table", "flat", "rest"}
)

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


def lint_struct_node(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> None:
    """Validate struct-level rules."""

    struct_name = lint.get_arg(node, 0)
    if not struct_name:
        lint.error(
            node,
            message="'struct' requires a name",
            code="E001",
            hint="example: struct MyStruct { ... }",
        )
        return

    raw = node.type_annotation
    struct_type = raw[1:-1] if raw else (lint.get_prop(node, "type") or "item")
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
            message=f"struct type='{struct_type}' missing required field(s) "
            + ", ".join(missing),
            code="E401",
            hint=f"add: {', '.join(missing)}",
        )

    for field_node in fields:
        field_name = lint.node_name(field_node)
        if not field_name:
            continue
        if field_name.startswith("@"):
            lint_reserved_field(field_node, field_name, struct_type, lint)
        else:
            if struct_type == "rest":
                lint.error(
                    field_node,
                    message=f"regular field '{field_name}' not allowed in struct type='rest'",
                    code="E203",
                )
            else:
                lint_regular_field(
                    field_node, field_name, ctx, lint, struct_type=struct_type
                )


def lint_reserved_field(
    node: KdlNode, field_name: str, struct_type: str, lint: LintContext
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
            lint.error(
                node,
                message="'@doc' requires a description string",
                code="E001",
            )
    elif field_name == "@request":
        if not lint.get_arg(node, 0):
            lint.error(
                node,
                message="'@request' requires a raw HTTP string",
                code="E001",
            )
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
        check_args = lint.get_args(node)
        check_name = check_args[0] if check_args else None
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
    elif field_name == "@error":
        err_args = lint.get_args(node)
        if len(err_args) < 2:
            lint.error(
                node,
                message="@error requires both status and schema name",
                code="E001",
                hint="example: @error 404 ApiError",
            )
            return
        positional_keys = set(err_args[2:])
        property_keys = set(node.properties.keys())
        duplicates = positional_keys & property_keys
        if duplicates:
            lint.error(
                node,
                message=f"@error has duplicate keys: {', '.join(sorted(duplicates))}",
                code="E400",
                hint="each key must be either a positional arg (presence check) or a property (value check)",
            )


def lint_request_placeholders(
    node: KdlNode, raw_payload: str, lint: LintContext
) -> None:
    """Validate placeholder names in an @request raw payload.

    Convention: uppercase {{NAME}} is a define substitution (only resolved
    within ``define`` values), lowercase {{name}} is a runtime fetch() param.
    Define substitution does NOT run on @request payloads, so any remaining
    uppercase tokens are bugs that silently become literal strings.
    """
    for m in PLACEHOLDER_WIDE_RE.finditer(raw_payload):
        token = m.group(0)
        strict = PLACEHOLDER_RE.match(token)
        if strict is None:
            lint.error(
                node,
                message=f"malformed placeholder {token!r} in @request",
                code="E002",
                hint="expected syntax: {{name}} or {{name:type}} (lowercase)",
            )
            continue
        name = strict.group(1)
        if name != name.lower():
            lint.error(
                node,
                message=f"placeholder '{{{{{name}}}}}' in @request must be lowercase; "
                f"uppercase names are define substitutions which don't resolve in @request",
                code="E002",
                hint=f"use lowercase for runtime params (e.g. {{{{{name.lower()}}}}}), "
                f"or compose the URL in a define first",
            )


def lint_regular_field(
    node: KdlNode,
    field_name: str,
    ctx: ParseContext,
    lint: LintContext,
    *,
    struct_type: str = "item",
) -> None:
    from ssc_codegen.core.type_checking import check_pipeline_types

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
    check_pipeline_types(ops, ctx, lint, start_type=VariableType.DOCUMENT)


# ── Transform/Define lint ──────────────────────────────────────────────────────


_VALID_TRANSFORM_TYPES = frozenset(
    {t.name for t in VariableType if t.name not in ("AUTO", "LIST_AUTO")}
)


def lint_transform_node(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
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


# ── JSON field lint ──────────────────────────────────────────────────────────────


_VALID_JSON_MODIFIERS = frozenset({"@skip", "@omitempty"})
_VALID_JSON_TYPES = frozenset({"str", "int", "float", "bool", "null"})


def lint_json_node(node: KdlNode, lint: LintContext, ctx: ParseContext) -> None:
    """Validate json definition block and its fields."""

    # ── block-level checks ────────────────────────────────────────────────────

    name = lint.get_arg(node, 0)
    if not name:
        lint.error(
            node,
            message="'json' requires a name",
            code="E001",
            hint="example: json MySchema { ... }",
        )
        return

    if name in ctx.json_defs:
        lint.error(
            node,
            message=f"duplicate json definition '{name}'",
            code="E001",
            hint=f"rename or remove one of the 'json {name}' definitions",
        )

    path_prop = node.properties.get("path")
    if path_prop is not None:
        path_val = str(path_prop.value)
        if not path_val:
            lint.error(
                node,
                message="'path' property must be a non-empty string",
                code="E002",
                hint='example: json MySchema path="response.data" { ... }',
            )

    # ── field-level checks ───────────────────────────────────────────────────

    seen_fields: set[str] = set()
    _lint_json_children(lint.get_children_nodes(node), lint, ctx, seen_fields)


def _lint_json_children(
    children: list[KdlNode],
    lint: LintContext,
    ctx: ParseContext,
    seen_fields: set[str],
) -> None:
    """Lint json field children, expanding block define references."""
    for field_node in children:
        field_name = lint.node_name(field_node)
        args = lint.get_args(field_node)

        # Block define expansion
        if not args and field_name in ctx.children_defines:
            lint.push(field_name)
            _lint_json_children(
                ctx.children_defines[field_name], lint, ctx, seen_fields
            )
            lint.pop()
            continue

        has_type = False
        has_skip = False
        for arg in args:
            if arg.startswith("@"):
                if arg not in _VALID_JSON_MODIFIERS:
                    lint.error(
                        field_node,
                        message=f"unknown json field modifier '{arg}'",
                        code="E002",
                        hint=f"valid modifiers: {', '.join(sorted(_VALID_JSON_MODIFIERS))}",
                    )
                if arg == "@skip":
                    has_skip = True
            else:
                has_type = True
                raw_type = arg
                if raw_type.startswith("(array)"):
                    raw_type = raw_type[len("(array)") :]
                if raw_type.endswith("?"):
                    raw_type = raw_type[:-1]
                if raw_type not in _VALID_JSON_TYPES and raw_type:
                    # might be a ref type — that's checked in post-pass
                    pass

        if not has_type and not has_skip:
            lint.error(
                field_node,
                message=f"json field '{field_name}' requires a type",
                code="E001",
                hint="example: field-name str  or  field-name @skip",
            )

        if field_name in seen_fields:
            lint.error(
                field_node,
                message=f"duplicate json field '{field_name}'",
                code="E001",
                hint=f"remove or rename the duplicate '{field_name}' field",
            )
        seen_fields.add(field_name)


def lint_json_cross_refs(ctx: ParseContext, lint: LintContext) -> None:
    """Post-pass: validate json cross-references and detect circular refs."""

    for json_def in ctx.json_defs.values():
        kdl_node = lint.json_kdl_nodes.get(json_def.name)
        if not kdl_node:
            continue
        for field in json_def.body:
            if not isinstance(field, JsonDefField):
                continue
            ref = field.ref_name
            if ref and ref not in ctx.json_defs:
                lint.error(
                    kdl_node,
                    message=f"json field '{field.name}' references undefined json definition '{ref}'",
                    code="E300",
                    hint=f"define 'json {ref} {{ ... }}' or fix the type name",
                )

    # circular reference detection
    visited: set[str] = set()

    def _has_cycle(name: str, stack: set[str]) -> str | None:
        if name in stack:
            return name
        if name in visited:
            return None
        visited.add(name)
        stack.add(name)
        jd = ctx.json_defs.get(name)
        if jd:
            for field in jd.body:
                if not isinstance(field, JsonDefField):
                    continue
                ref = field.ref_name
                if ref:
                    cycle = _has_cycle(ref, stack)
                    if cycle:
                        stack.discard(name)
                        return cycle
        stack.discard(name)
        return None

    for name in list(ctx.json_defs):
        visited.clear()
        stack: set[str] = set()
        cycle = _has_cycle(name, stack)
        if cycle:
            kdl_node = lint.json_kdl_nodes.get(name)
            if kdl_node:
                lint.error(
                    kdl_node,
                    message=f"circular reference detected involving json definition '{name}'",
                    code="E300",
                    hint="break the cycle by removing or changing one of the referenced types",
                )
            break


def lint_rest_cross_refs(ctx: ParseContext, lint: LintContext) -> None:
    """Post-pass: validate @request response and @error schema references in REST structs."""
    for kdl_node, schema_name in lint.rest_response_refs:
        if schema_name not in ctx.json_defs:
            lint.error(
                kdl_node,
                message=f"@request response='{schema_name}' references undefined json definition '{schema_name}'",
                code="E300",
                hint=f"define 'json {schema_name} {{ ... }}' or fix the response name",
            )
    for kdl_node, schema_name in lint.rest_error_refs:
        if schema_name not in ctx.json_defs:
            lint.error(
                kdl_node,
                message=f"@error schema '{schema_name}' references undefined json definition '{schema_name}'",
                code="E300",
                hint=f"define 'json {schema_name} {{ ... }}' or fix the schema name",
            )


_DEFINE_NAME_RE = _re.compile(r"^[A-Z_][A-Z0-9_-]*\Z")


def lint_define_node(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
    """Validate module-level define."""
    children = lint.get_children_nodes(node)
    args = lint.get_args(node)
    if args:
        name = args[0]
        if not _DEFINE_NAME_RE.match(name):
            lint.error(
                node,
                message=f"define name '{name}' must be UPPER_CASE ([A-Z_][A-Z0-9_-]*)",
                code="E002",
                hint="use UPPER_CASE: define MY-VAR=... or define MY_BLOCK { ... }",
            )
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
