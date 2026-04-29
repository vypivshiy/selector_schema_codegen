"""Pipeline type checking — op types, compatibility, mismatch hints."""

from __future__ import annotations

from ssc_codegen.ast import VariableType
from ssc_codegen.kdl import KdlNode

from ssc_codegen.core.contexts import DefineKind, LintContext, ParseContext
from ssc_codegen.core.expressions import _VAR_TYPE_MAP


# ── Op type table ──────────────────────────────────────────────────────────────


_OP_TYPES: dict[str, list[tuple[VariableType | None, VariableType | None]]] = {
    "css": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "css-all": [(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)],
    "xpath": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "xpath-all": [(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)],
    "css-remove": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "xpath-remove": [(VariableType.DOCUMENT, VariableType.DOCUMENT)],
    "text": [
        (VariableType.DOCUMENT, VariableType.STRING),
        (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING),
    ],
    "raw": [
        (VariableType.DOCUMENT, VariableType.STRING),
        (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING),
    ],
    "attr": [
        (VariableType.DOCUMENT, VariableType.STRING),
        (VariableType.LIST_DOCUMENT, VariableType.LIST_STRING),
    ],
    "trim": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "ltrim": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "rtrim": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "normalize-space": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "fmt": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "repl": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "lower": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "upper": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "rm-prefix": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "rm-suffix": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "rm-prefix-suffix": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "unescape": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "split": [(VariableType.STRING, VariableType.LIST_STRING)],
    "join": [(VariableType.LIST_STRING, VariableType.STRING)],
    "re": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "re-all": [(VariableType.STRING, VariableType.LIST_STRING)],
    "re-sub": [
        (VariableType.STRING, VariableType.STRING),
        (VariableType.LIST_STRING, VariableType.LIST_STRING),
    ],
    "index": [(None, None)],
    "first": [(None, None)],
    "last": [(None, None)],
    "slice": [(None, None)],
    "len": [(None, VariableType.INT)],
    "unique": [(VariableType.LIST_STRING, VariableType.LIST_STRING)],
    "to-int": [
        (VariableType.STRING, VariableType.INT),
        (VariableType.LIST_STRING, VariableType.LIST_INT),
    ],
    "to-float": [
        (VariableType.STRING, VariableType.FLOAT),
        (VariableType.LIST_STRING, VariableType.LIST_FLOAT),
    ],
    "to-bool": [(None, VariableType.BOOL)],
    "jsonify": [(VariableType.STRING, VariableType.JSON)],
    "nested": [(VariableType.DOCUMENT, VariableType.NESTED)],
    "match": [(VariableType.DOCUMENT, VariableType.STRING)],
}

_LIST_TO_SCALAR: frozenset[str] = frozenset({"index", "first", "last"})
_LIST_PRESERVE: frozenset[str] = frozenset({"slice"})


def _is_list_type(t: VariableType) -> bool:
    return t in (
        VariableType.LIST_AUTO,
        VariableType.LIST_DOCUMENT,
        VariableType.LIST_STRING,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
    )


def _vt_compatible(got: VariableType, expected: VariableType) -> bool:
    if got == expected:
        return True
    if got == VariableType.AUTO or expected == VariableType.AUTO:
        return not _is_list_type(got) and not _is_list_type(expected)
    if got == VariableType.LIST_AUTO or expected == VariableType.LIST_AUTO:
        return _is_list_type(got) or _is_list_type(expected)
    return False


def _resolve_op_ret(op: str, accept: VariableType) -> VariableType:
    pairs = _OP_TYPES.get(op)
    if not pairs:
        return VariableType.AUTO
    for pair_accept, pair_ret in pairs:
        if pair_accept is None or _vt_compatible(accept, pair_accept):
            if pair_ret is not None:
                return pair_ret
            if op in _LIST_TO_SCALAR:
                return accept.scalar
            if op in _LIST_PRESERVE:
                return accept
            return accept
    return VariableType.AUTO


