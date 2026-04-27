"""
KDL DSL linter — struct structural rules.

Context-aware: rules know whether they're at module level,
inside a struct field list, or inside a field pipeline.
"""

from __future__ import annotations

import difflib
from typing import Callable

from ssc_codegen.linter._kdl_lang import Node

from ssc_codegen.linter.base import LINTER, LintContext
from ssc_codegen.linter.types import ErrorCode, DefineKind
from ssc_codegen.linter.type_rules import check_pipeline_types
from ssc_codegen.ast.types import VariableType as VT
from ssc_codegen.linter.type_rules import PIPELINE_TYPE_RULES
from ssc_codegen.ast.struct import (
    _PLACEHOLDER_RE,
    _PLACEHOLDER_WIDE_RE,
    _parse_placeholder,
)

_VALID_TRANSFORM_TYPES = frozenset(
    {t.name for t in VT if t.name not in ("AUTO", "LIST_AUTO")}
)

# ── known ops ──────────────────────────────────────────────────────────────────

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
    "@split-doc": frozenset({"list", "dict"}),  # dict can also use @split-doc
    "@key": frozenset({"dict"}),
    "@value": frozenset({"dict", "table"}),
    "@table": frozenset({"table"}),
    "@rows": frozenset({"table"}),
    "@match": frozenset({"table"}),
    "@error": frozenset({"rest"}),
}

# Minimal boilerplate snippets for required fields (used in "did you mean" hints).
_FIELD_SNIPPET: dict[str, str] = {
    "@split-doc": '@split-doc { css-all "..." }',
    "@key": '@key { attr "..." }',
    "@value": '@value { attr "..." }',
    "@table": '@table { css "..." }',
    "@rows": '@rows { css-all "..." }',
    "@match": '@match { css "..." }',
}

# ops not tracked in PIPELINE_TYPE_RULES (type-transparent or handled specially)
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

# predicate/assert-only ops (no type signatures)
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

