"""Predicate builders and dispatch tables for filter/assert/match."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from ssc_codegen.ast import (
    Assert,
    Filter,
    LogicAnd,
    LogicNot,
    LogicOr,
    Match,
    Node as AstNode,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredContains,
    PredCountEq,
    PredCountGe,
    PredCountGt,
    PredCountLe,
    PredCountLt,
    PredCountNe,
    PredCountRange,
    PredCss,
    PredEnds,
    PredEq,
    PredGe,
    PredGt,
    PredHasAttr,
    PredIn,
    PredLe,
    PredLt,
    PredNe,
    PredRange,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredXpath,
    VariableType,
)
from ssc_codegen.exceptions import BuildTimeError
from kdlquery import KdlNode
from ssc_codegen.regex_utils import normalize_regex_pattern
from typing import cast

from ssc_codegen.core.contexts import LintContext, ParseContext
from ssc_codegen.core.linter import lint_predicate_op


# ── Parse filter/assert/match expressions ──────────────────────────────────────


def parse_filter_expr(
    kdl_nodes: Sequence[KdlNode],
    parent: Filter | LogicAnd | LogicNot | LogicOr,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "filter"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            parse_filter_expr(
                ctx.children_defines[node.name], parent, ctx, lint
            )
            continue
        lint_predicate_op(node, lint)
        expr = _build_filter_predicate(node, parent, ctx, lint)  # type: ignore[arg-type]
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            parse_filter_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


def parse_assert_expr(
    kdl_nodes: Sequence[KdlNode],
    parent: Assert | LogicAnd | LogicNot | LogicOr,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "assert"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            parse_assert_expr(
                ctx.children_defines[node.name], parent, ctx, lint
            )
            continue
        lint_predicate_op(node, lint)
        expr = _build_assert_predicate(node, parent, ctx, lint)  # type: ignore[arg-type]
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            parse_assert_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


def parse_match_expr(
    kdl_nodes: Sequence[KdlNode],
    parent: Match | LogicAnd | LogicNot | LogicOr,
    ctx: ParseContext,
    lint: LintContext,
) -> None:
    lint._predicate_depth += 1
    old_ctx = lint._predicate_context
    lint._predicate_context = "match"
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            parse_match_expr(ctx.children_defines[node.name], parent, ctx, lint)
            continue
        lint_predicate_op(node, lint)
        expr = _build_match_predicate(node, parent, ctx, lint)  # type: ignore[arg-type]
        if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
            parse_match_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
    lint._predicate_context = old_ctx
    lint._predicate_depth -= 1


# ── Predicate builders ─────────────────────────────────────────────────────────


def _build_filter_predicate(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
) -> AstNode:
    return _FILTER_DISPATCH.get(node.name, _unknown_pred)(
        node, parent, ctx, lint
    )


def _build_assert_predicate(
    node: KdlNode, parent: Assert, ctx: ParseContext, lint: LintContext
) -> AstNode:
    return _ASSERT_DISPATCH.get(node.name, _unknown_pred)(
        node, parent, ctx, lint
    )


def _build_match_predicate(
    node: KdlNode, parent: Match, ctx: ParseContext, lint: LintContext
) -> AstNode:
    return _MATCH_DISPATCH.get(node.name, _unknown_pred)(
        node, parent, ctx, lint
    )


def _unknown_pred(
    node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext
) -> AstNode:
    raise BuildTimeError(f"Unknown predicate: {node.name}")


def _pred_prev(node: KdlNode, parent: Any) -> VariableType:
    return parent.ret


# ── Predicate functions ────────────────────────────────────────────────────────


def _p_eq(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredEq(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_ne(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredNe(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_gt(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredGt(
        parent=parent,
        value=node.args[0].value,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_lt(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredLt(
        parent=parent,
        value=node.args[0].value,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_ge(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredGe(
        parent=parent,
        value=node.args[0].value,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_le(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredLe(
        parent=parent,
        value=node.args[0].value,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_range(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredRange(
        parent=parent,
        start=int(node.args[0].value),
        end=int(node.args[1].value),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_starts(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredStarts(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_ends(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredEnds(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_contains(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredContains(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_in(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    return PredIn(
        parent=parent,
        values=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_re(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredRe(
        parent=parent,
        pattern=normalize_regex_pattern(raw),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_re_all(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredReAll(
        parent=parent,
        pattern=normalize_regex_pattern(raw),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_re_any(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredReAny(
        parent=parent,
        pattern=normalize_regex_pattern(raw),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_css(node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredCss(
        parent=parent,
        query=cast(str, query),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_xpath(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredXpath(
        parent=parent,
        query=cast(str, query),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_has_attr(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredHasAttr(
        parent=parent,
        attrs=tuple(a.value for a in node.args),
        accept=_pred_prev(node, parent),
        ret=parent.ret,
    )


def _p_attr_eq(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredAttrEq(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args[1:]),
        name=node.args[0].value,
    )


def _p_attr_ne(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredAttrNe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args[1:]),
        name=node.args[0].value,
    )


def _p_attr_contains(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredAttrContains(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args[1:]),
        name=node.args[0].value,
    )


def _p_attr_re(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    raw = ctx.property_defines.get(node.args[1].value, node.args[1].value)
    return PredAttrRe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        pattern=normalize_regex_pattern(raw),
        name=node.args[0].value,
    )


def _p_attr_starts(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredAttrStarts(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args[1:]),
        name=node.args[0].value,
    )


def _p_attr_ends(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredAttrEnds(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args[1:]),
        name=node.args[0].value,
    )


def _p_text_contains(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredTextContains(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args),
    )


def _p_text_ends(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredTextEnds(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args),
    )


def _p_text_starts(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    return PredTextStarts(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        values=tuple(a.value for a in node.args),
    )


def _p_text_re(
    node: KdlNode, parent: Filter, ctx: ParseContext, lint: LintContext
):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    return PredTextRe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        pattern=normalize_regex_pattern(raw),
    )


# len-* predicates (assert scope)
def _p_len_eq(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountEq(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_gt(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountGt(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_lt(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountLt(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_ne(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountNe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_ge(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountGe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_le(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return PredCountLe(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        value=int(node.args[0].value),
    )


def _p_len_range(
    node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext
):
    return PredCountRange(
        parent=parent,
        accept=_pred_prev(node, parent),
        ret=parent.ret,
        start=int(node.args[0].value),
        end=int(node.args[1].value),
    )


def _p_and(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return LogicAnd(
        parent=parent, accept=_pred_prev(node, parent), ret=parent.ret
    )


def _p_not(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return LogicNot(
        parent=parent, accept=_pred_prev(node, parent), ret=parent.ret
    )


def _p_or(node: KdlNode, parent: Any, ctx: ParseContext, lint: LintContext):
    return LogicOr(
        parent=parent, accept=_pred_prev(node, parent), ret=parent.ret
    )


# ── Dispatch tables ────────────────────────────────────────────────────────────


_COMMON_PREDS = {
    "eq": _p_eq,
    "ne": _p_ne,
    "gt": _p_gt,
    "lt": _p_lt,
    "ge": _p_ge,
    "le": _p_le,
    "range": _p_range,
    "starts": _p_starts,
    "ends": _p_ends,
    "contains": _p_contains,
    "in": _p_in,
    "and": _p_and,
    "or": _p_or,
    "not": _p_not,
}

_FILTER_DISPATCH: dict[str, Callable] = {
    **_COMMON_PREDS,
    "re": _p_re,
    "css": _p_css,
    "xpath": _p_xpath,
    "has-attr": _p_has_attr,
    "attr-eq": _p_attr_eq,
    "attr-ne": _p_attr_ne,
    "attr-contains": _p_attr_contains,
    "attr-re": _p_attr_re,
    "attr-starts": _p_attr_starts,
    "attr-ends": _p_attr_ends,
    "text-contains": _p_text_contains,
    "text-ends": _p_text_ends,
    "text-starts": _p_text_starts,
    "text-re": _p_text_re,
}

_ASSERT_DISPATCH: dict[str, Callable] = {
    **_FILTER_DISPATCH,
    "re-all": _p_re_all,
    "re-any": _p_re_any,
    "len-eq": _p_len_eq,
    "len-gt": _p_len_gt,
    "len-lt": _p_len_lt,
    "len-ne": _p_len_ne,
    "len-ge": _p_len_ge,
    "len-le": _p_len_le,
    "len-range": _p_len_range,
}

_MATCH_DISPATCH: dict[str, Callable] = {
    "eq": _p_eq,
    "ne": _p_ne,
    "starts": _p_starts,
    "ends": _p_ends,
    "contains": _p_contains,
    "in": _p_in,
    "re": _p_re,
    "and": _p_and,
    "or": _p_or,
    "not": _p_not,
}
