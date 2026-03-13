"""
KDL DSL linter — pipeline type checker.

Performs a second pass over each field pipeline after structural rules,
inferring and validating VariableType through the chain of operations.

Entry point: check_pipeline_types(ops, ctx, start_type)

Design notes:
- Every pipeline starts at VT.DOCUMENT (or self-ref type from -init).
- AUTO / LIST_AUTO are compatible with any concrete type (pass-through).
- Block defines are treated as inline expansion — their ops are substituted
  into the pipeline at the call site, starting from the current pipeline type.
  This means EXTRACT-INT works for both STRING and LIST_STRING contexts.
- filter / assert are transparent (ret = accept).
- fallback {} is only valid when current type is LIST_* (returns empty list).
  fallback <scalar> must match the pipeline ret type (or #null for OPT_*).
- transform is skipped (not yet implemented).
"""

from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.ast.types import VariableType as VT
from ssc_codegen.kdl.linter.base import LintContext, DefineKind, ErrorCode


# ── type-pair table ────────────────────────────────────────────────────────────
# (accept, ret) — None accept = AUTO (any type); None ret = identity.

_TP = tuple[VT | None, VT | None]

_OP_TYPES: dict[str, list[_TP]] = {
    # selectors
    "css": [(VT.DOCUMENT, VT.DOCUMENT)],
    "css-all": [(VT.DOCUMENT, VT.LIST_DOCUMENT)],
    "xpath": [(VT.DOCUMENT, VT.DOCUMENT)],
    "xpath-all": [(VT.DOCUMENT, VT.LIST_DOCUMENT)],
    "css-remove": [(VT.DOCUMENT, VT.DOCUMENT)],
    "xpath-remove": [(VT.DOCUMENT, VT.DOCUMENT)],
    # extract
    "text": [(VT.DOCUMENT, VT.STRING), (VT.LIST_DOCUMENT, VT.LIST_STRING)],
    "raw": [(VT.DOCUMENT, VT.STRING), (VT.LIST_DOCUMENT, VT.LIST_STRING)],
    "attr": [(VT.DOCUMENT, VT.STRING), (VT.LIST_DOCUMENT, VT.LIST_STRING)],
    # string (map semantics: LIST follows scalar)
    "trim": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "ltrim": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "rtrim": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "normalize-space": [
        (VT.STRING, VT.STRING),
        (VT.LIST_STRING, VT.LIST_STRING),
    ],
    "fmt": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "repl": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "lower": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "upper": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "rm-prefix": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "rm-suffix": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "rm-prefix-suffix": [
        (VT.STRING, VT.STRING),
        (VT.LIST_STRING, VT.LIST_STRING),
    ],
    "unescape": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "split": [(VT.STRING, VT.LIST_STRING)],
    "join": [(VT.LIST_STRING, VT.STRING)],
    # regex
    "re": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    "re-all": [(VT.STRING, VT.LIST_STRING)],
    "re-sub": [(VT.STRING, VT.STRING), (VT.LIST_STRING, VT.LIST_STRING)],
    # array — None accept = LIST_AUTO
    "index": [(None, None)],  # LIST_* → scalar
    "first": [(None, None)],  # LIST_* → scalar
    "last": [(None, None)],  # LIST_* → scalar
    "slice": [(None, None)],  # LIST_* → LIST_* (preserve)
    "len": [(None, VT.INT)],
    "unique": [(VT.LIST_STRING, VT.LIST_STRING)],
    # cast
    "to-int": [(VT.STRING, VT.INT), (VT.LIST_STRING, VT.LIST_INT)],
    "to-float": [(VT.STRING, VT.FLOAT), (VT.LIST_STRING, VT.LIST_FLOAT)],
    "to-bool": [(None, VT.BOOL)],  # any scalar
    "jsonify": [(VT.STRING, VT.JSON)],
    "nested": [(VT.DOCUMENT, VT.NESTED)],
    # control — handled specially in check_pipeline_types
    "self": [],
    "fallback": [],
    "filter": [],
    "assert": [],
    "match": [(VT.DOCUMENT, VT.STRING)],
}

# ops that extract a scalar from a list (LIST_* → scalar)
_LIST_TO_SCALAR_OPS: frozenset[str] = frozenset({"index", "first", "last"})

