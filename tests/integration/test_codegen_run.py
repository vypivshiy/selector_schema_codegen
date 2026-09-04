"""Integration tests: generate Python code from KDL schemas, exec, and verify parse results.

Each test case: KDL schema + struct name → generate code for each py-* target → exec → parse HTML → assert output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ssc_codegen.core import parse_module
from kdlquery import Severity
from ssc_codegen.naming import to_pascal_case

SCHEMAS_DIR = Path(__file__).parent / "schemas"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
HTML_FIXTURE = FIXTURES_DIR / "dsl_coverage.html"

# Python targets and their converter imports
_PY_TARGETS = {
    "py-bs4": "ssc_codegen.targets.python:PY_BS4_CONVERTER",
    "py-lxml": "ssc_codegen.targets.python:PY_LXML_CONVERTER",
    "py-parsel": "ssc_codegen.targets.python:PY_PARSEL_CONVERTER",
    "py-slax": "ssc_codegen.targets.python:PY_SLAX_CONVERTER",
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

    @pytest.mark.parametrize("target", _TARGETS)
    def test_raw_inner_excludes_own_tag(self, html, target):
        result = _run_schema(
            SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic", html, target
        )
        for item in result:
            inner = item["inner_html"]
            outer = item["clean_html"]
            assert isinstance(inner, str)
            assert not inner.lstrip().startswith("<article")
            assert '<h2 class="title">' in inner
            # inner is a strict substring-ish shrink: shorter than outer
            assert len(inner) < len(outer)


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


class TestJsonAliasedRemapping:
    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_remapping_execution(self, html, target):
        kdl_src = """
json AuthorSchema {
    author_name str from="name"
    author_slug str from="slug"
}

(array)json QuoteSchema {
    quote_text str from="text"
    author AuthorSchema
    quote_score int from="score"
}

struct JsonAliasedScraper {
    @init {
        raw-json {
            css "script#test-data"
            text
            re #"(\\[.*\\])"#
        }
    }

    quotes {
        @raw-json
        jsonify QuoteSchema
    }

    first-author-name {
        @raw-json
        jsonify QuoteSchema path="0.author.name"
    }
}
"""
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["JsonAliasedScraper"]
        res = cls(html).parse()
        assert isinstance(res["quotes"], list)
        assert len(res["quotes"]) == 2
        first = res["quotes"][0]
        assert first["quote_text"] == "Quote one"
        assert first["quote_score"] == 7
        assert first["author"]["author_name"] == "Author One"
        assert first["author"]["author_slug"] == "author-one"
        assert "text" not in first
        assert "score" not in first
        assert "name" not in first["author"]
        assert res["first_author_name"] == "Author One"

    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_special_character_keys(self, target):
        kdl_src = """
json SpecialKeysSchema {
    context str from="@context"
    doc_type str from="@type"
    doc_id str from="@id"
    data_version str from="data-version"
    creator str from="dc:creator"
    rating_val float from="rating:score"
}

struct SpecialKeysScraper {
    @init {
        raw-json {
            css "script#jsonld"
            text
        }
    }

