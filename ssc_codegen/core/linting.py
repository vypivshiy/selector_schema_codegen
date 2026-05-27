"""Lint helpers — argument validation, CSS/XPath/regex validation, pipeline/predicate linting."""

from __future__ import annotations

import difflib as _difflib
import re as _re

from kdlquery import KdlNode
from ssc_codegen.core.contexts import (
    DefineKind,
    LintContext,
    ParseContext,
)
from ssc_codegen.core.linter import _DEFINE_NAME_RE


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
            if raw_args and _DEFINE_NAME_RE.match(raw_args[0].value):
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