# ops that preserve the list type (LIST_* → LIST_*)
_LIST_PRESERVE_OPS: frozenset[str] = frozenset({"slice"})


# ── helpers ────────────────────────────────────────────────────────────────────


def _is_list_type(t: VT) -> bool:
    return t in (
        VT.LIST_AUTO,
        VT.LIST_DOCUMENT,
        VT.LIST_STRING,
        VT.LIST_INT,
        VT.LIST_FLOAT,
    )


def _compatible(got: VT, expected: VT) -> bool:
    """
    True if `got` satisfies `expected`.
    AUTO matches any scalar; LIST_AUTO matches any list type.
    """
    if got == expected:
        return True
    if got == VT.AUTO or expected == VT.AUTO:
        # AUTO is scalar — only compatible with other scalars (or AUTO)
        return not _is_list_type(got) and not _is_list_type(expected)
    if got == VT.LIST_AUTO or expected == VT.LIST_AUTO:
        # LIST_AUTO matches any list
        return _is_list_type(got) or _is_list_type(expected)
    return False


def _resolve_ret(op: str, accept: VT) -> VT:
    """
    Resolve the return type for `op` given `accept`.
    Returns AUTO when the op is unknown or has no matching overload.
    """
    pairs = _OP_TYPES.get(op)
    if not pairs:
        return VT.AUTO

    for pair_accept, pair_ret in pairs:
        if pair_accept is None or _compatible(accept, pair_accept):
            if pair_ret is not None:
                return pair_ret
            # None ret = infer from accept
            if op in _LIST_TO_SCALAR_OPS:
                return accept.scalar  # LIST_STRING → STRING, LIST_AUTO → AUTO
            if op in _LIST_PRESERVE_OPS:
                return accept  # LIST_* → LIST_*
            return accept  # identity
    return VT.AUTO


# ── define ops extraction ──────────────────────────────────────────────────────


def _get_define_ops(
    define_name: str,
    ctx: LintContext,
    _visiting: set[str] | None = None,
) -> list[Node] | None:
    """
    Return the flat list of op nodes for a block define.
    Handles nested define refs by recursively expanding them.
    Returns None on cycles or missing defines.

    Note: we return the raw Node list and let check_pipeline_types
    handle type-checking with the actual pipeline context type.
    """
    info = ctx.defines.get(define_name)
    if info is None or info.kind != DefineKind.BLOCK:
        return None

    if _visiting is None:
        _visiting = set()
    if define_name in _visiting:
        return None  # cycle guard
    _visiting.add(define_name)

    result: list[Node] = []
    for op_node in ctx.get_children_nodes(info.node):
        op_nm = ctx.node_name(op_node)
        if not op_nm:
            continue
        # nested define — expand inline
        if op_nm in ctx.defines and ctx.defines[op_nm].kind == DefineKind.BLOCK:
            nested = _get_define_ops(op_nm, ctx, _visiting)
            if nested is None:
                _visiting.discard(define_name)
                return None
            result.extend(nested)
        else:
            result.append(op_node)

    _visiting.discard(define_name)
    return result


# ── VT string parser (for transform properties) ───────────────────────────────

_VT_BY_NAME: dict[str, VT] = {t.name: t for t in VT}


def _parse_vt(name: str) -> VT | None:
    """Parse a type name string (e.g. "STRING") into a VariableType."""
    return _VT_BY_NAME.get(name.strip().upper())


# ── fallback literal type inference ───────────────────────────────────────────


def _fallback_literal_type(ctx: LintContext, node: Node) -> VT | None:
    """
    Infer the VariableType of the fallback literal.

      fallback ""        → STRING
      fallback 0         → INT
      fallback 0.0       → FLOAT
      fallback #true     → BOOL
      fallback #false    → BOOL
      fallback #null     → NULL
      fallback {}        → LIST_AUTO  (empty-list sugar — only valid for LIST_*)
    """
    if ctx.get_children_nodes(node):
        return VT.LIST_AUTO

    raw_args = ctx.get_raw_args(node)
    if not raw_args:
        return None  # malformed — structural rule handles this

    raw = raw_args[0]
    val = raw.value

    # All CST args arrive as identifier tokens in KDL tree-sitter grammar.
    # Distinguish by value string rather than node.type.
    if val in ("#true", "#false"):
        return VT.BOOL
    if val == "#null":
        return VT.NULL
    # quoted / raw strings are already extracted as plain text by get_raw_args;
    # check is_identifier=False to tell them apart from bare identifiers
    if not raw.is_identifier:
        # numeric: '.' or 'e' present → float, then try int, else string
        if "." in val or "e" in val.lower():
            try:
                float(val)
                return VT.FLOAT
            except ValueError:
                return VT.STRING
        try:
            int(val)
            return VT.INT
        except ValueError:
            pass
        return VT.STRING
    # bare identifier (unquoted word) — treat as string literal per KDL2
    return VT.STRING