    item {
        @raw-json
        jsonify SpecialKeysSchema
    }
}
"""
        custom_html = """
        <html>
        <head>
            <script id="jsonld" type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Book",
                "@id": "urn:isbn:12345",
                "data-version": "1.4.2",
                "dc:creator": "Arthur Conan Doyle",
                "rating:score": 4.95,
                "unmapped_extra": "drop me"
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["SpecialKeysScraper"]
        res = cls(custom_html).parse()
        item = res["item"]
        assert item == {
            "context": "https://schema.org",
            "doc_type": "Book",
            "doc_id": "urn:isbn:12345",
            "data_version": "1.4.2",
            "creator": "Arthur Conan Doyle",
            "rating_val": 4.95,
        }
        assert "@context" not in item
        assert "unmapped_extra" not in item

    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_deep_nested_and_arrays(self, target):
        kdl_src = """
json SpecDetail {
    spec_key str from="k"
    spec_value str from="v"
}

json ProductItem {
    product_name str from="name"
    specs (array)SpecDetail from="spec_list"
}

json CategoryGroup {
    category_id int from="cat_id"
    products (array)ProductItem from="product_items"
}

(array)json CatalogPayload {
    catalog_name str from="name"
    categories (array)CategoryGroup from="cat_groups"
}

struct DeepCatalogScraper {
    catalog {
        css "script#catalog-data"
        text
        jsonify CatalogPayload
    }
}
"""
        custom_html = """
        <html>
        <body>
            <script id="catalog-data" type="application/json">
            [
                {
                    "name": "Electronics",
                    "cat_groups": [
                        {
                            "cat_id": 101,
                            "product_items": [
                                {
                                    "name": "Smartphone",
                                    "spec_list": [
                                        {"k": "RAM", "v": "16GB"},
                                        {"k": "Storage", "v": "512GB"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
            </script>
        </body>
        </html>
        """
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["DeepCatalogScraper"]
        res = cls(custom_html).parse()
        catalog = res["catalog"]
        assert isinstance(catalog, list)
        assert len(catalog) == 1
        cat0 = catalog[0]
        assert cat0["catalog_name"] == "Electronics"
        group0 = cat0["categories"][0]
        assert group0["category_id"] == 101
        prod0 = group0["products"][0]
        assert prod0["product_name"] == "Smartphone"
        specs = prod0["specs"]
        assert specs == [
            {"spec_key": "RAM", "spec_value": "16GB"},
            {"spec_key": "Storage", "spec_value": "512GB"},
        ]

    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_missing_keys_nulls_and_extra_fields(self, target):
        kdl_src = """
json UserState {
    account_id int from="id"
    nickname str from="user_name"
    avatar_url str? from="avatar"
    bio_text str? from="bio"
}

struct UserStateScraper {
    user {
        css "script#user-data"
        text
        jsonify UserState
    }
}
"""
        custom_html = """
        <html>
        <body>
            <script id="user-data" type="application/json">
            {
                "id": 999,
                "user_name": "bob",
                "avatar": null,
                "extra_key_one": 123,
                "extra_key_two": {"foo": "bar"}
            }
            </script>
        </body>
        </html>
        """
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["UserStateScraper"]
        res = cls(custom_html).parse()
        user = res["user"]
        assert user["account_id"] == 999
        assert user["nickname"] == "bob"
        assert user["avatar_url"] is None
        assert user["bio_text"] is None
        assert "extra_key_one" not in user
        assert "extra_key_two" not in user

    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_define_expansion(self, target):
        kdl_src = """
define COMMON-FIELDS {
    ident int from="id"
    is_active bool from="active"
}

json ExtendedUser {
    COMMON-FIELDS
    display_name str from="title"
}

struct DefineScraper {
    profile {
        css "script#profile"
        text
        jsonify ExtendedUser
    }
}
"""
        custom_html = """
        <html>
        <body>
            <script id="profile" type="application/json">
            {"id": 42, "active": true, "title": "Admin Alice"}
            </script>
        </body>
        </html>
        """
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["DefineScraper"]
        res = cls(custom_html).parse()
        assert res["profile"] == {
            "ident": 42,
            "is_active": True,
            "display_name": "Admin Alice",
        }

    @pytest.mark.parametrize("target", _TARGETS)
    def test_json_alias_raw_struct_execution(self, target):
        kdl_src = """
json ConfigPayload {
    host_addr str from="host"
    port_num int from="port"
    ssl_enabled bool from="tls"
}

(raw)struct RawConfigParser {
    config {
        jsonify ConfigPayload
    }
}
"""
        raw_json_str = '{"host": "db.internal.net", "port": 5432, "tls": true, "secret": "pwd"}'
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        converter = _get_converter(target)
        code = converter.convert(module_ast)
        namespace: dict = {}
        exec(code, namespace)
        cls = namespace["RawConfigParser"]
        res = cls(raw_json_str).parse()
        assert res["config"] == {
            "host_addr": "db.internal.net",
            "port_num": 5432,
            "ssl_enabled": True,
        }

    def test_json_alias_separate_runtime_execution(self, html):
        import sys
        import types
        from ssc_codegen.generation.runtime import runtime_module_content

        kdl_src = """
json UserInfo {
    user_id int @omitempty from="id"
    user_name str from="name"
}

struct RuntimeTestScraper {
    @init {
        raw-data {
            css "script#test-data"
            text
            re #"(\\[.*\\])"#
        }
    }

    first-user {
        @raw-data
        jsonify UserInfo path="0.author"
    }
}
"""
        module_ast, diagnostics = parse_module(kdl_src)
        assert not [d for d in diagnostics if d.severity == Severity.ERROR]
        runtime_src = runtime_module_content(module_ast)

        pkg_name = "test_pkg_runtime"
        runtime_name = "sscgen_runtime"
        pkg_mod = types.ModuleType(pkg_name)
        runtime_mod = types.ModuleType(f"{pkg_name}.{runtime_name}")
        exec(runtime_src, runtime_mod.__dict__)

        sys.modules[pkg_name] = pkg_mod
        sys.modules[f"{pkg_name}.{runtime_name}"] = runtime_mod
        setattr(pkg_mod, runtime_name, runtime_mod)

        try:
            converter = _get_converter("py-bs4")
            code = converter.convert(
                module_ast,
                package=pkg_name,
                runtime_module=runtime_name,
            )
            assert f"from .{runtime_name} import" in code
            assert "ssc_json_project" in code
            assert "def ssc_json_project(" not in code

            ns: dict = {
                "__name__": f"{pkg_name}.parser",
                "__package__": pkg_name,
            }
            exec(code, ns)
            cls = ns["RuntimeTestScraper"]
            res = cls(html).parse()
            assert res["first_user"] == {"user_name": "Author One"}
        finally:
            sys.modules.pop(f"{pkg_name}.{runtime_name}", None)
            sys.modules.pop(pkg_name, None)

    @pytest.mark.parametrize("target", _TARGETS)
    def test_schema_32_json_aliased_remapping(self, target):
        custom_html = """
        <html><body>
        <script id="test-data" type="application/json">[{"@id": 100, "@context": "https://example.com/ctx", "@type": "Product", "data-version": "2.0", "author": {"dc:creator": "John Doe", "slug": "johndoe", "location": {"lat": 51.5, "lng": -0.12}}, "rating_scores": [5, 4, 5]}]</script>
        </body></html>
        """
        res = _run_schema(
            SCHEMAS_DIR / "32_json_aliased_remapping.kdl",
            "JsonAliasedHtmlScraper",
            custom_html,
            target,
        )
        assert isinstance(res["items"], list)
        item0 = res["items"][0]
        assert item0["item_id"] == 100
        assert item0["item_context"] == "https://example.com/ctx"
        assert item0["item_type"] == "Product"
        assert item0["data_version"] == "2.0"
        assert item0["author"]["author_name"] == "John Doe"
        assert item0["author"]["author_slug"] == "johndoe"
        assert item0["author"]["location"] == {
            "latitude": 51.5,
            "longitude": -0.12,
        }
        assert item0["scores"] == [5, 4, 5]


