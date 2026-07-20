"""Tests for assert container codegen.

Covers:
- AST: Assert carries message + span (source location via kdl Span)
- Parser: optional message arg parsing & lint
- Python codegen: std_assert() emission, message construction, location
- JS codegen: _stdAssert() emission
- Runtime helpers: SscAssertionError + std_assert always exported
- Separate-runtime (-R): import std_assert from runtime, do not inline
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ssc_codegen.ast import Assert
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


def _find_assert(module) -> Assert:
    """Walk module body for the first Assert node."""
    stack = list(module.body)
    while stack:
        node = stack.pop()
        if isinstance(node, Assert):
            return node
        stack.extend(getattr(node, "body", []) or [])
    raise AssertionError("no Assert node found")


# ---------------------------------------------------------------------------
# AST + parser
# ---------------------------------------------------------------------------


class TestAssertAst:
    def test_assert_without_message(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        node = _find_assert(_parse(src))
        assert node.message == ""

    def test_assert_with_string_message(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert "boom" { len-gt 0 } }\n'
            "}\n"
        )
        node = _find_assert(_parse(src))
        assert node.message == "boom"

    def test_assert_source_location_populated(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        module = _parse(src, source_name="my_schema.kdl")
        node = _find_assert(module)
        assert module.source_file == "my_schema.kdl"
        assert node.span is not None
        assert node.span.start.line > 0
        assert node.span.start.column > 0

    def test_assert_source_file_is_basename_not_absolute(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        module = _parse(src, source_name="C:/dev/project/deep/my_schema.kdl")
        # Must be basename only — no absolute path leaks into generated code.
        assert "/" not in module.source_file
        assert "\\" not in module.source_file
        assert module.source_file == "my_schema.kdl"

    def test_assert_too_many_args_lints(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert "one" "two" { len-gt 0 } }\n'
            "}\n"
        )
        _, diagnostics = parse_module(src, source_path=Path("t.kdl"))
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert errors, "expected lint error for >1 assert args"

    def test_assert_non_string_arg_lints(self):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert #true { len-gt 0 } }\n'
            "}\n"
        )
        _, diagnostics = parse_module(src, source_path=Path("t.kdl"))
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert errors, "expected lint error for non-string assert arg"


# ---------------------------------------------------------------------------
# Python codegen
# ---------------------------------------------------------------------------


@pytest.fixture
def py_lxml():
    from ssc_codegen.targets.python import PY_LXML_CONVERTER

    return PY_LXML_CONVERTER


class TestPythonAssertCodegen:
    def test_visit_assert_emits_std_assert(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        # Must NOT contain bare `assert (` — that is the old keyword form
        # which Python can strip under -O.
        assert "assert (" not in code
        # Must use std_assert helper instead.
        assert "std_assert(" in code

    def test_assert_custom_message_in_output(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert "boom here" { len-gt 0 } }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "'boom here'" in code or '"boom here"' in code

    def test_assert_default_message_includes_source_location(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src, source_name="my_schema.kdl"))
        # File basename + line:col format, no absolute path.
        assert "my_schema.kdl" in code
        # Struct.Field location marker — uses raw KDL field name as
        # written by the user (here: "Field", not "field").
        assert "Page.Field" in code

    def test_assert_pre_validate_marker(self, py_lxml):
        src = (
            "struct Page type=item {\n"
            "    @pre-validate {\n"
            '      assert { css ".root" }\n'
            "    }\n"
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "@pre-validate" in code

    def test_assert_inline_class_definition_without_runtime(self, py_lxml):
        """Without -R, std_assert inline must include SscAssertionError
        class definition — otherwise NameError at runtime.
        """
        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        assert "class SscAssertionError(Exception)" in code
        assert "def std_assert(" in code


# ---------------------------------------------------------------------------
# Runtime exports
# ---------------------------------------------------------------------------


class TestRuntimeExports:
    def test_runtime_always_exports_ssc_assertion_error(self):
        """Even modules without assert{} must export SscAssertionError so
        consumer code can ``except SscAssertionError`` unconditionally.
        """
        from ssc_codegen.targets.python.rest import runtime_export_names
        from ssc_codegen.ast import Module

        # Empty HTML module — no asserts.
        mod = Module()
        names = runtime_export_names(mod)
        assert "SscAssertionError" in names
        assert "SscRegexError" in names

    def test_runtime_module_content_has_ssc_assertion_error(self):
        from ssc_codegen.ast import Module
        from ssc_codegen.generation.runtime import runtime_module_content

        content = runtime_module_content(Module())
        assert "class SscAssertionError(Exception)" in content
        assert "class SscRegexError(Exception)" in content
        assert "def std_assert(" in content
        assert "def std_re_search(" in content

    def test_runtime_file_py_exec_valid(self):
        """Runtime module file must be syntactically valid + importable."""
        from ssc_codegen.ast import Module
        from ssc_codegen.generation.runtime import runtime_module_content

        content = runtime_module_content(Module())
        # Compile check — raises SyntaxError on bad source.
        compile(content, "<runtime>", "exec")
        ns: dict = {}
        exec(compile(content, "<runtime>", "exec"), ns)
        assert issubclass(ns["SscAssertionError"], Exception)
        assert issubclass(ns["SscRegexError"], Exception)
        # Smoke: std_assert(False) raises SscAssertionError.
        with pytest.raises(ns["SscAssertionError"]):
            ns["std_assert"](False, "test")
        # Smoke: std_assert(True) is a no-op.
        ns["std_assert"](True, "should not raise")
        # Smoke: std_re_search with no match raises SscRegexError.
        with pytest.raises(ns["SscRegexError"]):
            ns["std_re_search"](r"(x)", "abc", "no match")
        # Smoke: std_re_search with match returns capture group.
        assert ns["std_re_search"](r"(\d+)", "abc123", "") == "123"


# ---------------------------------------------------------------------------
# Separate-runtime (-R) mode
# ---------------------------------------------------------------------------


class TestSeparateRuntimeAssert:
    def test_assert_under_R_uses_import_not_inline(self):
        """Under -R, std_assert must be imported from runtime; the
        inline ``def std_assert(...)`` must NOT be emitted into the
        parser file.
        """
        from ssc_codegen.targets.python import PY_LXML_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        module = _parse(src)
        code = PY_LXML_CONVERTER.convert(
            module, runtime_module="sscgen_runtime"
        )
        assert "from .sscgen_runtime import std_assert" in code
        # Inline definition must be absent.
        assert "def std_assert(" not in code
        # SscAssertionError is imported via the always-exports list.
        assert "SscAssertionError" in code
        assert "class SscAssertionError(Exception)" not in code

    def test_assert_under_R_message_still_emitted(self):
        from ssc_codegen.targets.python import PY_LXML_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert "custom msg" { len-gt 0 } }\n'
            "}\n"
        )
        module = _parse(src, source_name="loc.kdl")
        code = PY_LXML_CONVERTER.convert(
            module, runtime_module="sscgen_runtime"
        )
        assert "'custom msg'" in code or '"custom msg"' in code


# ---------------------------------------------------------------------------
# JS codegen
# ---------------------------------------------------------------------------


class TestJsAssertCodegen:
    def test_visit_assert_emits_std_assert(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        # Must NOT contain old hard-coded throw new Error form.
        assert "throw new Error('Assertion failed')" not in code
        # Must use _stdAssert helper.
        assert "_stdAssert(" in code

    def test_assert_custom_message_in_js_output(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert "boom" { len-gt 0 } }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        assert "'boom'" in code

    def test_js_inline_class_definition(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct Page type=item {\n"
            '    Field { css ".x"; assert { len-gt 0 } }\n'
            "}\n"
        )
        code = JS_CONVERTER.convert(_parse(src))
        assert "class SscAssertionError extends Error" in code
        assert "function _stdAssert(" in code


# ---------------------------------------------------------------------------
# Fallback interaction (current behaviour preserved)
# ---------------------------------------------------------------------------


class TestAssertFallbackInteraction:
    def test_assert_inside_fallback_emits_try_except(self, py_lxml):
        """assert failure inside a fallback{} block must still be caught
        — fallback suppresses the SscAssertionError per existing
        behaviour.
        """
        src = (
            "struct Page type=item {\n"
            "    Field {\n"
            '      css ".x"\n'
            "      text\n"
            "      assert { len-gt 100 }\n"
            '      fallback ""\n'
            "    }\n"
            "}\n"
        )
        code = py_lxml.convert(_parse(src))
        # Fallback wraps the pipeline in try/except — assert failure
        # is suppressed, returning the fallback value.
        assert "try:" in code
        assert "except Exception:" in code
