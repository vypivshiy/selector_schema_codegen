"""
KDL DSL linter rules.

Rules are registered via @LINTER.rule(*node_names).
Each rule receives (node: Node, ctx: LintContext) and calls
ctx.error() / ctx.warning() to report issues.
"""

from __future__ import annotations

import re

from tree_sitter import Node

from ssc_codegen.kdl.linter.base import LINTER, LintContext


# ── helpers ────────────────────────────────────────────────────────────────────

# all blocks that form a valid predicate context
_PREDICATE_BLOCKS = frozenset({"filter", "assert", "match", "not", "and", "or"})
# assert-only blocks
_ASSERT_ONLY_BLOCKS = frozenset({"assert"})


def _in_predicate(node: Node, ctx: LintContext) -> bool:
    """Return True if node is inside a predicate block (walks up past node_children)."""
    parent = node.parent
    # tree-sitter wraps children in a 'node_children' CST node — skip it
    if parent is not None and parent.type == "node_children":
        parent = parent.parent
    return bool(parent and ctx.node_name(parent) in _PREDICATE_BLOCKS)


def _in_assert(node: Node, ctx: LintContext) -> bool:
    """Return True if node is inside an assert block (walks up past node_children)."""
    parent = node.parent
    # tree-sitter wraps children in a 'node_children' CST node — skip it
    if parent is not None and parent.type == "node_children":
        parent = parent.parent
    return bool(parent and ctx.node_name(parent) in _ASSERT_ONLY_BLOCKS)


def _require_predicate_ctx(node: Node, ctx: LintContext) -> bool:
    """
    Ensure node is inside a predicate block.
    Reports error and returns False if not.
    """
    if _in_predicate(node, ctx):
        return True
    name = ctx.node_name(node)
    blocks = ", ".join(sorted(_PREDICATE_BLOCKS))
    ctx.error(
        node,
        message=f"'{name}' is only valid inside a predicate block",
        hint=f"wrap it in one of: {blocks}. Example: filter {{ {name} ... }}",
    )
    return False


def _require_assert_ctx(node: Node, ctx: LintContext) -> bool:
    """
    Ensure node is inside an assert block.
    Reports error and returns False if not.
    """
    if _in_assert(node, ctx):
        return True
    name = ctx.node_name(node)
    ctx.error(
        node,
        message=f"'{name}' is only valid inside an assert block",
        hint=f"example: assert {{ {name} ... }}",
    )
    return False


def _validate_regex(node: Node, ctx: LintContext, pattern: str) -> bool:
    """
    Validate regex pattern. Reports error and returns False if invalid.
    """
    try:
        re.compile(pattern)
        return True
    except re.error as e:
        ctx.error(
            node,
            message=f"invalid regex pattern: {e.msg}",
            hint='check regex syntax — raw strings #"..."# recommended',
        )
        return False


def _require_args_count(
    node: Node,
    ctx: LintContext,
    *,
    exact: int | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    example: str = "",
) -> list[str] | None:
    """
    Validate argument count. Returns args if valid, None if error reported.
    """
    args = ctx.get_args(node)
    name = ctx.node_name(node)
    count = len(args)

    if exact is not None and count != exact:
        noun = "argument" if exact == 1 else "arguments"
        ctx.error(
            node,
            message=f"'{name}' requires exactly {exact} {noun}, got {count}",
            hint=f"example: {example}" if example else "",
        )
        return None

    if min_count is not None and count < min_count:
        noun = "argument" if min_count == 1 else "arguments"
        ctx.error(
            node,
            message=f"'{name}' requires at least {min_count} {noun}, got {count}",
            hint=f"example: {example}" if example else "",
        )
        return None

    if max_count is not None and count > max_count:
        ctx.error(
            node,
            message=f"'{name}' allows at most {max_count} argument(s), got {count}",
            hint=f"example: {example}" if example else "",
        )
        return None

    return args


def _require_int_args(node: Node, ctx: LintContext, args: list[str]) -> bool:
    """Validate all args are integers. Returns False and reports error if not."""
    name = ctx.node_name(node)
    for arg in args:
        try:
            int(arg)
        except ValueError:
            ctx.error(
                node,
                message=f"'{name}' arguments must be integers, got '{arg}'",
                hint=f"example: {name} 0",
            )
            return False
    return True


# ── selectors ──────────────────────────────────────────────────────────────────