# ── RAW struct tests ──────────────────────────────────────────────────────────

_JS_TEXT = '<script>var player = new Playerjs({id:"player",file:"/v/list/abc.txt"});</script>'
_URL_TEXT = "https://ru.yummyani.me/iframeCVH.html?dubbing_code=Sanae&anime_id=339&episode=1"
_PLAYLIST_TEXT = "[480p]/v/anime/01_480p.m3u8\n[720p]/v/anime/01_720p.m3u8\n[1080p]/v/anime/01_1080p.m3u8"
_PLAIN_TEXT = "hello world"


class TestRawStructItem:
    """RAW struct ITEM mode: plain-text regex extraction."""

    @pytest.mark.parametrize("target", _TARGETS)
    def test_player_script_extraction(self, target):
        result = _run_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawPlayerScript",
            _JS_TEXT,
            target,
        )
        assert result["playlist_url"] == "/v/list/abc.txt"
        assert result["player_id"] == "player"

    @pytest.mark.parametrize("target", _TARGETS)
    def test_url_params_extraction(self, target):
        result = _run_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawUrlParams",
            _URL_TEXT,
            target,
        )
        assert result["dubbing_code"] == "Sanae"
        assert result["anime_id"] == 339

    @pytest.mark.parametrize("target", _TARGETS)
    def test_text_transform(self, target):
        result = _run_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawTextTransform",
            _PLAIN_TEXT,
            target,
        )
        assert result["upper_text"] == "HELLO WORLD"
        assert result["length"] == 11
        assert result["first_word"] == "hello"


class TestRawStructList:
    """RAW struct LIST mode: split-doc into items."""

    @pytest.mark.parametrize("target", _TARGETS)
    def test_line_items(self, target):
        result = _run_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawLineItems",
            _PLAYLIST_TEXT,
            target,
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["quality"] == "480p"
        assert result[0]["url"] == "/v/anime/01_480p.m3u8"
        assert result[2]["quality"] == "1080p"


# ── fn directive tests ────────────────────────────────────────────────────────


def _run_fn(
    schema_path: str | Path,
    fn_name: str,
    input_text: str,
    target: str = "py-bs4",
):
    """Parse KDL, generate code, exec, call fn(input_text), return result."""
    p = Path(schema_path)
    module_ast = _parse_kdl(p)
    from ssc_codegen.naming import to_snake_case

    snake_name = to_snake_case(fn_name)
    converter = _get_converter(target)
    code = converter.convert(module_ast)
    namespace: dict = {}
    exec(code, namespace)  # noqa: S102
    fn = namespace[snake_name]
    return fn(input_text)


_FN_HTML = "<html><body><h1>Hello World</h1><a href='/a'>A</a><a href='/b'>B</a></body></html>"
_FN_RAW = "first line\nsecond line\nthird line"
_FN_VERSION = "app version=1.2.3 released"


class TestFnHtml:
    """fn directive: HTML document single-value extraction."""

    @pytest.mark.parametrize("target", _TARGETS)
    def test_page_title(self, target):
        result = _run_fn(
            SCHEMAS_DIR / "25_fn.kdl",
            "page_title",
            _FN_HTML,
            target,
        )
        assert result == "Hello World"

    @pytest.mark.parametrize("target", _TARGETS)
    def test_all_links(self, target):
        result = _run_fn(
            SCHEMAS_DIR / "25_fn.kdl",
            "all_links",
            _FN_HTML,
            target,
        )
        assert result == ["/a", "/b"]


class TestFnRaw:
    """(raw)fn directive: plain-text single-value extraction."""

    @pytest.mark.parametrize("target", _TARGETS)
    def test_first_line(self, target):
        result = _run_fn(
            SCHEMAS_DIR / "25_fn.kdl",
            "first_line",
            _FN_RAW,
            target,
        )
        assert result == "first line"

    @pytest.mark.parametrize("target", _TARGETS)
    def test_extract_version(self, target):
        result = _run_fn(
            SCHEMAS_DIR / "25_fn.kdl",
            "extract_version",
            _FN_VERSION,
            target,
        )
        assert result == "1.2.3"