# all valid pipeline operation names
_KNOWN_OPS: frozenset[str] = (
    frozenset(PIPELINE_TYPE_RULES.keys()) | _EXTRA_PIPELINE_OPS | _PREDICATE_OPS
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
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
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
        # Build candidate pool: built-in ops + block defines + transforms
        candidates = sorted(
            _KNOWN_OPS
            | {k for k, v in ctx.defines.items() if v.kind == DefineKind.BLOCK}
            | set(ctx.transforms)
        )
        suggestions = difflib.get_close_matches(
            op_name, candidates, n=3, cutoff=0.6
        )
        if suggestions:
            quoted = " or ".join(f"'{s}'" for s in suggestions)
            hint = f"did you mean {quoted}?"
        else:
            hint = f"check spelling or declare it: define {op_name} {{ ... }}"
        ctx.error(
            node,
            ErrorCode.UNKNOWN_OPERATION,
            message=f"unknown operation '{op_name}'",
            hint=hint,
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

    missing = sorted(_REQUIRED_RESERVED[struct_type] - reserved_present)
    if missing:
        fields_str = " and ".join(f"'{f}'" for f in missing)
        snippet_lines = "\n        ".join(
            _FIELD_SNIPPET.get(f, f"{f} {{ ... }}") for f in missing
        )
        ctx.error(
            node,
            ErrorCode.MISSING_SPECIAL_FIELD,
            message=(
                f"struct type='{struct_type}' is missing required field"
                + ("s " if len(missing) > 1 else " ")
                + fields_str
            ),
            hint=f"add required fields:\n        {snippet_lines}",
        )

    for field_node in fields:
        field_name = ctx.node_name(field_node)
        if not field_name:
            continue
        if field_name.startswith("@"):
            _check_reserved_field(field_node, field_name, struct_type, ctx)
        else:
            if struct_type == "rest":
                ctx.error(
                    field_node,
                    ErrorCode.MISSING_ARGUMENT,
                    message=(
                        f"regular field '{field_name}' is not allowed "
                        "in struct type='rest'"
                    ),
                    hint=(
                        "type=rest struct contains only @request and @error "
                        "directives; output shape is defined by the json "
                        "schema referenced in response="
                    ),
                )
            else:
                _check_regular_field(
                    field_node, field_name, ctx, struct_type=struct_type
                )

    _check_request_uniqueness(fields, ctx, struct_type=struct_type)
    _check_request_placeholders(fields, ctx)
    if struct_type == "rest":
        _check_rest_errors(fields, ctx)

    ctx.pop()


# ── @request uniqueness ────────────────────────────────────────────────────────


def _check_request_uniqueness(
    fields: list, ctx: LintContext, *, struct_type: str = "item"
) -> None:
    """At most one unnamed @request; no duplicate resolved method names.
    For type=rest with multiple @request, name= is required on every one."""
    request_nodes = [f for f in fields if ctx.node_name(f) == "@request"]
    if len(request_nodes) <= 1:
        return

    if struct_type == "rest":
        for node in request_nodes:
            name = ctx.get_prop(node, "name") or ""
            if not name:
                ctx.error(
                    node,
                    ErrorCode.MISSING_ARGUMENT,
                    message=(
                        "@request in struct type='rest' with multiple "
                        "requests requires name="
                    ),
                    hint='add name=<identifier>: @request name="get-one" """..."""',
                )

    seen: dict[str, object] = {}
    for node in request_nodes:
        name = ctx.get_prop(node, "name") or ""
        if name in seen:
            if name:
                message = (
                    f'duplicate @request name="{name}": method name collision'
                )
                hint = "each @request must have a unique name= value"
            else:
                message = "duplicate unnamed @request: only one unnamed @request is allowed per struct"
                hint = 'add name= to extra @request blocks: @request name="by-slug" """..."""'
            ctx.error(
                node, ErrorCode.MISSING_ARGUMENT, message=message, hint=hint
            )
        else:
            seen[name] = node


_PY_JS_RESERVED = frozenset(
    {
        # common between Python and JS — avoid either-language collisions
        "class",
        "const",
        "return",
        "for",
        "if",
        "else",
        "while",
        "do",
        "switch",
        "case",
        "break",
        "continue",
        "try",
        "catch",
        "finally",
        "throw",
        "new",
        "this",
        "import",
        "export",
        "from",
        "as",
        "default",
        "true",
        "false",
        "null",
        "none",
        "in",
        "of",
        "void",
        "delete",
        "function",
        "def",
        "lambda",
        "pass",
        "yield",
        "global",
        "nonlocal",
        "raise",
        "except",
        "with",
        "and",
        "or",
        "not",
        "is",
        "let",
        "var",
        "typeof",
        "instanceof",
    }
)

_VALID_PRIMS = ("str", "int", "float", "bool")
_VALID_STYLES = ("repeat", "csv", "bracket", "pipe", "space")


def _check_request_placeholders(fields: list, ctx: LintContext) -> None:
    """Validate typed placeholders inside @request payloads.

    Rules (plan §3):
    1. conflicting types for the same NAME within one @request
    2. style |xxx used without [] array marker
    3. unknown primitive type
    4. unknown style token
    5. NAME (post-normalization) collides with Python/JS keyword
    6. malformed placeholder (e.g. {{_foo}}, {{1x}}, {{foo:bogus}}) — caught
       via the widened regex
    7. placeholder with [] inside URL path segment (not query/headers/body)
    8. ? on a path-segment placeholder (path cannot be optional)
    """
    for node in fields:
        if ctx.node_name(node) != "@request":
            continue
        raw = ctx.get_arg(node, 0)
        if not isinstance(raw, str) or not raw:
            continue

        strict_spans = {
            (m.start(), m.end()) for m in _PLACEHOLDER_RE.finditer(raw)
        }
        for wm in _PLACEHOLDER_WIDE_RE.finditer(raw):
            if (wm.start(), wm.end()) in strict_spans:
                continue
            inner = wm.group(1)
            # diagnose which dimension is off
            reason = _diagnose_placeholder(inner)
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=f"invalid placeholder '{{{{{inner}}}}}': {reason}",
                hint=(
                    "syntax: {{name[:type][[]][?][|style]}}; "
                    "name must start with a letter; "
                    f"type ∈ {{{', '.join(_VALID_PRIMS)}}}; "
                    f"style ∈ {{{', '.join(_VALID_STYLES)}}}"
                ),
            )

        specs_by_name: dict = {}
        for m in _PLACEHOLDER_RE.finditer(raw):
            ph = _parse_placeholder(m)
            # rule 2: style requires array
            if ph.style is not None and not ph.is_array:
                ctx.error(
                    node,
                    ErrorCode.MISSING_ARGUMENT,
                    message=(
                        f"placeholder '{ph.name}': style |{ph.style} "
                        "requires array [] modifier"
                    ),
                    hint=f"use {{{{{ph.name}:{ph.type_name}[]|{ph.style}}}}} instead",
                )
            # rule 1: conflicting spec for the same name
            prev = specs_by_name.get(ph.name)
            if prev is not None and prev != ph:
                ctx.error(
                    node,
                    ErrorCode.MISSING_ARGUMENT,
                    message=(
                        f"placeholder '{ph.name}' declared with "
                        "conflicting types in the same @request"
                    ),
                    hint=(
                        "each placeholder name must use an identical "
                        "type/array/optional/style across occurrences"
                    ),
                )
            else:
                specs_by_name[ph.name] = ph
            # rule 5: keyword collision (name is kebab-case here; normalize
            # to lowercase snake for keyword check — covers both targets)
            candidate = ph.name.replace("-", "_").lower()
            if candidate in _PY_JS_RESERVED:
                ctx.error(
                    node,
                    ErrorCode.MISSING_ARGUMENT,
                    message=(
                        f"placeholder name '{ph.name}' collides with a "
                        "Python/JS reserved keyword"
                    ),
                    hint="rename to a non-keyword identifier",
                )
            # rules 7,8: URL-path restrictions
            if _is_path_span(raw, m.start(), m.end()):
                if ph.is_array:
                    ctx.error(
                        node,
                        ErrorCode.MISSING_ARGUMENT,
                        message=(
                            f"placeholder '{ph.name}': array [] is not "
                            "allowed inside the URL path"
                        ),
                        hint="arrays belong in query/headers/body, not path",
                    )
                if ph.is_optional:
                    ctx.error(
                        node,
                        ErrorCode.MISSING_ARGUMENT,
                        message=(
                            f"placeholder '{ph.name}': optional ? is not "
                            "allowed inside the URL path"
                        ),
                        hint="path segments cannot be omitted — rethink the endpoint",
                    )


def _diagnose_placeholder(inner: str) -> str:
    """Best-effort reason why '{{…}}' didn't match strict grammar."""
    if not inner:
        return "empty"
    if not inner[0].isalpha():
        return f"name must start with a letter, got {inner[0]!r}"
    if ":" in inner:
        _, _, tail = inner.partition(":")
        # strip trailing array/optional/style before checking prim
        prim = tail.split("[")[0].split("?")[0].split("|")[0]
        if prim and prim not in _VALID_PRIMS:
            return f"unknown type {prim!r} (expected one of {_VALID_PRIMS})"
    if "|" in inner:
        style = inner.split("|", 1)[1]
        if style not in _VALID_STYLES:
            return f"unknown style {style!r} (expected one of {_VALID_STYLES})"
    return "malformed — check token order: name[:type][[]][?][|style]"


def _is_path_span(raw: str, start: int, end: int) -> bool:
    """True when the match is in the URL-path portion of the first request-line.

    Handles indented multiline payloads — locates the first non-empty line and
    finds the URI within it allowing leading whitespace.
    """
    # find the first non-empty line
    pos = 0
    while pos < len(raw):
        nl = raw.find("\n", pos)
        line_end = nl if nl >= 0 else len(raw)
        line = raw[pos:line_end]
        if line.strip():
            break
        pos = line_end + 1
    else:
        return False

    stripped = line.strip()
    # request-line format: METHOD URI HTTP/x.y
    parts = stripped.split(" ", 2)
    if len(parts) < 3 or not parts[2].startswith("HTTP/"):
        return False
    # uri substring location inside raw:
    uri_in_line = stripped.index(parts[1], len(parts[0]))
    leading_ws = len(line) - len(line.lstrip())
    uri_start_in_raw = pos + leading_ws + uri_in_line
    uri = parts[1]
    q = uri.find("?")
    path_end_in_raw = uri_start_in_raw + (q if q >= 0 else len(uri))
    return uri_start_in_raw <= start < path_end_in_raw


def _check_rest_errors(fields: list, ctx: LintContext) -> None:
    """Validate @error directives inside type=rest struct.

    Syntax: @error <status_code> <SchemaName> [key=value ...]
    - key=value are body field conditions (multiple = AND)
    - Dot-notation for nested: error.success=#false, data.0.type="error"
    - No properties = status-only check
    - 2xx status requires at least one condition
    """
    error_nodes = [f for f in fields if ctx.node_name(f) == "@error"]
    seen: dict[tuple[int, frozenset[tuple[str, str]]], object] = {}
    for node in error_nodes:
        args = ctx.get_args(node)
        if len(args) < 1:
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message="'@error' requires status code and schema name",
                hint="example: @error 404 ApiError  or  @error 200 success=#false ErrSchema",
            )
            continue
        status_raw = args[0]
        try:
            status = int(status_raw)
        except (TypeError, ValueError):
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=f"'@error' status must be integer, got {status_raw!r}",
                hint="example: @error 404 ApiError",
            )
            continue
        if not 100 <= status <= 599:
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=f"'@error' status {status} out of range [100..599]",
                hint="HTTP status codes are 3-digit integers in [100..599]",
            )
            continue
        if len(args) < 2:
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message="'@error' requires schema name after status",
                hint="example: @error 404 ApiError",
            )
            continue

        # collect all properties as conditions (key=value pairs)
        conditions = _collect_error_conditions(node, ctx)

        if 200 <= status < 300 and not conditions:
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=(
                    f"'@error' on 2xx status {status} requires at least one "
                    "body field condition"
                ),
                hint=(
                    "without conditions, every 2xx response would be treated "
                    "as an error; add field=value to disambiguate\n"
                    f"example: @error {status} {args[1]} success=#false"
                ),
            )
            continue

        key = (status, frozenset(conditions.items()))
        if key in seen:
            cond_str = (
                " ".join(f"{k}={v}" for k, v in sorted(conditions.items()))
                if conditions
                else "(status-only)"
            )
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=f"duplicate @error {status} {cond_str}",
                hint="each (status, conditions) combination must be unique within a struct",
            )
        else:
            seen[key] = node