@LINTER.rule("css", "css-all", "css-remove")
def rule_css(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    args = _require_args_count(
        node, ctx, exact=1, example=f'{name} ".my-class"'
    )
    if args and args[0].strip() == "":
        ctx.error(
            node,
            message=f"'{name}' CSS selector must not be empty",
            hint=f'example: {name} ".my-class"',
        )


@LINTER.rule("xpath", "xpath-all", "xpath-remove")
def rule_xpath(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    args = _require_args_count(
        node, ctx, exact=1, example=f"{name} \"//div[@class='item']\""
    )
    if args and args[0].strip() == "":
        ctx.error(
            node,
            message=f"'{name}' XPath expression must not be empty",
            hint=f'example: {name} "//div"',
        )


# ── extract ────────────────────────────────────────────────────────────────────


@LINTER.rule("text", "raw")
def rule_no_args(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    args = ctx.get_args(node)
    if args:
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"remove arguments: use just '{name}'",
        )


@LINTER.rule("attr")
def rule_attr(node: Node, ctx: LintContext) -> None:
    _require_args_count(
        node, ctx, min_count=1, example='attr "href"  or  attr "href" "src"'
    )


# ── string ─────────────────────────────────────────────────────────────────────


@LINTER.rule("normalize-space", "lower", "upper", "unescape")
def rule_string_no_args(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    if ctx.get_args(node):
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"remove arguments: use just '{name}'",
        )


@LINTER.rule("trim", "ltrim", "rtrim")
def rule_trim(node: Node, ctx: LintContext) -> None:
    """trim/ltrim/rtrim can optionally accept 1 argument (characters to remove)."""
    args = ctx.get_args(node)
    if len(args) > 1:
        name = ctx.node_name(node)
        ctx.error(
            node,
            message=f"'{name}' accepts at most 1 argument",
            hint=f'example: {name}  or  {name} "chars"',
        )


@LINTER.rule("rm-prefix", "rm-suffix", "rm-prefix-suffix")
def rule_rm_prefix_suffix(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    _require_args_count(node, ctx, exact=1, example=f'{name} "substring"')


@LINTER.rule("fmt")
def rule_fmt(node: Node, ctx: LintContext) -> None:
    args = _require_args_count(
        node, ctx, exact=1, example='fmt "prefix-{{}}-suffix"'
    )
    # Allow constant/define references (uppercase identifiers) or string literals with {{}}
    if args and not (args[0].isupper() or "{{}}" in args[0]):
        ctx.error(
            node,
            message="'fmt' template is missing the '{{}}' placeholder",
            hint=f'add placeholder to template, example: fmt "{args[0]}{{}}"',
        )


@LINTER.rule("repl")
def rule_repl(node: Node, ctx: LintContext) -> None:
    args = ctx.get_args(node)
    children = ctx.get_children_nodes(node)
    if not args and not children:
        ctx.error(
            node,
            message="'repl' requires 2 arguments or a children block",
            hint='example: repl "old" "new"  or  repl { "old" "new"; "foo" "bar" }',
        )
        return
    if args:
        _require_args_count(node, ctx, exact=2, example='repl "old" "new"')


@LINTER.rule("split", "join")
def rule_split_join(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    _require_args_count(node, ctx, exact=1, example=f'{name} " "')


# ── regex ──────────────────────────────────────────────────────────────────────


@LINTER.rule("re")
def rule_re(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    raw_args = ctx.get_raw_args(node)
    args = _require_args_count(node, ctx, exact=1, example=f'{name} #"(\\d+)"#')
    if not args:
        return
    # resolve define ref: if arg is an identifier, look up its scalar value
    pattern = args[0]
    if raw_args and raw_args[0].is_identifier:
        resolved = ctx.resolve_scalar_arg(pattern)
        if resolved is None:
            # block define — can't validate pattern statically, skip
            return
        if resolved == pattern and pattern not in ctx.defines:
            # unknown identifier, not a define — let wildcard rule handle it
            pass
        else:
            pattern = resolved
    if not _validate_regex(node, ctx, pattern):
        return
    # capture group check только для pipeline op (не в предикатном контексте)
    if not _in_predicate(node, ctx):
        groups = re.compile(pattern).groups
        if groups == 0:
            ctx.error(
                node,
                message=f"'{name}' pattern must have exactly one capture group",
                hint=f'wrap the match in a group: {name} #"({pattern})"#',
            )
        elif groups > 1:
            ctx.error(
                node,
                message=f"'{name}' pattern must have exactly one capture group, got {groups}",
                hint="use a non-capturing group (?:...) for grouping without capturing",
            )


@LINTER.rule("re-all")
def rule_re_all(node: Node, ctx: LintContext) -> None:
    # если внутри предикатного блока — это assert op, требуем assert
    if _in_predicate(node, ctx):
        if not _require_assert_ctx(node, ctx):
            return
    # в обоих случаях нужен паттерн
    args = _require_args_count(node, ctx, exact=1, example='re-all #"(\\d+)"#')
    if args:
        _validate_regex(node, ctx, args[0])


@LINTER.rule("re-sub")
def rule_re_sub(node: Node, ctx: LintContext) -> None:
    args = _require_args_count(node, ctx, exact=2, example='re-sub #"\\D"# ""')
    if args:
        _validate_regex(node, ctx, args[0])


# ── array ──────────────────────────────────────────────────────────────────────

_INDEX_HINT = (
    "example: index 0  or  index -1\n"
    "TIP: for LIST_DOCUMENT prefer CSS pseudo-selectors like :nth-child, :nth-of-type"
)
_SLICE_HINT = (
    "example: slice 0 10  or  slice -5 -1\n"
    "TIP: for LIST_DOCUMENT prefer CSS pseudo-selectors like :nth-child, :nth-of-type"
)


@LINTER.rule("first", "last", "len", "unique")
def rule_array_no_args(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    if ctx.get_args(node):
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"remove arguments: use just '{name}'",
        )


@LINTER.rule("index")
def rule_index(node: Node, ctx: LintContext) -> None:
    args = _require_args_count(node, ctx, exact=1, example=_INDEX_HINT)
    if args:
        _require_int_args(node, ctx, args)


@LINTER.rule("slice")
def rule_slice(node: Node, ctx: LintContext) -> None:
    args = _require_args_count(node, ctx, exact=2, example=_SLICE_HINT)
    if args:
        _require_int_args(node, ctx, args)


# ── cast ───────────────────────────────────────────────────────────────────────


@LINTER.rule("to-int", "to-float", "to-bool")
def rule_cast_no_args(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    if ctx.get_args(node):
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"remove arguments: use just '{name}'",
        )


@LINTER.rule("jsonify")
def rule_jsonify(node: Node, ctx: LintContext) -> None:
    _require_args_count(node, ctx, exact=1, example="jsonify MySchema")


@LINTER.rule("nested")
def rule_nested(node: Node, ctx: LintContext) -> None:
    _require_args_count(node, ctx, exact=1, example="nested MyStruct")


# ── control ────────────────────────────────────────────────────────────────────


@LINTER.rule("self")
def rule_self(node: Node, ctx: LintContext) -> None:
    args = _require_args_count(node, ctx, exact=1, example="self field-name")
    if args:
        field_name = args[0]
        if field_name not in ctx.init_fields:
            ctx.error(
                node,
                message=f"'self {field_name}': field '{field_name}' not found in @init block (deprecated syntax)",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }} or use new syntax: @{field_name}"
            )


# Note: @<name> references to @init fields are checked via wildcard rule below


@LINTER.rule("fallback")
def rule_fallback(node: Node, ctx: LintContext) -> None:
    # Allow empty blocks {} for empty list/dict fallbacks
    children = ctx.get_children_nodes(node)
    args = ctx.get_args(node)
    has_empty_block = ctx.has_empty_block(node)
    
    if not args and not children and not has_empty_block:
        ctx.error(
            node,
            message="'fallback' requires exactly 1 argument or a block",
            hint='example: fallback ""  or  fallback 0  or  fallback #null  or  fallback {}',
        )


# ── predicate containers ───────────────────────────────────────────────────────


@LINTER.rule("filter", "assert", "match")
def rule_predicate_container(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    if ctx.get_args(node):
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"move expressions into the children block: {name} {{ ... }}",
        )
    
    children = ctx.get_children_nodes(node)
    # Check for single-line syntax (operations as bare identifiers in node_children)
    has_single_line = False
    if not children:
        for child in node.children:
            if child.type == "node_children":
                identifiers = [c for c in child.children if c.type == "identifier"]
                if identifiers:
                    has_single_line = True
                break
    
    if not children and not has_single_line:
        ctx.error(
            node,
            message=f"'{name}' block must contain at least one predicate expression",
            hint=f'example: {name} {{ css ".item"; has-attr href }}',
        )


@LINTER.rule("not", "and", "or")
def rule_logic_container(node: Node, ctx: LintContext) -> None:
    name = ctx.node_name(node)
    if ctx.get_args(node):
        ctx.error(
            node,
            message=f"'{name}' does not accept arguments",
            hint=f"move expressions into the children block: {name} {{ ... }}",
        )
    
    children = ctx.get_children_nodes(node)
    # Check for single-line syntax (operations as bare identifiers in node_children)
    has_single_line = False
    if not children:
        for child in node.children:
            if child.type == "node_children":
                identifiers = [c for c in child.children if c.type == "identifier"]
                if identifiers:
                    has_single_line = True
                break
    
    if not children and not has_single_line:
        ctx.error(
            node,
            message=f"'{name}' block must contain at least one predicate expression",
            hint=f'example: {name} {{ starts "foo" }}',
        )


# ── predicate ops — string ─────────────────────────────────────────────────────


@LINTER.rule("eq", "ne")
def rule_eq_ne(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    _require_args_count(
        node, ctx, min_count=1, example=f'{name} "value"  or  {name} "a" "b"'
    )


@LINTER.rule("starts", "ends", "contains", "in")
def rule_string_predicates(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    _require_args_count(
        node, ctx, min_count=1, example=f'{name} "value"  or  {name} "a" "b"'
    )


# ── predicate ops — len ────────────────────────────────────────────────────────


@LINTER.rule("len-eq", "len-ne")
def rule_len_eq_ne(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    args = _require_args_count(node, ctx, min_count=1, example=f"{name} 5")
    if not args:
        return
    for arg in args:
        try:
            val = int(arg)
            if val < 0:
                ctx.error(
                    node,
                    message=f"'{name}' argument must be a non-negative integer, got {val}",
                    hint=f"example: {name} 5",
                )
                return
        except ValueError:
            ctx.error(
                node,
                message=f"'{name}' argument must be a non-negative integer, got '{arg}'",
                hint=f"example: {name} 5",
            )
            return


@LINTER.rule("len-gt", "len-lt", "len-ge", "len-le")
def rule_len_compare(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    args = _require_args_count(node, ctx, exact=1, example=f"{name} 10")
    if args:
        _require_int_args(node, ctx, args)


@LINTER.rule("len-range")
def rule_len_range(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    args = _require_args_count(node, ctx, exact=2, example="len-range 1 100")
    if args:
        _require_int_args(node, ctx, args)


# ── predicate ops — document ───────────────────────────────────────────────────


@LINTER.rule("has-attr")
def rule_has_attr(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    _require_args_count(
        node,
        ctx,
        min_count=1,
        example='has-attr "href"  or  has-attr "href" "src"',
    )


@LINTER.rule("attr-eq", "attr-ne", "attr-starts", "attr-ends")
def rule_attr_value_predicates(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    _require_args_count(
        node, ctx, min_count=2, example=f'{name} "href" "value1" "value2"'
    )


@LINTER.rule("attr-re")
def rule_attr_re(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    args = _require_args_count(
        node, ctx, exact=2, example='attr-re "href" #".*\\.(?:com|org)$"#'
    )
    if args:
        _validate_regex(node, ctx, args[1])


@LINTER.rule("text-re")
def rule_text_re(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    args = _require_args_count(node, ctx, exact=1, example='text-re #"\\d+"#')
    if args:
        _validate_regex(node, ctx, args[0])


@LINTER.rule("text-starts", "text-ends", "text-contains")
def rule_text_predicates(node: Node, ctx: LintContext) -> None:
    if not _require_predicate_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    _require_args_count(
        node, ctx, min_count=1, example=f'{name} "value1" "value2"'
    )


# ── assert-only predicate ops ──────────────────────────────────────────────────


@LINTER.rule("re-any")
def rule_re_any(node: Node, ctx: LintContext) -> None:
    if not _require_assert_ctx(node, ctx):
        return
    args = _require_args_count(node, ctx, exact=1, example='re-any #"\\d+"#')
    if args:
        _validate_regex(node, ctx, args[0])


# ── assert-only: numeric comparison ───────────────────────────────────────────


@LINTER.rule("gt", "lt", "ge", "le")
def rule_numeric_compare(node: Node, ctx: LintContext) -> None:
    if not _require_assert_ctx(node, ctx):
        return
    name = ctx.node_name(node)
    _require_args_count(node, ctx, exact=1, example=f"{name} 42")