# ── main pipeline checker ──────────────────────────────────────────────────────


def check_pipeline_types(
    ops: list[Node],
    ctx: LintContext,
    start_type: VT = VT.DOCUMENT,
) -> VT:
    """
    Type-check a flat list of pipeline operation nodes.
    Returns the final ret type of the pipeline.

    `start_type` is DOCUMENT for regular fields, or the inferred ret type
    of the -init sub-pipeline when `self` is the first op.
    """
    current = start_type

    for node in ops:
        op_name = ctx.node_name(node)
        if not op_name:
            continue

        # ── self ──────────────────────────────────────────────────────────────
        if op_name == "self":
            # accept = DOCUMENT (placeholder); actual start type is injected
            # via start_type at call site in _check_regular_field.
            # Here we just keep current (already set to init ret type).
            continue

        # ── fallback ──────────────────────────────────────────────────────────
        if op_name == "fallback":
            fb_type = _fallback_literal_type(ctx, node)
            if fb_type is None:
                continue

            if fb_type == VT.LIST_AUTO:
                # fallback {} — only valid when current type is a list
                if not _is_list_type(current) and current != VT.LIST_AUTO:
                    ctx.error(
                        node,
                        ErrorCode.TYPE_MISMATCH,
                        message=(
                            f"'fallback {{}}' (empty list) is only valid when the "
                            f"pipeline type is a list, got {current.name}"
                        ),
                        hint=(
                            "use 'css-all' or 'xpath-all' to produce a list, "
                            'or use a scalar fallback like fallback ""'
                        ),
                    )
                # ret stays as current list type (or LIST_AUTO)
                current = current if _is_list_type(current) else VT.LIST_AUTO
            elif fb_type == VT.NULL:
                # #null promotes scalar to OPT_*
                if current not in (
                    VT.STRING,
                    VT.INT,
                    VT.FLOAT,
                    VT.AUTO,
                    VT.OPT_STRING,
                    VT.OPT_INT,
                    VT.OPT_FLOAT,
                ):
                    ctx.error(
                        node,
                        ErrorCode.TYPE_MISMATCH,
                        message=(
                            f"'fallback #null' is only valid for STRING, INT, or FLOAT, "
                            f"got {current.name}"
                        ),
                        hint='use a typed fallback, e.g. fallback "" or fallback 0',
                    )
                current = current.optional
            else:
                # scalar fallback — must match current type
                if not _compatible(current, fb_type) and current not in (
                    VT.AUTO,
                    VT.LIST_AUTO,
                ):
                    ctx.error(
                        node,
                        ErrorCode.TYPE_MISMATCH,
                        message=(
                            f"'fallback' value type {fb_type.name} does not match "
                            f"pipeline type {current.name}"
                        ),
                        hint=(
                            f"use a {current.name.lower()} literal, "
                            f"or #null to make the field optional"
                        ),
                    )
                current = fb_type
            continue

        # ── transform ─────────────────────────────────────────────────────────
        if op_name == "transform":
            # DSL: transform <name>  (pipeline call — look up by name)
            args = ctx.get_args(node)
            t_name = args[0] if args else None
            if not t_name:
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message="'transform' call requires a name argument",
                    hint="example: transform to-base64",
                )
                current = VT.AUTO
                continue
            t_info = ctx.transforms.get(t_name)
            if t_info is None:
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message=f"'transform {t_name}' is not defined",
                    hint=f"declare it at module level: transform {t_name} accept=TYPE return=TYPE {{ ... }}",
                )
                current = VT.AUTO
                continue
            t_accept = _parse_vt(t_info.accept)
            t_ret = _parse_vt(t_info.ret)
            if t_accept is not None and not _compatible(current, t_accept):
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message=(
                        f"'transform {t_name}' expects {t_accept.name}, "
                        f"got {current.name}"
                    ),
                    hint=f"pipeline type must be {t_accept.name} before 'transform {t_name}'",
                )
            current = t_ret if t_ret is not None else VT.AUTO
            continue

        # ── filter ────────────────────────────────────────────────────────────
        if op_name == "filter":
            if not _is_list_type(current) and current not in (
                VT.AUTO,
                VT.LIST_AUTO,
            ):
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message=f"'filter' requires a list type, got {current.name}",
                    hint="'filter' works on LIST_DOCUMENT or LIST_STRING — use 'css-all', 'xpath-all', 're-all', or 'split' first",
                )
            # transparent — ret = accept
            continue

        # ── assert ────────────────────────────────────────────────────────────
        if op_name == "assert":
            # transparent — ret = accept; predicate children checked by _walk
            continue

        # ── match ─────────────────────────────────────────────────────────────
        if op_name == "match":
            # match must be the first op in a table field pipeline
            if current != start_type:
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message="'match' must be the first operation in the field pipeline",
                    hint="'match' selects a table row — place it before any other ops",
                )
            elif not _compatible(current, VT.DOCUMENT):
                ctx.error(
                    node,
                    ErrorCode.TYPE_MISMATCH,
                    message=f"'match' requires DOCUMENT, got {current.name}",
                    hint="'match' is only valid in table-type struct fields",
                )
            current = _resolve_ret("match", current)
            continue

        # ── block define — inline expansion ───────────────────────────────────
        if op_name in ctx.defines:
            info = ctx.defines[op_name]
            if info.kind == DefineKind.BLOCK:
                define_ops = _get_define_ops(op_name, ctx)
                if define_ops is None:
                    # cycle or empty — skip type checking
                    current = VT.AUTO
                    continue
                # expand inline: type-check define ops starting from current type
                current = check_pipeline_types(
                    define_ops, ctx, start_type=current
                )
            # scalar define as op — already reported by wildcard rule; skip
            continue

        # ── regular op ────────────────────────────────────────────────────────
        pairs = _OP_TYPES.get(op_name)
        if pairs is None:
            # unknown op — wildcard rule already reported; skip type check
            current = VT.AUTO
            continue

        accepted = [a for a, _ in pairs if a is not None]
        if accepted and not any(_compatible(current, a) for a in accepted):
            ctx.error(
                node,
                ErrorCode.TYPE_MISMATCH,
                message=(
                    f"'{op_name}' does not accept {current.name}; "
                    f"expected {' | '.join(t.name for t in accepted)}"
                ),
                hint=_type_mismatch_hint(op_name, current),
            )
            # continue with AUTO to suppress cascading errors
            current = VT.AUTO
            continue

        current = _resolve_ret(op_name, current)

    return current


# ── hint generator ─────────────────────────────────────────────────────────────


def _type_mismatch_hint(op_name: str, got: VT) -> str:
    _needs_text_first = {
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
    if got in (VT.DOCUMENT, VT.LIST_DOCUMENT) and op_name in _needs_text_first:
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
        return f"'{op_name}' requires a LIST type (LIST_DOCUMENT, LIST_STRING, etc.), got {got.name}"
    if op_name in ("unique", "join") and got != VT.LIST_STRING:
        return f"'{op_name}' requires LIST_STRING, got {got.name}"
    if not _is_list_type(got) and op_name == "len":
        return "'len' counts elements of any list — produce a list first (e.g. css-all, xpath-all, re-all, split)"
    if op_name == "split" and got != VT.STRING:
        return f"'split' requires STRING, got {got.name}"
    pairs = _OP_TYPES.get(op_name, [])
    valid = [a for a, _ in pairs if a is not None]
    if valid:
        return f"'{op_name}' accepts: {' | '.join(t.name for t in valid)}"
    return f"unexpected type {got.name} for '{op_name}'"


# Public alias for backward compatibility (used by rules_struct._KNOWN_OPS)
PIPELINE_TYPE_RULES = _OP_TYPES
