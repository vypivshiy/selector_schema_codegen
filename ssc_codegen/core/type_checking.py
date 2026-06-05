"""Pipeline type checking — op signatures, compatibility, mismatch hints."""

from __future__ import annotations

from typing import NamedTuple

from ssc_codegen.ast import VariableType
from kdlquery import KdlNode

from ssc_codegen.core.contexts import DefineKind, LintContext, ParseContext
from ssc_codegen.core.expressions import _VAR_TYPE_MAP


# ── Op signature ─────────────────────────────────────────────────────────────


class OpSig(NamedTuple):
    accept: VariableType | None  # base type (None = any)
    ret: VariableType | None  # base type return (None = unchanged)
    list_propagates: bool = True  # input is_array → output is_array
    force_list: bool = False  # output always list
    force_scalar: bool = False  # output always scalar


_OP_TYPES: dict[str, OpSig] = {
    "css": OpSig(VariableType.DOCUMENT, VariableType.DOCUMENT),
    "css-all": OpSig(
        VariableType.DOCUMENT, VariableType.DOCUMENT, force_list=True
    ),
    "xpath": OpSig(VariableType.DOCUMENT, VariableType.DOCUMENT),
    "xpath-all": OpSig(
        VariableType.DOCUMENT, VariableType.DOCUMENT, force_list=True
    ),
    "css-remove": OpSig(VariableType.DOCUMENT, VariableType.DOCUMENT),
    "xpath-remove": OpSig(VariableType.DOCUMENT, VariableType.DOCUMENT),
    "text": OpSig(
        VariableType.DOCUMENT, VariableType.STRING, list_propagates=True
    ),
    "raw": OpSig(
        VariableType.DOCUMENT, VariableType.STRING, list_propagates=True
    ),
    "attr": OpSig(
        VariableType.DOCUMENT, VariableType.STRING, list_propagates=True
    ),
    "trim": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "ltrim": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "rtrim": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "normalize-space": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "fmt": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "repl": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "lower": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "upper": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "rm-prefix": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "rm-suffix": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "rm-prefix-suffix": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "unescape": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "split": OpSig(VariableType.STRING, VariableType.STRING, force_list=True),
    "join": OpSig(VariableType.STRING, VariableType.STRING, force_scalar=True),
    "re": OpSig(VariableType.STRING, VariableType.STRING, list_propagates=True),
    "re-all": OpSig(VariableType.STRING, VariableType.STRING, force_list=True),
    "re-sub": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "index": OpSig(None, None, force_scalar=True),
    "first": OpSig(None, None, force_scalar=True),
    "last": OpSig(None, None, force_scalar=True),
    "slice": OpSig(None, None, list_propagates=True),
    "len": OpSig(None, VariableType.INT, force_scalar=True),
    "unique": OpSig(
        VariableType.STRING, VariableType.STRING, list_propagates=True
    ),
    "to-int": OpSig(
        VariableType.STRING, VariableType.INT, list_propagates=True
    ),
    "to-float": OpSig(
        VariableType.STRING, VariableType.FLOAT, list_propagates=True
    ),
    "to-bool": OpSig(None, VariableType.BOOL, force_scalar=True),
    "jsonify": OpSig(VariableType.STRING, VariableType.JSON, force_scalar=True),
    "nested": OpSig(
        VariableType.DOCUMENT, VariableType.NESTED, force_scalar=True
    ),
    "match": OpSig(
        VariableType.DOCUMENT, VariableType.STRING, force_scalar=True
    ),
}


def _vt_compatible(
    got_base: VariableType, got_is_array: bool, expected: VariableType | None
) -> bool:
    """Check if got type is compatible with expected base type."""
    if expected is None:
        return True
    if got_base == expected:
        return True
    if got_base == VariableType.AUTO or expected == VariableType.AUTO:
        return True
    return False


def _resolve_op_ret(
    op_name: str, current_base: VariableType, current_is_array: bool
) -> tuple[VariableType, bool]:
    """Return (new_base, new_is_array) after applying op."""
    sig = _OP_TYPES.get(op_name)
    if sig is None:
        return current_base, current_is_array

    # Resolve new base
    new_base = sig.ret if sig.ret is not None else current_base

    # Resolve new is_array
    if sig.force_list:
        new_is_array = True
    elif sig.force_scalar:
        new_is_array = False
    elif sig.list_propagates:
        new_is_array = current_is_array
    else:
        new_is_array = current_is_array

    return new_base, new_is_array


def _type_mismatch_hint(
    op_name: str, got_base: VariableType, got_is_array: bool
) -> str:
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
    if got_base == VariableType.DOCUMENT and op_name in _needs_text:
        return "add 'text', 'raw', or 'attr' before this operation to extract a string"
    if got_is_array and op_name in (
        "css",
        "xpath",
        "css-all",
        "xpath-all",
    ):
        return "selectors work on a single DOCUMENT, not a list"
    if op_name in ("index", "first", "last", "slice") and not got_is_array:
        return f"'{op_name}' requires a LIST type, got {got_base.name}"
    if op_name in ("unique", "join") and (
        got_base != VariableType.STRING or not got_is_array
    ):
        return f"'{op_name}' requires LIST_STRING, got {got_base.name}"
    if not got_is_array and op_name == "len":
        return "'len' counts elements of any list — produce a list first"
    if op_name == "split" and got_base != VariableType.STRING:
        return f"'split' requires STRING, got {got_base.name}"
    sig = _OP_TYPES.get(op_name)
    if sig and sig.accept is not None:
        return f"'{op_name}' accepts: {sig.accept.name}"
    return f"unexpected type {got_base.name} for '{op_name}'"


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
    for op_node in info.node.children:
        op_nm = op_node.name
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
) -> tuple[VariableType | None, bool]:
    """Return (base_type, is_array) for a fallback literal, or (None, False)."""
    if list(node.children):
        return VariableType.AUTO, True
    raw_args = node.args
    if not raw_args:
        return None, False
    raw = raw_args[0]
    val = raw.value
    if isinstance(val, bool):
        return VariableType.BOOL, False
    if val is None:
        return VariableType.NULL, False
    if isinstance(val, float):
        return VariableType.FLOAT, False
    if isinstance(val, int):
        return VariableType.INT, False
    return VariableType.STRING, False


