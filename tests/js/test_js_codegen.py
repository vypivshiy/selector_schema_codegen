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
JS_WORKER = Path(__file__).resolve().parent / "js_worker.cjs"

pytestmark = [
    pytest.mark.skipif(
        shutil.which("node") is None,
        reason="Node.js not found in PATH",
    ),
    pytest.mark.toolchain,
]


class _JsWorkerSession:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._req_id = 0

    def _ensure_proc(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                ["node", str(JS_WORKER)],
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )

    def execute(self, code: str, class_name: str, html: str) -> dict | list:
        self._ensure_proc()
        self._req_id += 1
        payload = json.dumps(
            {
                "id": self._req_id,
                "code": code,
                "className": class_name,
                "html": html,
            }
        )
        assert self._proc and self._proc.stdin and self._proc.stdout
        try:
            self._proc.stdin.write(payload + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
        except (BrokenPipeError, OSError):
            self._proc = None
            raise RuntimeError("JS worker process crashed or disconnected")

        if not line:
            stderr = self._proc.stderr.read() if self._proc.stderr else ""
            self._proc = None
            raise RuntimeError(f"JS worker exited unexpectedly: {stderr}")

        res = json.loads(line)
        if not res.get("ok"):
            raise RuntimeError(res.get("error", "Unknown JS execution error"))
        return res["result"]

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None


_WORKER = _JsWorkerSession()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_js_worker():
    yield
    _WORKER.close()


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


def _run_js_schema(
    schema_path: Path, struct_name: str, input_text: str | None = None
) -> dict | list:
    module_ast = _parse_kdl(schema_path)
    class_name = to_pascal_case(struct_name)
    code = JS_CONVERTER.convert(module_ast)
    html = (
        input_text
        if input_text is not None
        else HTML_FIXTURE.read_text(encoding="utf-8")
    )
    return _WORKER.execute(code, class_name, html)


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

    def test_raw_inner_excludes_own_tag(self):
        r = _run_js_schema(SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic")
        for item in r:
            inner = item["innerHtml"]
            outer = item["cleanHtml"]
            assert isinstance(inner, str)
            assert not inner.startswith("<article")
            assert "foo Title" in inner
            assert len(inner) < len(outer)


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


def _run_js_src(
    src: str,
    struct_name: str,
    input_file: Path = HTML_FIXTURE,
    input_text: str | None = None,
) -> dict | list:
    module_ast, diags = parse_module(src)
    assert not [d for d in diags if d.severity == Severity.ERROR]
    class_name = to_pascal_case(struct_name)
    code = JS_CONVERTER.convert(module_ast)
    if input_text is not None:
        html = input_text
    else:
        html = input_file.read_text(encoding="utf-8")
    return _WORKER.execute(code, class_name, html)


class TestJsJsonAliasedRemapping:
    def test_json_alias_remapping(self):
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
        r = _run_js_src(kdl_src, "JsonAliasedScraper")
        assert isinstance(r["quotes"], list)
        assert len(r["quotes"]) == 2
        first = r["quotes"][0]
        assert first["quote_text"] == "Quote one"
        assert first["quote_score"] == 7
        assert first["author"]["author_name"] == "Author One"
        assert first["author"]["author_slug"] == "author-one"
        assert "text" not in first
        assert "score" not in first
        assert "name" not in first["author"]
        assert r["firstAuthorName"] == "Author One"

    def test_json_alias_special_characters(self):
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
        r = _run_js_src(kdl_src, "SpecialKeysScraper", input_text=custom_html)
        item = r["item"]
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

    def test_json_alias_deep_nested_and_arrays(self):
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
        r = _run_js_src(kdl_src, "DeepCatalogScraper", input_text=custom_html)
        catalog = r["catalog"]
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

    def test_json_alias_missing_keys_nulls_and_extra_fields(self):
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
        r = _run_js_src(kdl_src, "UserStateScraper", input_text=custom_html)
        user = r["user"]
        assert user["account_id"] == 999
        assert user["nickname"] == "bob"
        assert user["avatar_url"] is None
        assert user["bio_text"] is None
        assert "extra_key_one" not in user
        assert "extra_key_two" not in user

    def test_json_alias_define_expansion(self):
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
        r = _run_js_src(kdl_src, "DefineScraper", input_text=custom_html)
        assert r["profile"] == {
            "ident": 42,
            "is_active": True,
            "display_name": "Admin Alice",
        }

    def test_json_alias_raw_struct(self):
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
        r = _run_js_src(kdl_src, "RawConfigParser", input_text=raw_json_str)
        assert r["config"] == {
            "host_addr": "db.internal.net",
            "port_num": 5432,
            "ssl_enabled": True,
        }

    def test_schema_32_json_aliased_remapping(self):
        custom_html = """
        <html><body>
        <script id="test-data" type="application/json">[{"@id": 100, "@context": "https://example.com/ctx", "@type": "Product", "data-version": "2.0", "author": {"dc:creator": "John Doe", "slug": "johndoe", "location": {"lat": 51.5, "lng": -0.12}}, "rating_scores": [5, 4, 5]}]</script>
        </body></html>
        """
        r = _run_js_schema(
            SCHEMAS_DIR / "32_json_aliased_remapping.kdl",
            "JsonAliasedHtmlScraper",
            input_text=custom_html,
        )
        assert isinstance(r["items"], list)
        item0 = r["items"][0]
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

    def test_json_dot_path_and_omitempty_projection(self):
        kdl_src = """
json DotProfile {
    user_id str from="meta.user_id"
    avatar_url str? from="profile.avatar.url"
    top_badge str? from="badges.0.icon"
    legacy_id int @omitempty from="meta.legacy.id"
}

(raw)struct DotParser {
    user {
        jsonify DotProfile
    }
}
"""
        raw_json_str = """{
            "meta": {"user_id": "u42"},
            "profile": {"avatar": {"url": "https://example.com/icon.png", "width": 64}},
            "badges": [{"icon": "shield", "level": 1}],
            "extra_key": "drop_me"
        }"""
        r = _run_js_src(kdl_src, "DotParser", input_text=raw_json_str)
        assert r["user"] == {
            "user_id": "u42",
            "avatar_url": "https://example.com/icon.png",
            "top_badge": "shield",
        }
        assert "legacy_id" not in r["user"]
        assert "extra_key" not in r["user"]


# ── RAW struct ────────────────────────────────────────────────────────────────

_JS_TEXT = '<script>var player = new Playerjs({id:"player",file:"/v/list/abc.txt"});</script>'
_URL_TEXT = "https://ru.yummyani.me/iframeCVH.html?dubbing_code=Sanae&anime_id=339&episode=1"
_PLAYLIST_TEXT = "[480p]/v/anime/01_480p.m3u8\n[720p]/v/anime/01_720p.m3u8\n[1080p]/v/anime/01_1080p.m3u8"
_PLAIN_TEXT = "hello world"


class TestJsRawStructItem:
    def test_player_script_extraction(self):
        r = _run_js_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawPlayerScript",
            input_text=_JS_TEXT,
        )
        assert r["playlistUrl"] == "/v/list/abc.txt"
        assert r["playerId"] == "player"

    def test_url_params_extraction(self):
        r = _run_js_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawUrlParams",
            input_text=_URL_TEXT,
        )
        assert r["dubbingCode"] == "Sanae"
        assert r["animeId"] == 339

    def test_text_transform(self):
        r = _run_js_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawTextTransform",
            input_text=_PLAIN_TEXT,
        )
        assert r["upperText"] == "HELLO WORLD"
        assert r["length"] == 11
        assert r["firstWord"] == "hello"


class TestJsRawStructList:
    def test_line_items(self):
        r = _run_js_schema(
            SCHEMAS_DIR / "23_raw_struct.kdl",
            "RawLineItems",
            input_text=_PLAYLIST_TEXT,
        )
        assert isinstance(r, list)
        assert len(r) == 3
        assert r[0]["quality"] == "480p"
        assert r[0]["url"] == "/v/anime/01_480p.m3u8"
        assert r[2]["quality"] == "1080p"
