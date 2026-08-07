"""Tests for fn / (raw)fn lint rules and parsing."""

from ssc_codegen.core import parse_module
from kdlquery import Severity


def _check_errors(src: str) -> list[str]:
    _, diags = parse_module(src)
    return [d.message for d in diags if d.severity == Severity.ERROR]


class TestFnParsing:
    def test_html_fn_no_errors(self):
        errors = _check_errors('fn title {\n  css "h1"\n  text\n}\n')
        assert not errors

    def test_raw_fn_no_errors(self):
        errors = _check_errors('(raw)fn w {\n  split ","\n  index 0\n}\n')
        assert not errors

    def test_fn_with_doc(self):
        errors = _check_errors(
            'fn title {\n  @doc "desc"\n  css "h1"\n  text\n}\n'
        )
        assert not errors

    def test_multiple_fns(self):
        errors = _check_errors(
            'fn a {\n  css "h1"\n  text\n}\nfn b {\n  css "h2"\n  text\n}\n'
        )
        assert not errors

    def test_fn_requires_name(self):
        errors = _check_errors('fn {\n  css "h1"\n  text\n}\n')
        assert any("requires a name" in e for e in errors)

    def test_fn_requires_ops(self):
        errors = _check_errors("fn empty {\n}\n")
        assert any("at least one" in e for e in errors)


class TestFnLintForbiddenDirectives:
    def test_no_init_in_fn(self):
        errors = _check_errors(
            'fn x {\n  @init { y { css ".z"; text } }\n  css "h1"\n  text\n}\n'
        )
        assert any("not allowed" in e for e in errors)

    def test_no_check_in_fn(self):
        errors = _check_errors(
            'fn x {\n  @check foo { css "h1"; text; to-bool }\n}\n'
        )
        assert any("not allowed" in e for e in errors)

    def test_no_split_doc_in_fn(self):
        errors = _check_errors('fn x {\n  @split-doc { split "\\n" }\n}\n')
        assert any("not allowed" in e for e in errors)


class TestRawFnForbiddenOps:
    def test_css_forbidden(self):
        errors = _check_errors('(raw)fn x {\n  css ".x"\n  text\n}\n')
        assert any("forbidden" in e for e in errors)

    def test_text_forbidden(self):
        errors = _check_errors("(raw)fn x {\n  text\n}\n")
        assert any("forbidden" in e for e in errors)

    def test_string_ops_allowed(self):
        errors = _check_errors('(raw)fn x {\n  split ","\n  index 0\n}\n')
        assert not errors