def _collect_error_conditions(node: Node, ctx: LintContext) -> dict[str, str]:
    """Extract all key=value conditions from an @error node as a dict."""
    conditions: dict[str, str] = {}
    for child in node.children:
        if child.type != "node_field":
            continue
        for sub in child.children:
            if sub.type != "prop":
                continue
            if not sub.children:
                continue
            key = sub.children[0].text.decode()
            value = ctx.navigator._extract_value(sub.children[2])
            conditions[key] = value
    return conditions


# ── reserved field checks ──────────────────────────────────────────────────────


def _check_doc_field(node: Node, field_name: str, ctx: LintContext) -> None:
    if not ctx.get_arg(node, 0):
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@doc' requires a description string",
            hint='example: @doc "description of this struct"',
        )


def _check_request_field(node: Node, field_name: str, ctx: LintContext) -> None:
    if not ctx.get_arg(node, 0):
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@request' requires a raw http or POSIX cURL string",
            hint='example: @request "curl https://httpbin.org/get"',
            notes=[
                "You can copy-paste cURL or raw http requests from browser devtools or sniffer"
            ],
        )


def _check_error_field(node: Node, field_name: str, ctx: LintContext) -> None:
    # detailed validation is centralised in _check_rest_errors
    pass


def _check_check_field(node: Node, field_name: str, ctx: LintContext) -> None:
    sub_pipelines = ctx.get_children_nodes(node)
    if not sub_pipelines:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@check' block must contain at least one named pipeline",
            hint='@check {\n    is-cond { css ".x"; to-bool }\n}',
            notes=[
                "combine checks via assert { ... } blocks and guard "
                "fallback #true / fallback #false exprs"
            ],
        )
        return

    for sub in sub_pipelines:
        sub_name = ctx.node_name(sub)
        if not sub_name:
            continue
        ops = ctx.get_children_nodes(sub)
        bare = ctx.get_bare_op_container(sub)
        if bare is not None:
            ops = [*ops, bare]
        if not ops:
            continue
        ret = check_pipeline_types(ops, ctx, start_type=VT.DOCUMENT)
        if ret != VT.BOOL and ret != VT.AUTO:
            ctx.error(
                sub,
                ErrorCode.TYPE_MISMATCH,
                message=(
                    f"@check '{sub_name}' pipeline returns {ret.name}, "
                    "expected BOOL"
                ),
                hint="add 'to-bool' at the end, or use "
                "'fallback #true' / 'fallback #false'",
            )