def check_pipeline_types(
    ops: list[KdlNode],
    ctx: ParseContext,
    lint: LintContext,
    start_type: VariableType = VariableType.DOCUMENT,
) -> VariableType:
    """Check pipeline type compatibility.

    Tracks (current_base, current_is_array) internally.
    Returns the final base type (for backward compat with callers that
    only need the VariableType).
    """
    current_base = start_type
    current_is_array = False

    for node in ops:
        op_name = node.name
        if not op_name:
            continue

        if op_name == "self":
            continue

        if op_name == "fallback":
            fb_base, fb_is_array = _fallback_literal_type(node, lint)
            if fb_base is None:
                continue
            if fb_is_array:
                if not current_is_array:
                    lint.error(
                        node,
                        message=f"'fallback {{}}' is only valid for list types, got {current_base.name}",
                        code="E100",
                        hint="use 'css-all' or 'xpath-all' to produce a list",
                    )
                continue
            if fb_base == VariableType.NULL:
                if current_base not in (
                    VariableType.STRING,
                    VariableType.INT,
                    VariableType.FLOAT,
                    VariableType.AUTO,
                ):
                    lint.error(
                        node,
                        message=f"'fallback #null' only valid for STRING/INT/FLOAT, got {current_base.name}",
                        code="E100",
                    )
                # #null marks the type as optional — we don't change base
                continue
            if (
                not _vt_compatible(current_base, current_is_array, fb_base)
                and current_base != VariableType.AUTO
            ):
                lint.error(
                    node,
                    message=f"'fallback' type {fb_base.name} does not match pipeline {current_base.name}",
                    code="E100",
                    hint=f"use a {current_base.name.lower()} literal or #null",
                )
                continue
            current_base = fb_base
            current_is_array = fb_is_array
            continue

        if op_name == "transform":
            args = [str(a.value) for a in node.args]
            t_name = args[0] if args else None
            if not t_name:
                lint.error(
                    node,
                    message="'transform' call requires a name",
                    code="E100",
                )
                current_base = VariableType.AUTO
                continue
            t_info = lint.transforms.get(t_name)
            if t_info is None:
                current_base = VariableType.AUTO
                continue
            t_accept = _VAR_TYPE_MAP.get(t_info.accept)
            t_ret = _VAR_TYPE_MAP.get(t_info.ret)
            if t_accept is not None and not _vt_compatible(
                current_base, current_is_array, t_accept
            ):
                lint.error(
                    node,
                    message=f"'transform {t_name}' expects {t_accept.name}, got {current_base.name}",
                    code="E100",
                )
            current_base = t_ret if t_ret is not None else VariableType.AUTO
            current_is_array = t_info.ret.startswith("LIST_")
            continue

        if op_name == "filter":
            if not current_is_array and current_base != VariableType.AUTO:
                lint.error(
                    node,
                    message=f"'filter' requires a list type, got {current_base.name}",
                    code="E100",
                    hint="use 'css-all', 'xpath-all', 're-all', or 'split' first",
                )
            continue

        if op_name == "assert":
            continue

        if op_name == "match":
            if current_base != start_type:
                lint.error(
                    node,
                    message="'match' must be the first operation in the field pipeline",
                    code="E100",
                )
            elif not _vt_compatible(
                current_base, current_is_array, VariableType.DOCUMENT
            ):
                lint.error(
                    node,
                    message=f"'match' requires DOCUMENT, got {current_base.name}",
                    code="E100",
                )
            current_base, current_is_array = _resolve_op_ret(
                "match", current_base, current_is_array
            )
            continue

        # block define — inline expansion
        if op_name in ctx.children_defines or op_name in lint.defines:
            define_ops = _get_define_ops(op_name, ctx, lint)
            if define_ops:
                result_base = check_pipeline_types(
                    define_ops, ctx, lint, start_type=current_base
                )
                current_base = result_base
            continue

        # regular op
        sig = _OP_TYPES.get(op_name)
        if sig is None:
            current_base = VariableType.AUTO
            continue
        if sig.accept is not None and not _vt_compatible(
            current_base, current_is_array, sig.accept
        ):
            lint.error(
                node,
                message=f"'{op_name}' does not accept {current_base.name}; expected {sig.accept.name}",
                code="E100",
                hint=_type_mismatch_hint(
                    op_name, current_base, current_is_array
                ),
            )
            current_base = VariableType.AUTO
            continue
        current_base, current_is_array = _resolve_op_ret(
            op_name, current_base, current_is_array
        )
    return current_base