def _type_mismatch_hint(op_name: str, got: VariableType) -> str:
    _needs_text = {
        "fmt",
        "trim",
        "ltrim",
        "rtrim",
        "lower",
        "upper",
        "re",
        "re-sub",
        "re-all",
        "to-int",
        "to-float",
        "split",
        "join",
        "normalize-space",
        "unescape",
        "rm-prefix",
        "rm-suffix",
        "rm-prefix-suffix",
    }
    if (
        got in (VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
        and op_name in _needs_text
    ):
        return "add 'text', 'raw', or 'attr' before this operation to extract a string"
    if _is_list_type(got) and op_name in (
        "css",
        "xpath",
        "css-all",
        "xpath-all",
    ):
        return "selectors work on a single DOCUMENT, not a list"
    if op_name in ("index", "first", "last", "slice") and not _is_list_type(
        got
    ):
        return f"'{op_name}' requires a LIST type, got {got.name}"
    if op_name in ("unique", "join") and got != VariableType.LIST_STRING:
        return f"'{op_name}' requires LIST_STRING, got {got.name}"
    if not _is_list_type(got) and op_name == "len":
        return "'len' counts elements of any list — produce a list first"
    if op_name == "split" and got != VariableType.STRING:
        return f"'split' requires STRING, got {got.name}"
    pairs = _OP_TYPES.get(op_name, [])
    valid = [a for a, _ in pairs if a is not None]
    if valid:
        return f"'{op_name}' accepts: {' | '.join(t.name for t in valid)}"
    return f"unexpected type {got.name} for '{op_name}'"


def _get_define_ops(
    define_name: str,
    ctx: ParseContext,
    lint: LintContext,
    _visiting: set[str] | None = None,
) -> list[KdlNode] | None:
    info = lint.defines.get(define_name)
    if info is None or info.kind != DefineKind.BLOCK:
        return None
    if _visiting is None:
        _visiting = set()
    if define_name in _visiting:
        return None
    _visiting.add(define_name)
    result: list[KdlNode] = []
    for op_node in lint.get_children_nodes(info.node):
        op_nm = lint.node_name(op_node)
        if not op_nm:
            continue
        if op_nm in ctx.children_defines:
            nested = _get_define_ops(op_nm, ctx, lint, _visiting)
            if nested is None:
                _visiting.discard(define_name)
                return None
            result.extend(nested)
        else:
            result.append(op_node)
    _visiting.discard(define_name)
    return result


def _fallback_literal_type(
    node: KdlNode, lint: LintContext
) -> VariableType | None:
    if lint.get_children_nodes(node):
        return VariableType.LIST_AUTO
    raw_args = lint.get_raw_args(node)
    if not raw_args:
        return None
    raw = raw_args[0]
    val = raw.value
    if val in ("#true", "#false"):
        return VariableType.BOOL
    if val == "#null":
        return VariableType.NULL
    if not raw.is_identifier:
        if "." in val or "e" in val.lower():
            try:
                float(val)
                return VariableType.FLOAT
            except ValueError:
                return VariableType.STRING
        try:
            int(val)
            return VariableType.INT
        except ValueError:
            pass
        return VariableType.STRING
    return VariableType.STRING


def check_pipeline_types(
    ops: list[KdlNode],
    ctx: ParseContext,
    lint: LintContext,
    start_type: VariableType = VariableType.DOCUMENT,
) -> VariableType:
    current = start_type
    for node in ops:
        op_name = lint.node_name(node)
        if not op_name:
            continue

        if op_name == "self":
            continue

        if op_name == "fallback":
            fb_type = _fallback_literal_type(node, lint)
            if fb_type is None:
                continue
            if fb_type == VariableType.LIST_AUTO:
                if (
                    not _is_list_type(current)
                    and current != VariableType.LIST_AUTO
                ):
                    lint.error(
                        node,
                        message=f"'fallback {{}}' is only valid for list types, got {current.name}",
                        code="E100",
                        hint="use 'css-all' or 'xpath-all' to produce a list",
                    )
                continue
            if fb_type == VariableType.NULL:
                if current not in (
                    VariableType.STRING,
                    VariableType.INT,
                    VariableType.FLOAT,
                    VariableType.AUTO,
                    VariableType.OPT_STRING,
                    VariableType.OPT_INT,
                    VariableType.OPT_FLOAT,
                ):
                    lint.error(
                        node,
                        message=f"'fallback #null' only valid for STRING/INT/FLOAT, got {current.name}",
                        code="E100",
                    )
                else:
                    current = current.optional
                continue
            if not _vt_compatible(current, fb_type) and current not in (
                VariableType.AUTO,
                VariableType.LIST_AUTO,
            ):
                lint.error(
                    node,
                    message=f"'fallback' type {fb_type.name} does not match pipeline {current.name}",
                    code="E100",
                    hint=f"use a {current.name.lower()} literal or #null",
                )
                continue
            current = fb_type
            continue

        if op_name == "transform":
            args = lint.get_args(node)
            t_name = args[0] if args else None
            if not t_name:
                lint.error(
                    node,
                    message="'transform' call requires a name",
                    code="E100",
                )
                current = VariableType.AUTO
                continue
            t_info = lint.transforms.get(t_name)
            if t_info is None:
                current = VariableType.AUTO
                continue
            t_accept = _VAR_TYPE_MAP.get(t_info.accept)
            t_ret = _VAR_TYPE_MAP.get(t_info.ret)
            if t_accept is not None and not _vt_compatible(current, t_accept):
                lint.error(
                    node,
                    message=f"'transform {t_name}' expects {t_accept.name}, got {current.name}",
                    code="E100",
                )
            current = t_ret if t_ret is not None else VariableType.AUTO
            continue

        if op_name == "filter":
            if not _is_list_type(current) and current not in (
                VariableType.AUTO,
                VariableType.LIST_AUTO,
            ):
                lint.error(
                    node,
                    message=f"'filter' requires a list type, got {current.name}",
                    code="E100",
                    hint="use 'css-all', 'xpath-all', 're-all', or 'split' first",
                )
            continue

        if op_name == "assert":
            continue

        if op_name == "match":
            if current != start_type:
                lint.error(
                    node,
                    message="'match' must be the first operation in the field pipeline",
                    code="E100",
                )
            elif not _vt_compatible(current, VariableType.DOCUMENT):
                lint.error(
                    node,
                    message=f"'match' requires DOCUMENT, got {current.name}",
                    code="E100",
                )
            current = _resolve_op_ret("match", current)
            continue

        # block define — inline expansion
        if op_name in ctx.children_defines or op_name in lint.defines:
            define_ops = _get_define_ops(op_name, ctx, lint)
            if define_ops:
                current = check_pipeline_types(
                    define_ops, ctx, lint, start_type=current
                )
            continue

        # regular op
        pairs = _OP_TYPES.get(op_name)
        if pairs is None:
            current = VariableType.AUTO
            continue
        accepted = [a for a, _ in pairs if a is not None]
        if accepted and not any(_vt_compatible(current, a) for a in accepted):
            lint.error(
                node,
                message=f"'{op_name}' does not accept {current.name}; expected {' | '.join(t.name for t in accepted)}",
                code="E100",
                hint=_type_mismatch_hint(op_name, current),
            )
            current = VariableType.AUTO
            continue
        current = _resolve_op_ret(op_name, current)
    return current