def _check_init_field(node: Node, field_name: str, ctx: LintContext) -> None:
    sub_pipelines = ctx.get_children_nodes(node)
    if not sub_pipelines:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'@init' block must contain at least one named pipeline",
            hint='@init {\n    my-field { css ".x"; text }\n}',
        )
        return

    for sub in sub_pipelines:
        sub_name = ctx.node_name(sub)
        if not sub_name:
            continue
        ctx.init_fields.add(sub_name)
        sub_ops = ctx.get_children_nodes(sub)

        # Check for single-line define reference
        if not sub_ops:
            for child in sub.children:
                if child.type == "node_children":
                    identifiers = [
                        c for c in child.children if c.type == "identifier"
                    ]
                    if len(identifiers) == 1:
                        define_name = identifiers[0].text.decode()
                        if (
                            define_name in ctx.defines
                            and ctx.defines[define_name].kind
                            == DefineKind.BLOCK
                        ):
                            from ssc_codegen.linter.type_rules import (
                                _get_define_ops,
                            )

                            expanded_ops = _get_define_ops(define_name, ctx)
                            if expanded_ops:
                                sub_ops = expanded_ops
                    break

        if sub_ops:
            ret = check_pipeline_types(sub_ops, ctx, start_type=VT.DOCUMENT)
            ctx.inferred_define_types[sub_name] = (VT.DOCUMENT, ret)


