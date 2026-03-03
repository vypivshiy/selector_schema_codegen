"""
KDL DSL linter rules.

Rules are registered via @LINTER.rule(*node_names).
Each rule receives (node: Node, ctx: LintContext) and calls
ctx.error() / ctx.warning() to report issues.
"""
from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.ast.types import VariableType as VT
from ssc_codegen.kdl.linter.base import LINTER, LintContext
from ssc_codegen.kdl.linter.type_rules import (
    PIPELINE_TYPE_RULES,
    SKIP_TYPE_CHECK,
    accepted_types,
    resolve_ret,
    type_mismatch_hint,
)


# ── selectors ──────────────────────────────────────────────────────────────────

_CSS_OPS   = ("css", "css-all", "css-remove")
_XPATH_OPS = ("xpath", "xpath-all", "xpath-remove")


@LINTER.rule(*_CSS_OPS)
def rule_css_requires_query(node: Node, ctx: LintContext) -> None:
    """css / css-all / css-remove require exactly one query argument."""
    name = ctx.node_name(node)
    query = ctx.get_arg(node, 0)

    if query is None:
        ctx.error(
            node,
            message=f"'{name}' requires a CSS query argument",
            hint=f'example: {name} ".my-class"',
        )
        return

    if query.strip() == "":
        ctx.error(
            node,
            message=f"'{name}' query argument is empty",
            hint=f'provide a valid CSS selector: {name} ".my-class"',
        )


@LINTER.rule(*_XPATH_OPS)
def rule_xpath_requires_query(node: Node, ctx: LintContext) -> None:
    """xpath / xpath-all / xpath-remove require exactly one query argument."""
    name = ctx.node_name(node)
    query = ctx.get_arg(node, 0)

    if query is None:
        ctx.error(
            node,
            message=f"'{name}' requires an XPath query argument",
            hint=f'example: {name} "//div[@class=\'item\']"',
        )
        return

    if query.strip() == "":
        ctx.error(
            node,
            message=f"'{name}' query argument is empty",
            hint=f'provide a valid XPath expression: {name} "//div"',
        )


# ── struct field type checking ─────────────────────────────────────────────────

# reserved fields that have pipelines — each starts from DOCUMENT
_RESERVED_PIPELINE_FIELDS: dict[str, VT] = {
    "-pre-validate": VT.DOCUMENT,
    "-split-doc":    VT.DOCUMENT,
    "-key":          VT.DOCUMENT,
    "-value":        VT.DOCUMENT,
    "-table":        VT.DOCUMENT,
    "-row":          VT.DOCUMENT,
    "-match":        VT.DOCUMENT,
}


@LINTER.rule("struct")
def rule_struct_field_types(node: Node, ctx: LintContext) -> None:
    """
    Check pipeline type compatibility for all fields inside a struct.

    Regular fields always start with DOCUMENT.
    Reserved fields (-split-doc, -key, etc.) also start with DOCUMENT.
    -init fields are skipped here — handled separately.
    """
    struct_name = ctx.get_arg(node, 0) or "?"

    for field_node in ctx.get_children_nodes(node):
        field_name = ctx.node_name(field_node)
        if not field_name:
            continue

        # skip -doc, -init (no pipeline to check)
        if field_name in ("-doc", "-init"):
            continue

        start_type = _RESERVED_PIPELINE_FIELDS.get(field_name, VT.DOCUMENT)
        _check_field_pipeline(field_node, field_name, start_type, ctx)


def _check_field_pipeline(
    field_node: Node,
    field_name: str,
    start_type: VT,
    ctx: LintContext,
) -> None:
    """
    Walk pipeline ops of a single field and verify type compatibility.
    Pushes field_name onto ctx path for error location.
    """
    ops = ctx.get_children_nodes(field_node)
    if not ops:
        return

    ctx.push(field_name)
    current_type = start_type

    for op_node in ops:
        op_name = ctx.node_name(op_node)
        if not op_name or op_name in SKIP_TYPE_CHECK:
            # self — type is unknown statically without -init resolution,
            # reset to AUTO to avoid false positives
            if op_name == "self":
                current_type = VT.AUTO
            continue

        pairs = PIPELINE_TYPE_RULES.get(op_name)
        if pairs is None:
            # unknown op — unknown-op rule handles this separately
            continue

        # find matching pair for current type
        match = next(
            ((a, r) for a, r in pairs if a is None or a == current_type),
            None,
        )

        if match is None:
            valid = accepted_types(op_name)
            expected = " | ".join(t.name for t in valid)
            ctx.error(
                op_node,
                message=(
                    f"type mismatch: '{op_name}' expects {expected}, "
                    f"got {current_type.name}"
                ),
                hint=type_mismatch_hint(op_name, current_type),
            )
            # don't update current_type — chain is broken,
            # but keep walking to surface more errors
            continue

        _, ret = match
        current_type = ret if ret is not None else current_type

    ctx.pop()