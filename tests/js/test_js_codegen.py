"""JS codegen integration tests via pytest.

Generates JavaScript code via js_pure converter, runs it in Node.js + jsdom,
and validates the parse results. All tests are skipped if Node.js is not found.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ssc_codegen.core import parse_module
from kdlquery import Severity
from ssc_codegen.targets.javascript import JS_CONVERTER
from ssc_codegen.naming import to_pascal_case

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = ROOT / "tests" / "integration" / "schemas"
HTML_FIXTURE = ROOT / "tests" / "integration" / "fixtures" / "dsl_coverage.html"
JS_RUNNER = Path(__file__).resolve().parent / "js_runner.cjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js not found in PATH",
)


def _parse_kdl(schema_path: Path):
    src = schema_path.read_text(encoding="utf-8-sig")
    module_ast, diagnostics = parse_module(src, source_path=schema_path)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError(
            f"Parse errors in {schema_path}: "
            + "; ".join(d.message for d in errors)
        )
    return module_ast


def _run_js_schema(schema_path: Path, struct_name: str) -> dict | list:
    module_ast = _parse_kdl(schema_path)
    class_name = to_pascal_case(struct_name)
    code = JS_CONVERTER.convert(module_ast)

    proc = subprocess.run(
        ["node", str(JS_RUNNER), str(HTML_FIXTURE), class_name],
        input=code,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"JS runtime error for {schema_path.name}:{struct_name}:\n{proc.stderr}"
        )
    return json.loads(proc.stdout)


# ── Smoke: each schema × js-pure generates valid JS that runs ────────────────

_SMOKES = [
    ("01_strings_basic.kdl", "StringsBasic"),
    ("02_arrays_and_conversions.kdl", "ArraysAndConversions"),
    ("03_filters_and_predicates.kdl", "FiltersAndPredicates"),
    ("05_flat.kdl", "FlatCoverage"),
    ("06_dict.kdl", "MetaDict"),
    ("06_dict.kdl", "MetaAliasDict"),
    ("06_dict.kdl", "DictRoot"),
    ("07_table.kdl", "TableCoverage"),
    ("18_json_basic.kdl", "JsonBasic"),
    ("19_json_mixed.kdl", "JsonMixed"),
]


@pytest.mark.parametrize(
    "schema_file,struct_name", _SMOKES, ids=[f"{s}:{n}" for s, n in _SMOKES]
)
def test_js_codegen_runs_without_error(schema_file, struct_name):
    result = _run_js_schema(SCHEMAS_DIR / schema_file, struct_name)
    assert result is not None


# ── StringsBasic ─────────────────────────────────────────────────────────────


class TestJsStringsBasic:
    def test_returns_list_of_2(self):
        r = _run_js_schema(SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic")
        assert isinstance(r, list) and len(r) == 2

    def test_fields_present(self):
        r = _run_js_schema(SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic")
        for item in r:
            assert all(
                k in item for k in ("title", "link", "slug", "activeFlag")
            )

    def test_field_types(self):
        r = _run_js_schema(SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic")
        item = r[0]
        assert isinstance(item["title"], str)
        assert isinstance(item["activeFlag"], bool)


# ── ArraysAndConversions ─────────────────────────────────────────────────────


class TestJsArraysAndConversions:
    def test_structure_and_types(self):
        r = _run_js_schema(
            SCHEMAS_DIR / "02_arrays_and_conversions.kdl",
            "ArraysAndConversions",
        )
        assert isinstance(r, list) and len(r) == 2
        item = r[0]
        assert isinstance(item["tokenList"], list)
        assert isinstance(item["score"], int)
        assert isinstance(item["ratio"], float)


# ── Dict ──────────────────────────────────────────────────────────────────────


class TestJsDict:
    def test_meta_dict(self):
        r = _run_js_schema(SCHEMAS_DIR / "06_dict.kdl", "MetaDict")
        assert isinstance(r, dict) and "description" in r

    def test_meta_alias_dict(self):
        r = _run_js_schema(SCHEMAS_DIR / "06_dict.kdl", "MetaAliasDict")
        assert isinstance(r, dict) and "og:title" in r

    def test_dict_root(self):
        r = _run_js_schema(SCHEMAS_DIR / "06_dict.kdl", "DictRoot")
        assert "namedMeta" in r and "aliasMeta" in r


# ── Table ────────────────────────────────────────────────────────────────────


class TestJsTable:
    def test_field_values(self):
        r = _run_js_schema(SCHEMAS_DIR / "07_table.kdl", "TableCoverage")
        assert r["identifier"] == "ABC-123"
        assert r["price"] == 9.99
        assert r["state"] == "active"


# ── JsonBasic ────────────────────────────────────────────────────────────────


class TestJsJsonBasic:
    def test_full_payload(self):
        r = _run_js_schema(SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic")
        assert isinstance(r["fullPayload"], list)
        assert len(r["fullPayload"]) == 2

    def test_item_shape(self):
        r = _run_js_schema(SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic")
        item = r["fullPayload"][0]
        assert item["text"] == "Quote one"
        assert item["score"] == 7

    def test_path_access(self):
        r = _run_js_schema(SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic")
        assert r["firstAuthorName"] == "Author One"
        assert r["firstTags"] == ["alpha", "beta"]