def _check_default_field(node: Node, field_name: str, ctx: LintContext) -> None:
    ops = ctx.get_children_nodes(node)
    bare_container = ctx.get_bare_op_container(node)
    has_bare_op = bare_container is not None

    if not ops and not has_bare_op:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'{field_name}' block must contain at least one operation",
            hint=f'example: {field_name} {{ css ".item" }}',
        )
    else:
        all_ops = list(ops)
        if has_bare_op and bare_container is not None:
            all_ops.append(bare_container)
        check_pipeline_types(all_ops, ctx, start_type=VT.DOCUMENT)


_RESERVED_FIELD_CHECKS: dict[str, Callable] = {
    "@doc": _check_doc_field,
    "@request": _check_request_field,
    "@error": _check_error_field,
    "@check": _check_check_field,
    "@init": _check_init_field,
}


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

    checker = _RESERVED_FIELD_CHECKS.get(field_name, _check_default_field)
    checker(node, field_name, ctx)


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

    # Check for bare trailing op (KDL 2.0: last op without `;` is not wrapped in node)
    bare_container = ctx.get_bare_op_container(node)
    has_bare_op = bare_container is not None

    if not ops and not has_bare_op:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"field '{field_name}' has no operations",
            hint=f'add at least one operation: {field_name} {{ css ".item"; text }}',
        )
        ctx.pop()
        return

    # Include bare trailing op in the pipeline for type checking.
    # In KDL 2.0, the last op without `;` is a bare identifier in node_children
    # and node_children itself works as a virtual node for ctx.node_name/get_args.
    all_ops = list(ops)
    if has_bare_op and bare_container is not None:
        all_ops.append(bare_container)

    # For table fields the pipeline starts with 'match { ... }' which
    # accepts DOCUMENT and returns STRING (the value cell from @value).
    # So start_type is always DOCUMENT here — match handles the transition.
    # For regular fields: DOCUMENT, unless self-ref from @init.
    start = VT.DOCUMENT
    if struct_type == "table":
        # table fields MUST start with match { ... }
        if not all_ops or ctx.node_name(all_ops[0]) != "match":
            ctx.error(
                node,
                ErrorCode.MISSING_ARGUMENT,
                message=f"table field '{field_name}' must start with 'match {{ ... }}'",
                hint=f'example: {field_name} {{ match {{ eq "value" }} }}',
            )
    elif all_ops and ctx.node_name(all_ops[0]) == "self":
        init_name = ctx.get_arg(all_ops[0], 0)
        if init_name and init_name in ctx.inferred_define_types:
            _, start = ctx.inferred_define_types[init_name]
    check_pipeline_types(all_ops, ctx, start_type=start)
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
            notes=["Allow miltiple reuese scalar define:\n"
            'define BASE-URL="example.com\n'
            'define URL="{{BASE-URL}}/index.html"'
            ]
        )


