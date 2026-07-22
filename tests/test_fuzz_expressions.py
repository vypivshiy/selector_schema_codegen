"""Fuzz tests for KDL pipeline expressions.

Goal: for every pipeline op, predicate, container, special field and struct
variation, verify:
  1. AST parses without ERROR diagnostics.
  2. Python codegen (4 backends) is syntactically valid + names resolve
     via ``exec(compile(...))`` (catches dropped imports / NameError).
  3. JS codegen is syntactically valid (``node --check`` if node available).

Plus a hypothesis-based robustness layer that throws arbitrary op/predicate
sequences at the parser and asserts it NEVER raises (only emits diagnostics
or raises ``KDLParseError`` for syntactically broken KDL).

Output correctness of the generated parser is NOT tested here — only
syntactic/semantic validity of the produced source code.
"""

from __future__ import annotations

import ast as pyast
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from kdlquery import KDLParseError, Severity
from ssc_codegen.ast import VariableType
from ssc_codegen.core import parse_module
from ssc_codegen.core.type_checking import OP_TYPES, OpSig
from ssc_codegen.targets.javascript import JS_CONVERTER
from ssc_codegen.targets.python import (
    PY_BS4_CONVERTER,
    PY_LXML_CONVERTER,
    PY_PARSEL_CONVERTER,
    PY_SLAX_CONVERTER,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Catalog: pipeline op KDL forms
# ═══════════════════════════════════════════════════════════════════════════════


# Op forms — one or more KDL body-line variations per op.
# Forms are body lines (no indentation); they reference defines/json/structs
# provided by the shared _MODULE_PREFIX.
OP_FORMS: dict[str, tuple[str, ...]] = {
    # selectors
    "css": ('css ".card"',),
    "css-all": ('css-all ".card"',),
    "xpath": ('xpath "//div"',),
    "xpath-all": ('xpath-all "//div"',),
    "css-remove": ('css-remove ".ad"',),
    "xpath-remove": ('xpath-remove "//div"',),
    # extract
    "text": ("text",),
    "raw": ("raw",),
    "attr": ('attr "href"', 'attr "href" "data-id"'),
    # string ops
    "trim": ("trim", 'trim "ab"'),
    "ltrim": ("ltrim", 'ltrim "ab"'),
    "rtrim": ("rtrim", 'rtrim "ab"'),
    "normalize-space": ("normalize-space",),
    "fmt": ('fmt "pre{{}}post"',),
    "repl": ('repl "a" "b"',),
    "lower": ("lower",),
    "upper": ("upper",),
    "rm-prefix": ('rm-prefix "ab"',),
    "rm-suffix": ('rm-suffix "ab"',),
    "rm-prefix-suffix": ('rm-prefix-suffix "ab"',),
    "unescape": ("unescape",),
    "split": ('split ","',),
    "join": ('join ","',),
    # regex
    "re": ("re RE-DIGITS",),
    "re-all": ("re-all RE-DIGITS",),
    "re-sub": ('re-sub RE-WS "-"',),
    # array
    "index": ("index 0", "index 1", "index -1"),
    "first": ("first",),
    "last": ("last",),
    "slice": ("slice 0 2",),
    "len": ("len",),
    "unique": ("unique", "unique keep-order=#true"),
    # casts
    "to-int": ("to-int",),
    "to-float": ("to-float",),
    "to-bool": ("to-bool",),
    # terminal (require module-level setup — provided by _MODULE_PREFIX)
    "jsonify": ("jsonify TestJson", 'jsonify TestJson path="name"'),
    "nested": ("nested DummyList",),
}

# Ops excluded from generic solo/pair fuzzing for structural reasons.
# - match: must be first op in a table-struct field (tested separately)
# - jsonify/nested: terminal; included only as last op of a chain
_TERMINAL_OPS = frozenset({"jsonify", "nested"})
_SKIP_SOLO = frozenset({"match"}) | _TERMINAL_OPS

# Ops whose type signature demands a non-DOCUMENT input or a list input,
# so a minimal context-producing prefix must be prepended for solo tests.
_LIST_REQUIRED = frozenset(
    {"index", "first", "last", "slice", "len", "unique", "join", "filter"}
)


@dataclass(frozen=True)
class OpSpec:
    name: str
    sig: OpSig


def _all_pipeline_ops() -> list[OpSpec]:
    return [OpSpec(n, s) for n, s in OP_TYPES.items() if n in OP_FORMS]


def _type_compatible(
    prev_ret: VariableType | None, accept: VariableType | None
) -> bool:
    """Mirror of `_vt_compatible` in type_checking — non-erroring variant."""
    if accept is None:
        return True
    if prev_ret is None:
        return True
    if prev_ret == VariableType.AUTO or accept == VariableType.AUTO:
        return True
    return prev_ret == accept


def _prepend_for(op_name: str) -> str:
    """Return pipeline body lines that produce an acceptable input type.

    Empty string means: op accepts DOCUMENT (the default initial type) and
    needs no prepend.
    """
    if op_name in _LIST_REQUIRED:
        return 'css-all ".x"\n        text'
    # to-bool has accept=None but its handler requires a preceding node.
    if op_name == "to-bool":
        return 'css ".x"'
    sig = OP_TYPES[op_name]
    if sig.accept is None or sig.accept == VariableType.DOCUMENT:
        return ""
    if sig.accept == VariableType.STRING:
        return 'css ".x"\n        text'
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Catalog: predicates
# ═══════════════════════════════════════════════════════════════════════════════


# Predicate KDL forms grouped by the containers in which they are legal.
# Mirrors _FILTER_DISPATCH / _ASSERT_DISPATCH / _MATCH_DISPATCH in predicates.py.
_PRED_FORMS_FILTER: dict[str, tuple[str, ...]] = {
    "eq": ('eq "a"', 'eq "a" "b"'),
    "ne": ('ne "a"', 'ne "a" "b"'),
    "starts": ('starts "a"', 'starts "a" "b"'),
    "ends": ('ends "a"', 'ends "a" "b"'),
    "contains": ('contains "a"', 'contains "a" "b"'),
    "re": ("re RE-DIGITS",),
    "css": ('css ".icon"',),
    "xpath": ('xpath "//span"',),
    "has-attr": ('has-attr "href"', 'has-attr "href" "data-id"'),
    "attr-eq": ('attr-eq "data-kind" "nav"',),
    "attr-ne": ('attr-ne "rel" "nofollow"',),
    "attr-contains": ('attr-contains "href" "example"',),
    "attr-re": ('attr-re "href" RE-HREF',),
    "attr-starts": ('attr-starts "href" "/"',),
    "attr-ends": ('attr-ends "href" ".html"',),
    "text-contains": ('text-contains "guide"',),
    "text-ends": ('text-ends "more"',),
    "text-starts": ('text-starts "Go"',),
    "text-re": ("text-re RE-WORD",),
}

_PRED_FORMS_ASSERT: dict[str, tuple[str, ...]] = {
    **_PRED_FORMS_FILTER,
    "re-all": ("re-all RE-WORD",),
    "re-any": ("re-any RE-DIGITS",),
    "len-eq": ("len-eq 3",),
    "len-ne": ("len-ne 3",),
    "len-gt": ("len-gt 3",),
    "len-lt": ("len-lt 20",),
    "len-ge": ("len-ge 4",),
    "len-le": ("len-le 20",),
    "len-range": ("len-range 1 10",),
}

_PRED_FORMS_MATCH: dict[str, tuple[str, ...]] = {
    "eq": ('eq "id"', 'eq "id" "identifier"'),
    "ne": ('ne "skip"', 'ne "skip" "ignore"'),
    "starts": ('starts "price"',),
    "ends": ('ends "tax"', 'ends "tax" "fee"'),
    "contains": ('contains "price"', 'contains "price" "amount"'),
    "re": ("re RE-CODE",),
}


_LOGIC_TREES: tuple[str, ...] = (
    'not { eq "a" }',
    'and { eq "a"; eq "b" }',
    'or { eq "a"; eq "b" }',
    'and { not { eq "a" }; or { eq "b"; eq "c" } }',
    'or { and { eq "a"; eq "b" }; not { eq "c" } }',
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Shared KDL preamble (defines + json + dummy struct used by op forms)
# ═══════════════════════════════════════════════════════════════════════════════


_MODULE_PREFIX = """\
define CSS-X=".x"
define RE-DIGITS=#"(\\d+)"#
define RE-FLOAT=#"(\\d+\\.\\d+)"#
define RE-WS=#"\\s+"#
define RE-WORD=#"^[A-Za-z0-9_-]+$"#
define RE-HREF=#"https?://|/"#
define RE-CODE=#"^code"#

json TestJson {
    name str
    value int
}

(list)struct DummyList {
    @split-doc {
        css-all "div"
    }
    txt {
        css "span"
        text
    }
}
"""


def _wrap_item_struct(*, field_body: str, field_name: str = "f") -> str:
    """Wrap a field body into an item struct inside a full KDL module."""
    return (
        _MODULE_PREFIX + f"struct Fuzz {{\n"
        f"    {field_name} {{\n"
        f"        {field_body}\n"
        f"    }}\n"
        f"}}\n"
    )


def _indent_block(body: str, indent: str = "        ") -> str:
    """Re-indent a multi-line body string to live inside a field block."""
    lines = body.splitlines()
    return "\n".join(indent + ln if ln else ln for ln in lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Validators
# ═══════════════════════════════════════════════════════════════════════════════


_PY_CONVERTERS = {
    "py-bs4": PY_BS4_CONVERTER,
    "py-lxml": PY_LXML_CONVERTER,
    "py-parsel": PY_PARSEL_CONVERTER,
    "py-slax": PY_SLAX_CONVERTER,
}

# bs4 and slax DomSpellings raise NotImplementedError on xpath ops at
# codegen time (supports_xpath = False). Only lxml and parsel emit xpath.
_PY_SUPPORTS_XPATH = {"py-lxml", "py-parsel"}
_XPATH_RE = re.compile(r"\bxpath(?:-all|-remove)?\b")


def _skip_unsupported_xpath(body: str, target: str) -> None:
    if _XPATH_RE.search(body) and target not in _PY_SUPPORTS_XPATH:
        pytest.skip(f"{target} does not support xpath")


_NODE_BIN = shutil.which("node")


def _assert_ast_valid(kdl_src: str) -> object:
    mod, diags = parse_module(kdl_src, source_path=Path("fuzz.kdl"))
    errs = [d for d in diags if d.severity == Severity.ERROR]
    assert not errs, (
        "AST ERROR diagnostics:\n"
        + "\n".join(f"  - {d.message}" for d in errs)
        + f"\nKDL:\n{kdl_src}"
    )
    return mod


def _assert_py_valid(converter: object, mod: object) -> None:
    code = converter.convert(mod)  # type: ignore[attr-defined]
    pyast.parse(code)  # syntax
    exec(compile(code, "<fuzz>", "exec"), {})  # name resolution


def _assert_js_valid(mod: object) -> None:
    if _NODE_BIN is None:
        pytest.skip("node not in PATH")
    code = JS_CONVERTER.convert(mod)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        js_path = f.name
    try:
        proc = subprocess.run(
            [_NODE_BIN, "--check", js_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0, (
            f"node --check failed:\n{proc.stderr}\nJS:\n{code}"
        )
    finally:
        Path(js_path).unlink(missing_ok=True)


# Parametrize ids helper: keep pytest output readable.
def _converter_id(target: str) -> str:
    return target


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 1: solo op (with prepend context when needed)
# ═══════════════════════════════════════════════════════════════════════════════


def _solo_cases() -> list[tuple[str, str]]:
    """Return list of (op_name, kdl_field_body) for solo testing."""
    cases: list[tuple[str, str]] = []
    for op in _all_pipeline_ops():
        if op.name in _SKIP_SOLO:
            continue
        for form in OP_FORMS[op.name]:
            prepend = _prepend_for(op.name)
            body = f"{prepend}\n        {form}" if prepend else form
            cases.append((op.name, body))
    return cases


@pytest.mark.parametrize(
    "op_name,body", _solo_cases(), ids=lambda v: v if isinstance(v, str) else v
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_solo_op_py(op_name: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "op_name,body", _solo_cases(), ids=lambda v: v if isinstance(v, str) else v
)
def test_solo_op_js(op_name: str, body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 2: type-compatible op pairs
# ═══════════════════════════════════════════════════════════════════════════════


def _simulate(ops: list[str]) -> tuple[VariableType, bool]:
    """Simulate (base, is_array) state after running `ops` from DOCUMENT."""
    base = VariableType.DOCUMENT
    arr = False
    for n in ops:
        sig = OP_TYPES.get(n)
        if sig is None:
            continue
        new_base = sig.ret if sig.ret is not None else base
        if sig.force_list:
            new_arr = True
        elif sig.force_scalar:
            new_arr = False
        else:
            new_arr = arr
        base, arr = new_base, new_arr
    return base, arr


# Mapping from `_prepend_for` outputs to the op sequences they represent.
_PREPEND_TO_OPS: dict[str, list[str]] = {
    "": [],
    'css ".x"': ["css"],
    'css ".x"\n        text': ["css", "text"],
    'css-all ".x"\n        text': ["css-all", "text"],
}


def _apply_op(
    base: VariableType, arr: bool, op_name: str
) -> tuple[VariableType, bool]:
    sig = OP_TYPES[op_name]
    new_base = sig.ret if sig.ret is not None else base
    if sig.force_list:
        new_arr = True
    elif sig.force_scalar:
        new_arr = False
    else:
        new_arr = arr
    return new_base, new_arr


def _pair_cases() -> list[tuple[str, str, str]]:
    """All (op1, op2, body) where ret(op1) compatible with accept(op2)."""
    cases: list[tuple[str, str, str]] = []
    ops = _all_pipeline_ops()
    for op1 in ops:
        if op1.name == "match":
            continue
        prepend = _prepend_for(op1.name)
        pre_base, pre_arr = _simulate(_PREPEND_TO_OPS[prepend])
        # Validate op1 itself accepts what prepend produces — skip invalid.
        if not _type_compatible(pre_base, op1.sig.accept):
            continue
        if op1.name in _LIST_REQUIRED and not pre_arr:
            continue
        for form1 in OP_FORMS[op1.name]:
            head = f"{prepend}\n        {form1}" if prepend else form1
            base_after_1, arr_after_1 = _apply_op(pre_base, pre_arr, op1.name)
            for op2 in ops:
                if op2.name in _SKIP_SOLO and op2.name not in _TERMINAL_OPS:
                    continue
                if not _type_compatible(base_after_1, op2.sig.accept):
                    continue
                if op2.name in _LIST_REQUIRED and not arr_after_1:
                    continue
                if op2.name == "filter" and not arr_after_1:
                    continue
                for form2 in OP_FORMS[op2.name]:
                    body = f"{head}\n        {form2}"
                    cases.append((op1.name, op2.name, body))
    # Dedup while preserving order.
    seen: set[tuple[str, str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for c in cases:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


@pytest.mark.parametrize(
    "op1,op2,body", _pair_cases(), ids=lambda v: v if isinstance(v, str) else v
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_op_pair_py(op1: str, op2: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "op1,op2,body", _pair_cases(), ids=lambda v: v if isinstance(v, str) else v
)
def test_op_pair_js(op1: str, op2: str, body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 3: representative triples
# ═══════════════════════════════════════════════════════════════════════════════


_TRIPLES: tuple[tuple[str, ...], ...] = (
    # selector → extract → string op
    ('css ".title"', "text", "trim"),
    ('css ".title"', "text", "lower"),
    ('css ".title"', "text", 'repl "a" "b"'),
    ('css "a"', 'attr "href"', "lower"),
    ('css "a"', 'attr "href"', 'fmt "x{{}}"'),
    # selector-all → extract → array op
    ('css-all "a"', 'attr "href"', "first"),
    ('css-all "a"', 'attr "href"', "last"),
    ('css-all "a"', 'attr "href"', "index 0"),
    ('css-all "a"', 'attr "href"', "slice 0 2"),
    ('css-all "a"', 'attr "href"', "len"),
    ('css-all "a"', 'attr "href"', "unique"),
    ('css-all "a"', 'attr "href"', 'join ","'),
    # string → list → string
    ('css ".x"', "text", 'split ","'),
    # regex chains
    ('css ".x"', "text", "re RE-DIGITS"),
    ('css ".x"', "text", 're-sub RE-WS "-"'),
    ("raw", "", "re-all RE-DIGITS"),
    # casts
    ('css ".x"', "text", "to-int"),
    ('css ".x"', "text", "to-float"),
    ('css ".is-active"', "", "to-bool"),
    # cleanup chain
    ('css ".x"', "text", "normalize-space"),
    ('css ".x"', "text", "unescape"),
    ('css ".x"', "text", 'rm-prefix "a"'),
    ('css ".x"', "text", 'rm-suffix "a"'),
    ('css ".x"', "text", 'rm-prefix-suffix "a"'),
)


def _triple_cases() -> list[str]:
    cases: list[str] = []
    for spec in _TRIPLES:
        op1, op2, op3 = spec
        # op1 may be a multi-token form; trim empty trailing entries.
        lines = [ln for ln in (op1, op2, op3) if ln]
        cases.append("\n        ".join(lines))
    return cases


@pytest.mark.parametrize("body", _triple_cases())
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_op_triple_py(body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize("body", _triple_cases())
def test_op_triple_js(body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 4: fallback variations (literal / #null / {})
# ═══════════════════════════════════════════════════════════════════════════════


# (base_pipeline_producing_type, fallback_forms_valid_for_that_type)
_FALLBACK_PIPELINES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # STRING result
    (
        'css ".x"\n        text',
        ('fallback ""', 'fallback "default"', "fallback #null"),
    ),
    # INT result
    (
        'css ".x"\n        text\n        to-int',
        ("fallback 0", "fallback #null"),
    ),
    # FLOAT result
    (
        'css ".x"\n        text\n        to-float',
        ("fallback 0.0", "fallback #null"),
    ),
    # BOOL result
    ('css ".is"\n        to-bool', ("fallback #true", "fallback #false")),
    # LIST_STRING result
    (
        'css-all "a"\n        attr "href"',
        ("fallback {}",),
    ),
    # LIST_DOCUMENT result
    ('css-all ".card"', ("fallback {}",)),
)


def _fallback_cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for pipeline, fb_forms in _FALLBACK_PIPELINES:
        for fb in fb_forms:
            cases.append((pipeline, fb))
    return cases


@pytest.mark.parametrize(
    "pipeline,fb",
    _fallback_cases(),
    ids=[f"{i}" for i in range(len(_fallback_cases()))],
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_fallback_forms_py(pipeline: str, fb: str, target: str) -> None:
    body = f"{pipeline}\n        {fb}"
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "pipeline,fb",
    _fallback_cases(),
    ids=[f"{i}" for i in range(len(_fallback_cases()))],
)
def test_fallback_forms_js(pipeline: str, fb: str) -> None:
    body = f"{pipeline}\n        {fb}"
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 5: predicates inside filter / assert containers
# ═══════════════════════════════════════════════════════════════════════════════


def _filter_predicate_cases() -> list[tuple[str, str]]:
    """(predicate_name, full_field_body) for filter container."""
    cases: list[tuple[str, str]] = []
    for pred, forms in _PRED_FORMS_FILTER.items():
        for form in forms:
            body = (
                'css-all "a"\n'
                '        attr "href"\n'
                "        filter {\n"
                f"            {form}\n"
                "        }"
            )
            cases.append((pred, body))
    return cases


@pytest.mark.parametrize(
    "pred,body",
    _filter_predicate_cases(),
    ids=[c[0] for c in _filter_predicate_cases()],
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_predicate_in_filter_py(pred: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "pred,body",
    _filter_predicate_cases(),
    ids=[c[0] for c in _filter_predicate_cases()],
)
def test_predicate_in_filter_js(pred: str, body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


def _assert_predicate_cases() -> list[tuple[str, str]]:
    """(predicate_name, full_field_body) for assert container.

    List-only predicates (re-all, re-any, len-*) get a list-producing prefix.
    """
    cases: list[tuple[str, str]] = []
    list_predicates = {
        "re-all",
        "re-any",
        "len-eq",
        "len-ne",
        "len-gt",
        "len-lt",
        "len-ge",
        "len-le",
        "len-range",
    }
    for pred, forms in _PRED_FORMS_ASSERT.items():
        for form in forms:
            if pred in list_predicates:
                prefix = 'css ".x"\n        text\n        split ","'
            else:
                prefix = 'css ".x"\n        text'
            body = (
                f"{prefix}\n        assert {{\n            {form}\n        }}"
            )
            cases.append((pred, body))
    return cases


@pytest.mark.parametrize(
    "pred,body",
    _assert_predicate_cases(),
    ids=[c[0] for c in _assert_predicate_cases()],
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_predicate_in_assert_py(pred: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "pred,body",
    _assert_predicate_cases(),
    ids=[c[0] for c in _assert_predicate_cases()],
)
def test_predicate_in_assert_js(pred: str, body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 6: logic trees (not / and / or) inside filter + assert
# ═══════════════════════════════════════════════════════════════════════════════


def _logic_in_filter_cases() -> list[str]:
    bodies: list[str] = []
    for tree in _LOGIC_TREES:
        bodies.append(
            'css-all "a"\n'
            '            attr "href"\n'
            "            filter {\n"
            f"                {tree}\n"
            "            }"
        )
    return bodies


@pytest.mark.parametrize("body", _logic_in_filter_cases())
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_logic_in_filter_py(body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize("body", _logic_in_filter_cases())
def test_logic_in_filter_js(body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


def _logic_in_assert_cases() -> list[str]:
    bodies: list[str] = []
    for tree in _LOGIC_TREES:
        bodies.append(
            'css ".x"\n'
            "            text\n"
            "            assert {\n"
            f"                {tree}\n"
            "            }"
        )
    return bodies


@pytest.mark.parametrize("body", _logic_in_assert_cases())
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_logic_in_assert_py(body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize("body", _logic_in_assert_cases())
def test_logic_in_assert_js(body: str) -> None:
    kdl = _wrap_item_struct(field_body=body)
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 7: special struct fields (@init, @pre-validate, @check, @split-doc)
# ═══════════════════════════════════════════════════════════════════════════════


_SPECIAL_FIELD_BODIES: tuple[tuple[str, str], ...] = (
    (
        "@init",
        """\
@init {
        cached {
            css ".x"
            text
        }
    }

    f {
        @cached
        upper
    }""",
    ),
    (
        "@pre-validate",
        """\
@pre-validate {
        assert {
            css ".x"
        }
    }

    f {
        css ".x"
        text
    }""",
    ),
    (
        "@check",
        """\
@check is-x {
        assert {
            css ".x"
        }
        to-bool
        fallback #false
    }

    f {
        css ".x"
        text
    }""",
    ),
    (
        "@split-doc-list",
        """\
@split-doc {
        css-all ".card"
    }

    f {
        css ".x"
        text
    }""",
    ),
)


def _special_field_cases() -> list[tuple[str, str]]:
    return list(_SPECIAL_FIELD_BODIES)


@pytest.mark.parametrize(
    "kind,body",
    _special_field_cases(),
    ids=[k for k, _ in _special_field_cases()],
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_special_field_py(kind: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    # @split-doc only meaningful in non-item structs; use list.
    struct_prefix = "(list)" if kind == "@split-doc-list" else ""
    kdl = _MODULE_PREFIX + f"{struct_prefix}struct Fuzz {{\n    {body}\n}}\n"
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "kind,body",
    _special_field_cases(),
    ids=[k for k, _ in _special_field_cases()],
)
def test_special_field_js(kind: str, body: str) -> None:
    struct_prefix = "(list)" if kind == "@split-doc-list" else ""
    kdl = _MODULE_PREFIX + f"{struct_prefix}struct Fuzz {{\n    {body}\n}}\n"
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test 8: struct type variations (item / list / dict / table / flat)
# ═══════════════════════════════════════════════════════════════════════════════


_STRUCT_TYPE_BODIES: tuple[tuple[str, str], ...] = (
    (
        "item",
        """\
f {
        css ".x"
        text
        trim
    }""",
    ),
    (
        "list",
        """\
@split-doc {
        css-all ".card"
    }

    f {
        css ".x"
        text
    }""",
    ),
    (
        "flat",
        """\
f {
        css-all "a"
        attr "href"
    }""",
    ),
    (
        "dict",
        """\
@split-doc {
        css-all "meta[name][content]"
    }

    @key {
        attr "name"
    }

    @value {
        attr "content"
    }""",
    ),
    (
        "table",
        """\
@table {
        css "table"
    }

    @rows {
        css-all "tr"
    }

    @match {
        css "th"
        text
        lower
    }

    @value {
        css "td"
        text
    }

    f {
        match {
            eq "id"
        }
    }""",
    ),
)


def _struct_type_cases() -> list[tuple[str, str]]:
    return list(_STRUCT_TYPE_BODIES)


@pytest.mark.parametrize(
    "kind,body",
    _struct_type_cases(),
    ids=[k for k, _ in _struct_type_cases()],
)
@pytest.mark.parametrize(
    "target", list(_PY_CONVERTERS), ids=list(_PY_CONVERTERS)
)
def test_struct_type_py(kind: str, body: str, target: str) -> None:
    _skip_unsupported_xpath(body, target)
    prefix = {
        "item": "",
        "list": "(list)",
        "flat": "(flat)",
        "dict": "(dict)",
        "table": "(table)",
    }[kind]
    kdl = _MODULE_PREFIX + f"{prefix}struct Fuzz {{\n    {body}\n}}\n"
    mod = _assert_ast_valid(kdl)
    _assert_py_valid(_PY_CONVERTERS[target], mod)


@pytest.mark.parametrize(
    "kind,body",
    _struct_type_cases(),
    ids=[k for k, _ in _struct_type_cases()],
)
def test_struct_type_js(kind: str, body: str) -> None:
    prefix = {
        "item": "",
        "list": "(list)",
        "flat": "(flat)",
        "dict": "(dict)",
        "table": "(table)",
    }[kind]
    kdl = _MODULE_PREFIX + f"{prefix}struct Fuzz {{\n    {body}\n}}\n"
    mod = _assert_ast_valid(kdl)
    _assert_js_valid(mod)


# ═══════════════════════════════════════════════════════════════════════════════
#  Hypothesis robustness — parser must NEVER raise, only emit diagnostics.
#
#  Random op/predicate sequences are fed to `parse_module`. Any exception
#  other than KDLParseError (signalling syntactic KDL errors from the
#  upstream kdlquery lexer/parser) is a bug — the ssc_codegen layer must
#  surface semantic problems as ERROR diagnostics, never as crashes.
# ═══════════════════════════════════════════════════════════════════════════════


# Extra control ops not in OP_TYPES but legal pipeline tokens.
_CONTROL_FORMS: tuple[str, ...] = (
    'fallback ""',
    'fallback "x"',
    "fallback #null",
    "fallback 0",
    "fallback 0.0",
    "fallback #true",
    "fallback #false",
    "fallback {}",
)

_ALL_OP_FORMS: list[str] = [
    form for forms in OP_FORMS.values() for form in forms
] + list(_CONTROL_FORMS)

_ALL_FILTER_PREDS: list[str] = [
    form for forms in _PRED_FORMS_FILTER.values() for form in forms
] + list(_LOGIC_TREES)

_ALL_ASSERT_PREDS: list[str] = [
    form for forms in _PRED_FORMS_ASSERT.values() for form in forms
] + list(_LOGIC_TREES)

_ALL_MATCH_PREDS: list[str] = [
    form for forms in _PRED_FORMS_MATCH.values() for form in forms
] + list(_LOGIC_TREES)


# Hypothesis strategies.
_random_op_seq = st.lists(
    st.sampled_from(_ALL_OP_FORMS), min_size=1, max_size=10
)
_random_filter_preds = st.lists(
    st.sampled_from(_ALL_FILTER_PREDS), min_size=1, max_size=8
)
_random_assert_preds = st.lists(
    st.sampled_from(_ALL_ASSERT_PREDS), min_size=1, max_size=8
)
_random_match_preds = st.lists(
    st.sampled_from(_ALL_MATCH_PREDS), min_size=1, max_size=6
)


def _expect_no_crash(kdl: str, *, label: str) -> None:
    """Run `parse_module` and assert it does not raise.

    KDLParseError is allowed — it signals syntactic KDL errors from the
    upstream kdlquery lexer/parser. Any other exception is a bug.
    """
    try:
        parse_module(kdl, source_path=Path("fuzz.kdl"))
    except KDLParseError:
        return
    except Exception as e:  # pragma: no cover - reached only on bug
        pytest.fail(
            f"parser crashed on {label} with {type(e).__name__}: {e}\nKDL:\n{kdl}"
        )


@settings(
    max_examples=400,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(ops=_random_op_seq)
def test_parser_never_crashes_random_pipeline(ops: list[str]) -> None:
    """Random op sequences (ignoring type-compat) must not crash parser."""
    body = "\n        ".join(ops)
    kdl = _wrap_item_struct(field_body=body)
    _expect_no_crash(kdl, label="random pipeline")


@settings(
    max_examples=200,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(preds=_random_filter_preds)
def test_parser_never_crashes_random_filter(preds: list[str]) -> None:
    """Random predicate sequences inside `filter { ... }` must not crash."""
    inner = "\n                ".join(preds)
    body = (
        'css-all "a"\n'
        '        attr "href"\n'
        "        filter {\n"
        f"            {inner}\n"
        "        }"
    )
    kdl = _wrap_item_struct(field_body=body)
    _expect_no_crash(kdl, label="random filter body")


@settings(
    max_examples=200,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(preds=_random_assert_preds)
def test_parser_never_crashes_random_assert(preds: list[str]) -> None:
    """Random predicate sequences inside `assert { ... }` must not crash."""
    inner = "\n                ".join(preds)
    body = (
        'css ".x"\n'
        "        text\n"
        "        assert {\n"
        f"            {inner}\n"
        "        }"
    )
    kdl = _wrap_item_struct(field_body=body)
    _expect_no_crash(kdl, label="random assert body")


@settings(
    max_examples=100,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(preds=_random_match_preds)
def test_parser_never_crashes_random_match_in_table(preds: list[str]) -> None:
    """Random predicate sequences inside table `match { ... }` must not crash."""
    inner = "\n                ".join(preds)
    body = f"match {{\n            {inner}\n        }}"
    kdl = (
        _MODULE_PREFIX + "(table)struct Fuzz {\n"
        '    @table {\n        css "table"\n    }\n'
        '    @rows {\n        css-all "tr"\n    }\n'
        '    @match {\n        css "th"\n        text\n    }\n'
        '    @value {\n        css "td"\n        text\n    }\n'
        f"    f {{\n        {body}\n    }}\n"
        "}\n"
    )
    _expect_no_crash(kdl, label="random match body")


# Negative test: to-bool solo must produce ERROR diagnostic (regression for
# the IndexError crash that existed before this fix).
def test_to_bool_solo_emits_diagnostic_not_crash() -> None:
    kdl = "struct X {\n    f {\n        to-bool\n    }\n}\n"
    try:
        _, diags = parse_module(kdl, source_path=Path("fuzz.kdl"))
    except Exception as e:
        pytest.fail(
            f"parser crashed on solo `to-bool` with {type(e).__name__}: {e}"
        )
    errs = [d for d in diags if d.severity == Severity.ERROR]
    assert errs, "expected ERROR diagnostic for solo `to-bool`"
    assert any("to-bool" in d.message for d in errs), (
        f"expected 'to-bool' in message, got: {[d.message for d in errs]}"
    )
