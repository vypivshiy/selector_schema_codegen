"""Integration tests: generate Python code from KDL schemas, exec, and verify parse results.

Each test case: KDL schema + struct name → generate code for each py-* target → exec → parse HTML → assert output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ssc_codegen.core import parse_module
from kdlquery import Severity
from ssc_codegen.converters.helpers import to_pascal_case

SCHEMAS_DIR = Path(__file__).parent / "schemas"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
HTML_FIXTURE = FIXTURES_DIR / "dsl_coverage.html"

# Python targets and their converter imports
_PY_TARGETS = {
    "py-bs4": "ssc_codegen.converters.py_bs4:PY_BASE_CONVERTER",
    "py-lxml": "ssc_codegen.converters.py_lxml:PY_LXML_CONVERTER",
    "py-parsel": "ssc_codegen.converters.py_parsel:PY_PARSEL_CONVERTER",
    "py-slax": "ssc_codegen.converters.py_slax:PY_SLAX_CONVERTER",
}


def _get_converter(target: str):
    module_path, attr = _PY_TARGETS[target].rsplit(":", 1)
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, attr)


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


def _run_schema(
    schema_path: str | Path,
    struct_name: str,
    html: str,
    target: str = "py-bs4",
) -> dict | list:
    """Parse KDL, generate code, exec, instantiate class, call parse()."""
    p = Path(schema_path)
    module_ast = _parse_kdl(p)
    class_name = to_pascal_case(struct_name)

    converter = _get_converter(target)
    code = converter.convert(module_ast)

    namespace: dict = {}
    exec(code, namespace)  # noqa: S102

    cls = namespace[class_name]
    return cls(html).parse()


@pytest.fixture(scope="module")
def html() -> str:
    return HTML_FIXTURE.read_text(encoding="utf-8")


# ── Test cases: (schema_file, struct_name) ────────────────────────────────────

_SCHEMAS = [
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

_TARGETS = ["py-bs4", "py-lxml", "py-parsel", "py-slax"]


# ── Parametrized: each schema × each target ───────────────────────────────────


@pytest.mark.parametrize(
    "schema_file,struct_name", _SCHEMAS, ids=[f"{s}:{n}" for s, n in _SCHEMAS]
)
@pytest.mark.parametrize("target", _TARGETS)
def test_codegen_runs_without_error(schema_file, struct_name, target, html):
    """Generated code executes and returns a result without exceptions."""
    schema_path = SCHEMAS_DIR / schema_file
    result = _run_schema(schema_path, struct_name, html, target)
    assert result is not None


# ── Structure validation tests (py-bs4 baseline) ─────────────────────────────


# NOTE: StringsBasic uses the `raw` operation which produces different whitespace
# across backend libraries (bs4 str(), lxml html.tostring(), parsel .get(), slax .html).
# Each library serializes HTML differently — this is inherent, not a bug.
# Test each backend separately instead of cross-target comparison.


class TestStringsBasic:
    @pytest.mark.parametrize("target", _TARGETS)
    def test_returns_list(self, html, target):
        result = _run_schema(
            SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic", html, target
        )
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.parametrize("target", _TARGETS)
    def test_fields_present(self, html, target):
        result = _run_schema(
            SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic", html, target
        )
        for item in result:
            assert "title" in item
            assert "link" in item
            assert "slug" in item
            assert "active_flag" in item

    @pytest.mark.parametrize("target", _TARGETS)
    def test_field_types(self, html, target):
        result = _run_schema(
            SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic", html, target
        )
        item = result[0]
        assert isinstance(item["title"], str)
        assert isinstance(item["link"], str)
        assert isinstance(item["slug"], str)
        assert isinstance(item["active_flag"], bool)


class TestArraysAndConversions:
    def test_returns_list(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "02_arrays_and_conversions.kdl",
            "ArraysAndConversions",
            html,
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_field_types(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "02_arrays_and_conversions.kdl",
            "ArraysAndConversions",
            html,
        )
        item = result[0]
        assert isinstance(item["token_list"], list)
        assert isinstance(item["first_token"], str)
        assert isinstance(item["state_code"], int)
        assert isinstance(item["score"], int)
        assert isinstance(item["ratio"], float)
        assert isinstance(item["any_link_count"], int)

    def test_token_list_values(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "02_arrays_and_conversions.kdl",
            "ArraysAndConversions",
            html,
        )
        assert result[0]["token_list"] == [
            "tag-core-alpha1-x",
            "item-beta2-y",
            "ref3",
        ]


class TestFiltersAndPredicates:
    def test_returns_list(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "03_filters_and_predicates.kdl",
            "FiltersAndPredicates",
            html,
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fields_present(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "03_filters_and_predicates.kdl",
            "FiltersAndPredicates",
            html,
        )
        for item in result:
            assert "filtered_links" in item
            assert "logic_check" in item
            assert "numeric_check" in item


class TestFlatCoverage:
    def test_returns_list(self, html):
        result = _run_schema(SCHEMAS_DIR / "05_flat.kdl", "FlatCoverage", html)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_contains_hrefs(self, html):
        result = _run_schema(SCHEMAS_DIR / "05_flat.kdl", "FlatCoverage", html)
        # flat struct returns a flat list — contains hrefs and tokens
        assert any("/nested/" in str(v) for v in result)


class TestDictSchemas:
    def test_meta_dict_returns_dict(self, html):
        result = _run_schema(SCHEMAS_DIR / "06_dict.kdl", "MetaDict", html)
        assert isinstance(result, dict)
        assert "description" in result

    def test_meta_alias_dict_returns_dict(self, html):
        result = _run_schema(SCHEMAS_DIR / "06_dict.kdl", "MetaAliasDict", html)
        assert isinstance(result, dict)
        assert "og:title" in result

    def test_dict_root_nested(self, html):
        result = _run_schema(SCHEMAS_DIR / "06_dict.kdl", "DictRoot", html)
        assert isinstance(result, dict)
        assert "named_meta" in result
        assert "alias_meta" in result
        assert isinstance(result["named_meta"], dict)
        assert isinstance(result["alias_meta"], dict)


class TestTableCoverage:
    def test_returns_dict(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "07_table.kdl", "TableCoverage", html
        )
        assert isinstance(result, dict)

    def test_field_values(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "07_table.kdl", "TableCoverage", html
        )
        assert result["identifier"] == "ABC-123"
        assert result["code_value"] == "CODE-1"
        assert result["price"] == 9.99
        assert result["tax_or_fee"] == 1.25
        assert result["state"] == "active"


# ── Cross-target consistency: all py targets produce identical results ────────


@pytest.mark.parametrize(
    "schema_file,struct_name", _SCHEMAS, ids=[f"{s}:{n}" for s, n in _SCHEMAS]
)
def test_all_targets_produce_same_result(schema_file, struct_name, html):
    """All Python targets produce identical parse results for the same schema."""
    schema_path = SCHEMAS_DIR / schema_file
    results = {}
    for target in _TARGETS:
        results[target] = _run_schema(schema_path, struct_name, html, target)

    baseline = results["py-bs4"]
    for target, result in results.items():
        assert result == baseline, (
            f"{target} produced different result than py-bs4 for {schema_file}:{struct_name}"
        )


# ── Nested JSON schemas ────────────────────────────────────────────────────────


def test_json_nested_root(html):
    _run_schema(SCHEMAS_DIR / "04_json_and_nested.kdl", "JsonNestedRoot", html)


def test_coverage_root_full(html):
    _run_schema(SCHEMAS_DIR / "00_full.kdl", "CoverageRoot", html)


# ── JSON integration: validate parsed results ────────────────────────────────


class TestJsonBasic:
    def test_full_payload_returns_list(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert isinstance(result, dict)
        payload = result["full_payload"]
        assert isinstance(payload, list)
        assert len(payload) == 2

    def test_full_payload_item_shape(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        item = result["full_payload"][0]
        assert item["text"] == "Quote one"
        assert item["score"] == 7
        assert item["rating"] == 4.5
        assert item["active"] is True

    def test_full_payload_nested_ref(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        author = result["full_payload"][0]["author"]
        assert isinstance(author, dict)
        assert author["name"] == "Author One"
        assert author["slug"] == "author-one"

    def test_full_payload_array_field(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert result["full_payload"][0]["tags"] == ["alpha", "beta"]

    def test_full_payload_second_item(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        item = result["full_payload"][1]
        assert item["text"] == "Quote two"
        assert item["score"] == 12
        assert item["active"] is False

    def test_path_author_name(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert result["first_author_name"] == "Author One"
        assert isinstance(result["first_author_name"], str)

    def test_path_score(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert result["first_score"] == 7

    def test_path_tags(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert result["first_tags"] == ["alpha", "beta"]

    def test_path_second_text(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic", html
        )
        assert result["second_text"] == "Quote two"


class TestJsonMixed:
    def test_html_title_parsed(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "19_json_mixed.kdl", "JsonMixed", html
        )
        assert result["html_title"] == "DSL Coverage Fixture"

    def test_json_payload_parsed(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "19_json_mixed.kdl", "JsonMixed", html
        )
        assert isinstance(result["json_payload"], list)
        assert len(result["json_payload"]) == 2

    def test_nested_item_parsed(self, html):
        result = _run_schema(
            SCHEMAS_DIR / "19_json_mixed.kdl", "JsonMixed", html
        )
        assert isinstance(result["nested_item"], dict)
        assert result["nested_item"]["title"] == "Single Item Title"
