"""
Pipeline type rules for KDL DSL linter.

Each op maps to a list of (accept, ret) pairs — explicit overloads.
  - accept=None  means any type is accepted (AUTO)
  - ret=None     means ret follows accept (identity / map semantics)

To add a new op:
    "my-op": [(VT.STRING, VT.INT), (VT.LIST_STRING, VT.LIST_INT)],
"""
from __future__ import annotations

from ssc_codegen.kdl.ast.types import VariableType as VT

# (accept, ret) — None means AUTO / follows accept
TypePair = tuple[VT | None, VT | None]
PipelineTypeMap = dict[str, list[TypePair]]

PIPELINE_TYPE_RULES: PipelineTypeMap = {
    # ── selectors ──────────────────────────────────────────────────────────────
    "css":              [(VT.DOCUMENT,       VT.DOCUMENT)],
    "css-all":          [(VT.DOCUMENT,       VT.LIST_DOCUMENT)],
    "xpath":            [(VT.DOCUMENT,       VT.DOCUMENT)],
    "xpath-all":        [(VT.DOCUMENT,       VT.LIST_DOCUMENT)],
    "css-remove":       [(VT.DOCUMENT,       VT.DOCUMENT)],
    "xpath-remove":     [(VT.DOCUMENT,       VT.DOCUMENT)],

    # ── extract ────────────────────────────────────────────────────────────────
    "text":             [(VT.DOCUMENT,       VT.STRING),
                         (VT.LIST_DOCUMENT,  VT.LIST_STRING)],
    "raw":              [(VT.DOCUMENT,       VT.STRING),
                         (VT.LIST_DOCUMENT,  VT.LIST_STRING)],
    "attr":             [(VT.DOCUMENT,       VT.STRING),
                         (VT.LIST_DOCUMENT,  VT.LIST_STRING)],

    # ── string ─────────────────────────────────────────────────────────────────
    "trim":             [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "ltrim":            [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "rtrim":            [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "normalize-space":  [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "fmt":              [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "repl":             [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "lower":            [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "upper":            [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "rm-prefix":        [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "rm-suffix":        [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "rm-prefix-suffix": [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "unescape":         [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "split":            [(VT.STRING,         VT.LIST_STRING)],
    "join":             [(VT.LIST_STRING,    VT.STRING)],

    # ── regex ──────────────────────────────────────────────────────────────────
    "re":               [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],
    "re-all":           [(VT.STRING,         VT.LIST_STRING)],
    "re-sub":           [(VT.STRING,         VT.STRING),
                         (VT.LIST_STRING,    VT.LIST_STRING)],

    # ── array ──────────────────────────────────────────────────────────────────
    "index":            [(None,              None)],   # LIST_AUTO -> AUTO
    "first":            [(None,              None)],
    "last":             [(None,              None)],
    "slice":            [(None,              None)],
    "len":              [(None,              VT.INT)],
    "unique":           [(VT.LIST_STRING,    VT.LIST_STRING)],

    # ── cast ───────────────────────────────────────────────────────────────────
    "to-int":           [(VT.STRING,         VT.INT),
                         (VT.LIST_STRING,    VT.LIST_INT)],
    "to-float":         [(VT.STRING,         VT.FLOAT),
                         (VT.LIST_STRING,    VT.LIST_FLOAT)],
    "to-bool":          [(None,              VT.BOOL)],
    "jsonify":          [(VT.STRING,         VT.JSON)],
    "nested":           [(VT.DOCUMENT,       VT.NESTED)],

    # ── control (не проверяются в type chain) ──────────────────────────────────
    "self":             [(None,              None)],
    "fallback":         [(None,              None)],
    "filter":           [(None,              None)],
    "assert":           [(None,              None)],
    "match":            [(VT.DOCUMENT,       VT.STRING)],
}

# ops that don't participate in type checking
SKIP_TYPE_CHECK: frozenset[str] = frozenset({
    "self", "fallback", "filter", "assert", "match",
})


def resolve_ret(op_name: str, accept: VT) -> VT:
    """
    Find the matching (accept→ret) pair and return ret.
    ret=None means ret follows accept (identity).
    No match → pass accept through.
    """
    pairs = PIPELINE_TYPE_RULES.get(op_name)
    if not pairs:
        return accept
    for pair_accept, pair_ret in pairs:
        if pair_accept is None or pair_accept == accept:
            return pair_ret if pair_ret is not None else accept
    return accept


def accepted_types(op_name: str) -> list[VT]:
    """Return all valid accept types for an op. Empty list = any type."""
    pairs = PIPELINE_TYPE_RULES.get(op_name, [])
    return [a for a, _ in pairs if a is not None]


def type_mismatch_hint(op_name: str, got: VT) -> str:
    """Generate a helpful hint for a type mismatch."""
    _needs_text_first = {
        "fmt", "trim", "ltrim", "rtrim", "lower", "upper",
        "re", "re-sub", "re-all", "to-int", "to-float",
        "split", "join", "normalize-space", "unescape",
        "rm-prefix", "rm-suffix", "rm-prefix-suffix",
    }
    if got in (VT.DOCUMENT, VT.LIST_DOCUMENT) and op_name in _needs_text_first:
        return "add 'text' or 'attr' before this operation to extract a string"
    if got == VT.LIST_STRING and op_name in ("css", "xpath", "css-all", "xpath-all"):
        return "selectors work on DOCUMENT, not strings"
    if got == VT.STRING and op_name in ("index", "first", "last", "slice", "unique", "join"):
        return "this operation expects a list — use 'css-all' or 're-all' to get a list"
    if got == VT.LIST_STRING and op_name == "split":
        return "'split' works on a single STRING, not LIST_STRING — use 'join' first"
    if got == VT.STRING and op_name == "len":
        return "'len' counts list elements — use 'css-all' or 're-all' to get a list first"
    valid = accepted_types(op_name)
    if valid:
        return f"'{op_name}' accepts: {' | '.join(t.name for t in valid)}"
    return f"unexpected type {got.name} for '{op_name}'"