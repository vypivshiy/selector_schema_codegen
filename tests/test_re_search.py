"""Tests for re (regex search) operation codegen via std_re_search helper.

Covers:
- AST: Re carries span (source location via kdl Span)
- Parser: _expr_re populates span from KdlNode.span
- Python codegen: std_re_search() emission, message construction, location
- JS codegen: _stdReSearch() emission
- Runtime helpers: SscRegexError + std_re_search always exported
- Separate-runtime (-R): import std_re_search from runtime, do not inline
- Linter: re-all requires exactly one capture group (matches re behaviour)
- Fallback: re-no-match inside fallback is suppressed
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ssc_codegen.ast import Re
from ssc_codegen.core import parse_module
from kdlquery import Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(src: str, *, source_name: str = "test.kdl"):
    module, diagnostics = parse_module(src, source_path=Path(source_name))
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError("; ".join(d.message for d in errors))
    return module


def _find_re(module) -> Re:
    """Walk module body for the first Re node."""
    stack = list(module.body)
    while stack:
        node = stack.pop()
        if isinstance(node, Re):
            return node
        stack.extend(getattr(node, "body", []) or [])
    raise AssertionError("no Re node found")


# ---------------------------------------------------------------------------
# AST + parser
# ---------------------------------------------------------------------------


class TestReAst:
    def test_re_span_populated(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        module = _parse(src, source_name="my_schema.kdl")
        node = _find_re(module)
        assert module.source_file == "my_schema.kdl"
        assert node.span is not None
        assert node.span.start.line > 0
        assert node.span.start.column > 0

    def test_module_source_file_basename(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        module = _parse(src, source_name="C:/dev/proj/deep/foo.kdl")
        assert "/" not in module.source_file
        assert "\\" not in module.source_file
        assert module.source_file == "foo.kdl"

    def test_node_span_default_none(self):
        """AST nodes without explicit span must default to None."""
        from ssc_codegen.ast import Re

        node = Re()
        assert node.span is None


# ---------------------------------------------------------------------------
# Python codegen
# ---------------------------------------------------------------------------


@pytest.fixture
def py_lxml():
    from ssc_codegen.targets.python import PY_LXML_CONVERTER

    return PY_LXML_CONVERTER


class TestPythonReCodegen:
    def test_visit_re_emits_std_re_search(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        # Must NOT contain bare re.search(...)[1] form — crashes with
        # TypeError on no-match without context.
        assert "re.search(" not in code or "std_re_search" in code
        assert "std_re_search(" in code

    def test_re_default_message_includes_source_location(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src, source_name="my_schema.kdl"))
        assert "my_schema.kdl" in code
        # Struct.Field location marker — uses raw KDL field name.
        assert "Page.Field" in code
        # Pattern is included in the message for debugging.
        assert "(\\\\d+)" in code or "(\\d+)" in code

    def test_re_inline_class_definition_without_runtime(self, py_lxml):
        """Without -R, std_re_search inline must include SscRegexError
        class definition — otherwise NameError at runtime.
        """
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "class SscRegexError(Exception)" in code
        assert "def std_re_search(" in code

    def test_re_array_form_uses_listcomp(self, py_lxml):
        """css-all + re → list comprehension form."""
        src = (
            "struct Page type=item {\n"
            '    Field { css-all ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "[std_re_search(" in code
        assert "for i in" in code


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------


class TestReRuntimeHelpers:
    def test_runtime_module_content_has_ssc_regex_error(self):
        from ssc_codegen.ast import Module
        from ssc_codegen.generation.runtime import runtime_module_content

        content = runtime_module_content(Module())
        assert "class SscRegexError(Exception)" in content
        assert "def std_re_search(" in content

    def test_runtime_module_exec_re_search(self):
        """std_re_search must raise SscRegexError on no match, return
        first capture group on match.
        """
        from ssc_codegen.ast import Module
        from ssc_codegen.generation.runtime import runtime_module_content

        content = runtime_module_content(Module())
        ns: dict = {}
        exec(compile(content, "<runtime>", "exec"), ns)
        assert issubclass(ns["SscRegexError"], Exception)
        # No-match path.
        with pytest.raises(ns["SscRegexError"]):
            ns["std_re_search"](r"(\d+)", "abc", "loc")
        # Match path — returns first capture group.
        assert ns["std_re_search"](r"(\d+)", "abc123", "") == "123"
        # Empty msg fallback works.
        with pytest.raises(ns["SscRegexError"]) as exc_info:
            ns["std_re_search"](r"(x)", "abc", "")
        assert "ssc-gen" in str(exc_info.value) or "re-match" in str(
            exc_info.value
        )


# ---------------------------------------------------------------------------
# Separate-runtime (-R) mode
# ---------------------------------------------------------------------------


class TestSeparateRuntimeRe:
    def test_re_under_R_uses_import_not_inline(self):
        from ssc_codegen.targets.python import PY_LXML_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        module = _parse(src)
        code = PY_LXML_CONVERTER.convert(
            module, runtime_module="sscgen_runtime"
        )
        assert "from .sscgen_runtime import std_re_search" in code
        assert "def std_re_search(" not in code
        # SscRegexError imported via always-exports list.
        assert "SscRegexError" in code
        assert "class SscRegexError(Exception)" not in code


# ---------------------------------------------------------------------------
# JS codegen
# ---------------------------------------------------------------------------


class TestJsReCodegen:
    def test_visit_re_emits_std_re_search(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        assert "_stdReSearch(" in code

    def test_js_inline_class_definition(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        assert "class SscRegexError extends Error" in code
        assert "function _stdReSearch(" in code

    def test_js_array_form_uses_map(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css-all ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        assert ".map(s => _stdReSearch(" in code

    def test_js_default_message_includes_location(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re #"(\\d+)"# }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src, source_name="js_schema.kdl"))
        assert "js_schema.kdl" in code
        assert "Page.Field" in code


# ---------------------------------------------------------------------------
# Linter — re-all now requires exactly one capture group
# ---------------------------------------------------------------------------


class TestReAllLinter:
    def test_re_all_zero_groups_lints(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re-all #"foo"# }\n'
            "}\n"
        )
        _, diagnostics = parse_module(src, source_path=Path("t.kdl"))
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert errors, "expected lint error for re-all with 0 capture groups"

    def test_re_all_two_groups_lints(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re-all #"(a)(b)"# }\n'
            "}\n"
        )
        _, diagnostics = parse_module(src, source_path=Path("t.kdl"))
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert errors, "expected lint error for re-all with >1 capture groups"

    def test_re_all_one_group_passes(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; text; re-all #"(\\d+)"# }\n'
            "}\n"
        )
        _, diagnostics = parse_module(src, source_path=Path("t.kdl"))
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert not errors, "single-group re-all must pass linter"


# ---------------------------------------------------------------------------
# Fallback interaction
# ---------------------------------------------------------------------------


class TestReFallbackInteraction:
    def test_re_inside_fallback_emits_try_except(self, py_lxml):
        """re-no-match inside a fallback{} block must be caught by the
        surrounding try/except — SscRegexError is suppressed, returning
        the fallback value.
        """
        src = (
            "struct Page type=item {\n"
            "    Field {\n"
            '      css ".x"\n'
            "      text\n"
            r'      re #"(\d+)"#' + "\n"
            '      fallback ""\n'
            "    }\n"
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "try:" in code
        assert "except Exception:" in code
        # std_re_search must be called inside try-block (raw position).
        assert "std_re_search(" in code