# ── transform (module-level) ───────────────────────────────────────────────────


def _validate_transform_props(node: Node, name: str, ctx: LintContext) -> None:
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


def _validate_lang_block(
    lang_node: Node, name: str, lang: str, ctx: LintContext
) -> None:
    impl_nodes = ctx.get_children_nodes(lang_node)
    has_code = False

    if impl_nodes:
        for impl_node in impl_nodes:
            impl_name = ctx.node_name(impl_node)
            match impl_name:
                case "code":
                    has_code = True
                    if not ctx.get_args(impl_node):
                        ctx.error(
                            impl_node,
                            ErrorCode.MISSING_ARGUMENT,
                            message=f"'transform {name}' > '{lang}' > 'code' requires a string argument",
                            hint='example: code "{{NXT}} = {{PRV}}"',
                        )
                case "import":
                    if not ctx.get_args(impl_node):
                        ctx.error(
                            impl_node,
                            ErrorCode.MISSING_ARGUMENT,
                            message=f"'transform {name}' > '{lang}' > 'import' requires a string argument",
                            hint='example: import "from base64 import b64decode"',
                        )
                case _:
                    if impl_name:  # защита от пустого имени
                        ctx.error(
                            impl_node,
                            ErrorCode.MISSING_ARGUMENT,
                            message=f"'transform {name}' > '{lang}': unknown keyword '{impl_name}'",
                            hint="only 'import' and 'code' are allowed inside language blocks",
                        )
    else:
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
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}' > '{lang}' has no 'code' statement",
            hint='add: code "{{NXT}} = {{PRV}}"',
        )


@LINTER.rule("transform")
def rule_transform(node: Node, ctx: LintContext) -> None:
    """Validate module-level transform definition.

    Pipeline calls (transform <name> inside a field) are handled by type_rules
    and have no accept=/return= props — skip them here.
    """
    accept_str = ctx.get_prop(node, "accept")
    ret_str = ctx.get_prop(node, "return")
    lang_nodes = ctx.get_children_nodes(node)
    is_definition = bool(accept_str or ret_str or lang_nodes)
    if not is_definition:
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
    _validate_transform_props(node, name, ctx)

    lang_nodes = ctx.get_children_nodes(node)
    if not lang_nodes:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message=f"'transform {name}' has no language implementations",
            hint='add at least one language block, e.g.: py { code "{{NXT}} = {{PRV}}" }',
        )
        return

    for lang_node in lang_nodes:
        lang = ctx.node_name(lang_node)
        if lang:
            _validate_lang_block(lang_node, name, lang, ctx)
