"""Tests for (raw)struct lint rules: forbidden HTML operations."""

from __future__ import annotations

import pytest
from ssc_codegen.core import parse_module
from kdlquery import Severity


def _check_errors(src: str) -> list[str]:
    _, diags = parse_module(src)
    return [d.message for d in diags if d.severity == Severity.ERROR]


_FORBIDDEN_OPS = {
    "css": 'css ".x"',
    "text": "text",
    "raw": "raw",
    "attr": 'attr "href"',
    "xpath": 'xpath "//div"',
}


class TestRawLintForbiddenOps:
    @pytest.mark.parametrize("op", ["css", "text", "raw", "attr", "xpath"])
    def test_forbidden_ops(self, op: str) -> None:
        errors = _check_errors(
            f"(raw)struct S {{\n  f {{ {_FORBIDDEN_OPS[op]} }}\n}}\n"
        )
        assert any("forbidden" in e for e in errors)

    def test_string_ops_allowed(self):
        errors = _check_errors(
            "(raw)struct S {\n"
            '  f { re #"(\\w+)"# }\n'
            '  g { split "," }\n'
            "  h { upper }\n"
            "}\n"
        )
        assert not errors


class TestRawStructParsing:
    def test_raw_item_no_errors(self):
        errors = _check_errors('(raw)struct S {\n  f { re #"x(.+)"# }\n}\n')
        assert not errors

    def test_raw_list_with_split_doc(self):
        errors = _check_errors(
            '(raw)struct S {\n  @split-doc { split "\\n" }\n  f { trim }\n}\n'
        )
        assert not errors

    def test_raw_with_init(self):
        errors = _check_errors(
            '(raw)struct S {\n  @init { x { split "?" } }\n  f { @x }\n}\n'
        )
        assert not errors

    def test_raw_with_request(self):
        errors = _check_errors(
            "(raw)struct S {\n"
            '  @request "curl https://example.com"\n'
            '  f { re #"x(.+)"# }\n'
            "}\n"
        )
        assert not errors
