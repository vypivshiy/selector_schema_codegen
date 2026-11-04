"""JS codegen integration tests via pytest.

Generates JavaScript code via js_pure converter, runs it in Node.js + jsdom,
and validates the parse results. All tests are skipped if Node.js is not found.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from kdlquery import Severity

from ssc_codegen.core import parse_module
from ssc_codegen.naming import to_pascal_case
from ssc_codegen.targets.javascript import JS_CONVERTER

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
            env = os.environ.copy()
            if "NODE_PATH" not in env:
                candidates = [
                    ROOT / "node_modules",
                ]
                try:
                    proc = subprocess.run(
                        ["git", "rev-parse", "--git-common-dir"],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        common_git = Path(proc.stdout.strip())
                        candidates.append(common_git.parent / "node_modules")
                except Exception:
                    pass
                for cand in candidates:
                    if cand.is_dir():
                        env["NODE_PATH"] = str(cand.resolve())
                        break
            self._proc = subprocess.Popen(
                ["node", str(JS_WORKER)],
                cwd=ROOT,
                env=env,
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


# ── Smoke: schemas without dedicated value-check classes below ───────────────

_SMOKES = [
    ("03_filters_and_predicates.kdl", "FiltersAndPredicates"),
    ("05_flat.kdl", "FlatCoverage"),
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
    def test_strings_basic_extraction(self):
        r = _run_js_schema(SCHEMAS_DIR / "01_strings_basic.kdl", "StringsBasic")
        assert isinstance(r, list) and len(r) == 2
        for item in r:
            assert all(
                k in item for k in ("title", "link", "slug", "activeFlag")
            )
            assert isinstance(item["title"], str)
            assert isinstance(item["activeFlag"], bool)
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
    def test_json_basic_extraction(self):
        r = _run_js_schema(SCHEMAS_DIR / "18_json_basic.kdl", "JsonBasic")
        assert isinstance(r["fullPayload"], list)
        assert len(r["fullPayload"]) == 2
        item = r["fullPayload"][0]
        assert item["text"] == "Quote one"
        assert item["score"] == 7
        assert r["firstAuthor"] == {"name": "Author One", "slug": "author-one"}
        assert r["secondAuthor"] == {
            "name": "Author Two",
            "slug": "author-two",
        }


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


def _convert_kdl(src: str) -> str:
    module_ast, diags = parse_module(src)
    assert not [d for d in diags if d.severity == Severity.ERROR]
    return JS_CONVERTER.convert(module_ast)


class TestJsJsonAliasedRemapping:
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


class TestJsJsonDictAndInlineSchemas:
    def test_top_level_dict_json_codegen_and_execution(self):
        kdl_src = """
(dict)json Translations {
    @key str
    @value (array)str
}

(raw)struct TranslationsParser {
    translations {
        jsonify Translations
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert "* @typedef {Record<string, string[]>} TranslationsJson" in code

        raw_payload = json.dumps(
            {
                "1": ["jap", "Мега-Аниме"],
                "10": ["jap", "СВ-Дубль"],
            }
        )
        r = _run_js_src(kdl_src, "TranslationsParser", input_text=raw_payload)
        assert r["translations"] == {
            "1": ["jap", "Мега-Аниме"],
            "10": ["jap", "СВ-Дубль"],
        }

        # Passing non-object throws SscJsonSchemaError
        with pytest.raises(RuntimeError, match="Translations: Expected object"):
            _run_js_src(
                kdl_src, "TranslationsParser", input_text='["invalid", "array"]'
            )

    def test_inline_dict_nullable_and_omitempty(self):
        kdl_src = """
json ConfigResponse {
    id str
    meta (dict)? @omitempty {
        @key str
        @value str
    }
    tags (dict)? {
        @key str
        @value str
    }
}

(raw)struct ConfigParser {
    cfg {
        jsonify ConfigResponse
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert (
            "* @property {Record<string, string>|null} meta (OMITEMPTY)" in code
        )
        assert "* @property {Record<string, string>|null} tags" in code

        # When omitted on wire (meta omitted, tags null)
        r1 = _run_js_src(kdl_src, "ConfigParser", input_text='{"id": "c1"}')
        assert r1["cfg"] == {"id": "c1", "tags": None}
        assert "meta" not in r1["cfg"]

        # When null on wire (meta omitted due to omitempty, tags explicitly null)
        r2 = _run_js_src(
            kdl_src,
            "ConfigParser",
            input_text='{"id": "c1", "meta": null, "tags": null}',
        )
        assert r2["cfg"] == {"id": "c1", "tags": None}
        assert "meta" not in r2["cfg"]

        # When provided on wire
        r3 = _run_js_src(
            kdl_src,
            "ConfigParser",
            input_text='{"id": "c1", "meta": {"env": "prod"}, "tags": {"team": "core"}}',
        )
        assert r3["cfg"] == {
            "id": "c1",
            "meta": {"env": "prod"},
            "tags": {"team": "core"},
        }

    def test_inline_combined_nested_hierarchy(self):
        kdl_src = """
json AnimeResponse {
    id str
    anime_poster str

    franchise Franchise {
        id str
        shikimori_id str from="shiki_id"

        links (array)Links {
            id int
            relation str
        }

        nodes (array)Node {
            id int
            name str
            score float
        }
    }

    material_data {
        anime_title str from="title"
        year int
    }

    self_hosted SelfHosted? from="self_hosted_data" @omitempty {
        available bool
        episodes (array)str
        translations (dict) {
            @key str
            @value (array)str
        }
    }
}

(raw)struct FullAnimeParser {
    data {
        jsonify AnimeResponse
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert "@typedef {Object} FranchiseJson" in code
        assert "@typedef {Object} LinksJson" in code
        assert "@typedef {Object} NodeJson" in code
        assert "@typedef {Object} AnimeResponseMaterialDataJson" in code
        assert "@typedef {Object} SelfHostedJson" in code
        assert "@typedef {Object} AnimeResponseJson" in code
        assert "* @property {FranchiseJson} franchise" in code
        assert "* @property {LinksJson[]} links" in code
        assert "* @property {NodeJson[]} nodes" in code
        assert (
            "* @property {AnimeResponseMaterialDataJson} material_data" in code
        )
        assert (
            "* @property {SelfHostedJson|null} self_hosted (OMITEMPTY)" in code
        )
        assert "* @property {Record<string, string[]>} translations" in code

        raw_payload = json.dumps(
            {
                "id": "anime_full",
                "anime_poster": "https://example.com/poster.jpg",
                "franchise": {
                    "id": "fr_1",
                    "shiki_id": "sh_100",
                    "links": [{"id": 1, "relation": "sequel"}],
                    "nodes": [{"id": 10, "name": "Original", "score": 8.5}],
                },
                "material_data": {
                    "title": "Anime Title",
                    "year": 2024,
                },
                "self_hosted_data": {
                    "available": True,
                    "episodes": ["ep1", "ep2"],
                    "translations": {"1": ["jap", "eng"]},
                },
            }
        )
        r = _run_js_src(kdl_src, "FullAnimeParser", input_text=raw_payload)
        assert r["data"] == {
            "id": "anime_full",
            "anime_poster": "https://example.com/poster.jpg",
            "franchise": {
                "id": "fr_1",
                "shikimori_id": "sh_100",
                "links": [{"id": 1, "relation": "sequel"}],
                "nodes": [{"id": 10, "name": "Original", "score": 8.5}],
            },
            "material_data": {
                "anime_title": "Anime Title",
                "year": 2024,
            },
            "self_hosted": {
                "available": True,
                "episodes": ["ep1", "ep2"],
                "translations": {"1": ["jap", "eng"]},
            },
        }

    def test_top_level_dict_with_inline_value_block_codegen_and_execution(self):
        kdl_src = """
(dict)json Translations {
    @key str
    @value TranslationValue {
        title str from="display_title"
        count int
        notes @skip
    }
}

(raw)struct TranslationsParser {
    translations {
        jsonify Translations
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert "* @typedef {Object} TranslationValueJson" in code
        assert "* @property {string} title" in code
        assert "* @property {number} count" in code
        assert "notes" not in code
        assert (
            "* @typedef {Record<string, TranslationValueJson>} TranslationsJson"
            in code
        )

        raw_payload = json.dumps(
            {
                "rus": {
                    "display_title": "Русский",
                    "count": 12,
                    "notes": "ignore",
                },
                "eng": {"display_title": "English", "count": 24},
            }
        )
        r = _run_js_src(kdl_src, "TranslationsParser", input_text=raw_payload)
        assert r["translations"] == {
            "rus": {"title": "Русский", "count": 12},
            "eng": {"title": "English", "count": 24},
        }

    def test_nested_dict_value_schema_multi_level_codegen_and_execution(self):
        kdl_src = """
json AnimeResponse {
    translations (dict)Translation {
        @key str
        @value TranslationValue {
            episodes (dict)EpisodeMap {
                @key int
                @value EpisodeValue {
                    link str from="stream_url"
                    screenshots @skip
                }
            }
            is_active bool
            kind str from="type"
        }
    }
}

(raw)struct AnimeParser {
    anime {
        jsonify AnimeResponse
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert "* @typedef {Object} EpisodeValueJson" in code
        assert "* @property {string} link" in code
        assert "screenshots" not in code
        assert "* @typedef {Object} TranslationValueJson" in code
        assert "* @property {Record<number, EpisodeValueJson>} episodes" in code
        assert "* @property {boolean} is_active" in code
        assert "* @property {string} kind" in code
        assert "* @typedef {Object} AnimeResponseJson" in code
        assert (
            "* @property {Record<string, TranslationValueJson>} translations"
            in code
        )

        raw_payload = json.dumps(
            {
                "translations": {
                    "sub": {
                        "episodes": {
                            "1": {
                                "stream_url": "https://stream/1",
                                "screenshots": ["s1.jpg"],
                            },
                            "2": {"stream_url": "https://stream/2"},
                        },
                        "is_active": True,
                        "type": "tv",
                    }
                }
            }
        )
        r = _run_js_src(kdl_src, "AnimeParser", input_text=raw_payload)
        assert r["anime"] == {
            "translations": {
                "sub": {
                    "episodes": {
                        "1": {"link": "https://stream/1"},
                        "2": {"link": "https://stream/2"},
                    },
                    "is_active": True,
                    "kind": "tv",
                }
            }
        }

    def test_inline_dict_anonymous_value_block_and_array_value_codegen_and_execution(
        self,
    ):
        kdl_src = """
json Project {
    groups (dict) {
        @key str
        @value (array)GroupItem {
            id int
            name str from="group_name"
        }
    }
    settings (dict) {
        @key str
        @value {
            enabled bool
            priority int? @omitempty
        }
    }
}

(raw)struct ProjectParser {
    proj {
        jsonify Project
    }
}
"""
        code = _convert_kdl(kdl_src)
        assert "* @typedef {Object} GroupItemJson" in code
        assert "* @property {number} id" in code
        assert "* @property {string} name" in code
        assert "* @typedef {Object} ProjectSettingsValueJson" in code
        assert "* @property {boolean} enabled" in code
        assert "* @property {number|null} priority (OMITEMPTY)" in code
        assert "* @property {Record<string, GroupItemJson[]>} groups" in code
        assert (
            "* @property {Record<string, ProjectSettingsValueJson>} settings"
            in code
        )

        raw_payload = json.dumps(
            {
                "groups": {
                    "backend": [
                        {"id": 1, "group_name": "Core"},
                        {"id": 2, "group_name": "Ops"},
                    ]
                },
                "settings": {
                    "notifications": {"enabled": True, "priority": 5},
                    "telemetry": {"enabled": False},
                },
            }
        )
        r = _run_js_src(kdl_src, "ProjectParser", input_text=raw_payload)
        assert r["proj"] == {
            "groups": {
                "backend": [
                    {"id": 1, "name": "Core"},
                    {"id": 2, "name": "Ops"},
                ]
            },
            "settings": {
                "notifications": {"enabled": True, "priority": 5},
                "telemetry": {"enabled": False},
            },
        }


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


class TestJsJsonDescriptorAlignment:
    def test_gjson_path_subset_escaped_dots_hash_len_and_projection(self):
        kdl_src = r"""
json ReleaseManifest {
    os_version str from="os\\.version"
    nested_version str from="meta.os\\.version"
    backslash_key str from="meta.path\\\\dir"
    hash_key str from="meta.\\#"
    item_count int from="items.#"
    opt_count int? from="missing.#"
    tag_names (array)str from="tags.#.name"
    deep_ids (array)int from="groups.#.meta.id"
}

(raw)struct ManifestParser {
    manifest {
        jsonify ReleaseManifest path="envelope\\.data"
    }
}
"""
        payload = json.dumps(
            {
                "envelope.data": {
                    "os.version": "24.04",
                    "meta": {
                        "os.version": "6.8.0-generic",
                        "path\\dir": "C:\\bin",
                        "#": "pound_val",
                    },
                    "items": ["a", "b", "c"],
                    "tags": [
                        {"name": "action", "id": 1},
                        {"name": "sci-fi", "id": 2},
                        {"other": "skipped"},
                    ],
                    "groups": [
                        {"meta": {"id": 10}},
                        {"meta": {"id": 20}},
                    ],
                }
            }
        )
        r = _run_js_src(kdl_src, "ManifestParser", input_text=payload)
        assert r["manifest"] == {
            "os_version": "24.04",
            "nested_version": "6.8.0-generic",
            "backslash_key": "C:\\bin",
            "hash_key": "pound_val",
            "item_count": 3,
            "opt_count": None,
            "tag_names": ["action", "sci-fi"],
            "deep_ids": [10, 20],
        }

        # Non-array on terminal # raises SscJsonPathError with Schema.field context
        bad_payload = json.dumps(
            {
                "envelope.data": {
                    "os.version": "24.04",
                    "meta": {
                        "os.version": "6.8.0-generic",
                        "path\\dir": "C:\\bin",
                        "#": "pound_val",
                    },
                    "items": "not_an_array",
                    "tags": [],
                    "groups": [],
                }
            }
        )
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonPathError: ReleaseManifest\.item_count: Expected list for '#'",
        ):
            _run_js_src(kdl_src, "ManifestParser", input_text=bad_payload)

    def test_schema_error_on_null_or_primitive_and_qualified_field_errors(self):
        kdl_src = """
json user_profile {
    id int
    username str from="user_name"
    city str from="address.city"
    tags (array)str?
    translations (dict)? {
        @key str
        @value (array)str
    }
}

(raw)struct ProfileParser {
    profile {
        jsonify user_profile
    }
}
"""
        # Null root throws SscJsonSchemaError with PascalCase SchemaName
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonSchemaError: UserProfile: Expected object, got null",
        ):
            _run_js_src(kdl_src, "ProfileParser", input_text="null")

        # Primitive root throws SscJsonSchemaError with SchemaName
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonSchemaError: UserProfile: Expected object, got number",
        ):
            _run_js_src(kdl_src, "ProfileParser", input_text="42")

        # Array root when object expected throws SscJsonSchemaError
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonSchemaError: UserProfile: Expected object, got array",
        ):
            _run_js_src(kdl_src, "ProfileParser", input_text="[1, 2]")

        # Missing required direct field includes UserProfile.username
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonFieldMissingError: UserProfile\.username: Required JSON field 'user_name' \(mapped to 'username'\) is missing",
        ):
            _run_js_src(
                kdl_src,
                "ProfileParser",
                input_text='{"id": 1, "address": {"city": "NY"}}',
            )

        # Null non-nullable field includes UserProfile.username
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonFieldMissingError: UserProfile\.username: Field 'user_name' is null, but 'username' is not nullable",
        ):
            _run_js_src(
                kdl_src,
                "ProfileParser",
                input_text='{"id": 1, "user_name": null, "address": {"city": "NY"}}',
            )

        # Missing path segment includes UserProfile.city
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonPathError: UserProfile\.city: Missing key 'city' in path 'address\.city'",
        ):
            _run_js_src(
                kdl_src,
                "ProfileParser",
                input_text='{"id": 1, "user_name": "alice", "address": {}}',
            )

        # Non-array on scalar array field throws SscJsonSchemaError with UserProfile.tags
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonSchemaError: UserProfile\.tags: Expected array, got string",
        ):
            _run_js_src(
                kdl_src,
                "ProfileParser",
                input_text='{"id": 1, "user_name": "alice", "address": {"city": "NY"}, "tags": "not_an_array"}',
            )

        # Non-array value in (dict) with @value (array)str throws SscJsonSchemaError
        with pytest.raises(
            RuntimeError,
            match=r"SscJsonSchemaError: UserProfile\.translations: Expected array, got string",
        ):
            _run_js_src(
                kdl_src,
                "ProfileParser",
                input_text='{"id": 1, "user_name": "alice", "address": {"city": "NY"}, "translations": {"en": "not_an_array"}}',
            )

    def test_nested_projector_call_stack_and_rest_null_body_error(self):
        kdl_src = '''
json Preroll {
    stream_url str from="url"
}

json Vast {
    preroll Preroll
}

json CdnVideoHubResponse {
    vast Vast
}

(rest)struct VideoClient {
    @request name=get-video response=CdnVideoHubResponse """
    GET /video HTTP/1.1
    Host: api.example.com
    """
}
'''
        code = _convert_kdl(kdl_src)
        script = (
            code
            + """
(async () => {
  // 1. Verify nested projector stack frames (_projectCdnVideoHubResponse -> _projectVast -> _projectPreroll)
  let caughtNested = null;
  try {
    _projectCdnVideoHubResponse({ vast: { preroll: {} } });
  } catch (err) {
    caughtNested = err;
  }
  if (!caughtNested || caughtNested.name !== 'SscJsonFieldMissingError') {
    throw new Error('Expected SscJsonFieldMissingError');
  }
  if (!caughtNested.message.includes('Preroll.stream_url')) {
    throw new Error('Missing Preroll.stream_url in message: ' + caughtNested.message);
  }
  const stack = String(caughtNested.stack || '');
  for (const fn of ['_projectPreroll', '_projectVast', '_projectCdnVideoHubResponse']) {
    if (!stack.includes(fn)) {
      throw new Error(`Missing ${fn} in stack:\\n${stack}`);
    }
  }

  // 2. Verify REST 2xx response with null body throws SscJsonSchemaError instead of returning Ok(null)
  const fakeNullClient = async () => ({
    status: 200,
    headers: new Map(),
    json: async () => null,
  });
  let caughtRest = null;
  try {
    await VideoClient.getVideo(fakeNullClient);
  } catch (err) {
    caughtRest = err;
  }
  if (!caughtRest || caughtRest.name !== 'SscJsonSchemaError') {
    throw new Error('Expected SscJsonSchemaError on null 2xx body');
  }
  if (!caughtRest.message.includes('CdnVideoHubResponse')) {
    throw new Error('Missing CdnVideoHubResponse in error: ' + caughtRest.message);
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
        )
        node_eval = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert node_eval.returncode == 0

    def test_js_runtime_http_delegation_null_body_and_opts_merge(self):
        kdl_src = '''
@doc """
    Multi-line JS module doc.
    Line two.
    """

json User {
    id int
    name str
    nickname str?
}

(rest)struct UserClient {
    @doc """
        UserClient REST struct doc.
        Line two.
        """
    @request name=update-user response=User doc="""
        Update user endpoint doc.
        Line two.
        """ """
    POST /users?tag={{tag:str}}&filter={{filter:str?}} HTTP/1.1
    Host: api.example.com
    Content-Type: application/json
    X-App: ssc-js
    X-Trace: {{trace:str?}}

    {"name": "{{name:str}}", "nickname": {{nickname:str?}}}
    """
}
'''
        module, diags = parse_module(kdl_src)
        assert not [d for d in diags if d.severity == Severity.ERROR]

        fetch_code = JS_CONVERTER.convert(module, http_client="fetch")
        axios_code = JS_CONVERTER.convert(module, http_client="axios")

        assert " * Multi-line JS module doc.\n * Line two." in fetch_code
        assert " * UserClient REST struct doc.\n * Line two." in fetch_code
        assert "   * Update user endpoint doc.\n   * Line two." in fetch_code

        fetch_script = (
            fetch_code
            + """
(async () => {
  let capturedUrl = null;
  let capturedOpts = null;
  const mockFetch = async (url, opts) => {
    capturedUrl = url;
    capturedOpts = opts;
    return {
      status: 200,
      headers: new Map(),
      json: async () => ({ id: 1, name: 'Alice', nickname: null }),
    };
  };

  const res = await UserClient.updateUser(
    mockFetch,
    { tag: 'v1', name: 'Alice', nickname: null },
    { headers: { 'X-Custom': 'caller' }, params: { extra: 'yes' } }
  );
  if (!res.isOk || res.value.name !== 'Alice' || res.value.nickname !== null) {
    throw new Error('Unexpected response: ' + JSON.stringify(res));
  }
  if (capturedUrl !== 'https://api.example.com/users?tag=v1&extra=yes') {
    throw new Error('Unexpected URL (filter should be omitted, extra merged): ' + capturedUrl);
  }
  if (capturedOpts.headers['X-App'] !== 'ssc-js' || capturedOpts.headers['X-Custom'] !== 'caller') {
    throw new Error('Headers not shallow-merged: ' + JSON.stringify(capturedOpts.headers));
  }
  if ('X-Trace' in capturedOpts.headers) {
    throw new Error('Optional undefined X-Trace header should be omitted');
  }
  const parsedBody = JSON.parse(capturedOpts.body);
  if (parsedBody.name !== 'Alice' || parsedBody.nickname !== null || !('nickname' in parsedBody)) {
    throw new Error('JSON body did not preserve nickname: null: ' + capturedOpts.body);
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
        )
        res_fetch = subprocess.run(
            ["node", "-e", fetch_script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert res_fetch.returncode == 0

        axios_script = (
            axios_code
            + """
(async () => {
  let capturedCfg = null;
  const mockAxios = {
    request: async (cfg) => {
      capturedCfg = cfg;
      return {
        status: 200,
        headers: {},
        data: { id: 2, name: 'Bob', nickname: null },
      };
    },
  };

  const res = await UserClient.updateUser(
    mockAxios,
    { tag: 'v2', name: 'Bob', nickname: null },
    { headers: { 'X-Custom': 'axios-caller' }, params: { extra: '1' } }
  );
  if (!res.isOk || res.value.name !== 'Bob') {
    throw new Error('Unexpected axios response: ' + JSON.stringify(res));
  }
  if (capturedCfg.params.toString() !== 'tag=v2&extra=1') {
    throw new Error('Unexpected axios params: ' + capturedCfg.params.toString());
  }
  if (capturedCfg.headers['X-App'] !== 'ssc-js' || capturedCfg.headers['X-Custom'] !== 'axios-caller') {
    throw new Error('Axios headers not merged: ' + JSON.stringify(capturedCfg.headers));
  }
  if ('X-Trace' in capturedCfg.headers) {
    throw new Error('Optional X-Trace should be omitted in axios');
  }
  const parsedBody = JSON.parse(capturedCfg.data);
  if (parsedBody.name !== 'Bob' || parsedBody.nickname !== null || !('nickname' in parsedBody)) {
    throw new Error('Axios JSON body did not preserve nickname: null: ' + capturedCfg.data);
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
        )
        res_axios = subprocess.run(
            ["node", "-e", axios_script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert res_axios.returncode == 0

    def test_js_rest_dotpath_keys_and_safe_errmatcher_fallthrough_fetch_and_axios(
        self,
    ):
        kdl_src = '''
json User {
    id int
    name str
}

json ApiError {
    code int from="error.code"
    message str from="error.message"
}

json SpecificError {
    error str
    code int
}

json GenericError {
    message str
}

(rest)struct SearchClient {
    @error 200 ApiError "error.code"
    @error:not-found 404 SpecificError error="Ничего не найдено"
    @error 404 GenericError

    @request name=search response=User """
    GET /search HTTP/1.1
    Host: api.example.com
    """
}
'''
        module, diags = parse_module(kdl_src)
        assert not [d for d in diags if d.severity == Severity.ERROR]

        fetch_code = JS_CONVERTER.convert(module, http_client="fetch")
        axios_code = JS_CONVERTER.convert(module, http_client="axios")

        fetch_script = (
            fetch_code
            + """
(async () => {
  const makeFetch = (status, body, isJson = true) => async () => ({
    status,
    headers: new Map([['content-type', isJson ? 'application/json' : 'text/html']]),
    json: async () => {
      if (!isJson) throw new SyntaxError('Unexpected token < in JSON');
      return body;
    },
  });

  // 1. Nested positional key "error.code" matches {"error": {"code": 123, "message": "bad"}}
  const r1 = await SearchClient.search(
    makeFetch(200, { error: { code: 123, message: 'bad' } })
  );
  if (r1.isOk !== false || r1.status !== 200 || r1.value.code !== 123 || r1.value.message !== 'bad') {
    throw new Error('Expected 200 ApiError match: ' + JSON.stringify(r1));
  }

  // 2. Nested positional key "error.code" rejects {"error": {}} and {} -> Ok
  const r2 = await SearchClient.search(
    makeFetch(200, { id: 1, name: 'Alice', error: {} })
  );
  if (r2.isOk !== true || r2.value.id !== 1 || r2.value.name !== 'Alice') {
    throw new Error('Expected 200 Ok when error.code is missing: ' + JSON.stringify(r2));
  }

  // 3. SpecificError matches on 404 when both condition and schema match
  const r3 = await SearchClient.search(
    makeFetch(404, { error: 'Ничего не найдено', code: 404, extra: 'ignored' })
  );
  if (r3.isOk !== false || r3.status !== 404 || r3.value.error !== 'Ничего не найдено' || r3.value.code !== 404 || 'extra' in r3.value) {
    throw new Error('Expected SpecificError match: ' + JSON.stringify(r3));
  }

  // 4. SpecificError condition matches, but projection throws (missing 'code') -> falls through to GenericError
  const r4 = await SearchClient.search(
    makeFetch(404, { error: 'Ничего не найдено', message: 'Fallback generic', extra: 1 })
  );
  if (r4.isOk !== false || r4.status !== 404 || r4.value.message !== 'Fallback generic' || 'extra' in r4.value) {
    throw new Error('Expected fallthrough to GenericError: ' + JSON.stringify(r4));
  }

  // 5. Empty JSON `{}` fails both 404 matchers -> falls through to UnknownErr without throwing
  const r5 = await SearchClient.search(makeFetch(404, {}));
  if (r5.isOk !== false || r5.status !== 404 || JSON.stringify(r5.value) !== '{}') {
    throw new Error('Expected UnknownErr with {} value: ' + JSON.stringify(r5));
  }

  // 6. HTML 404 response (body is null) -> falls through to UnknownErr without throwing
  const r6 = await SearchClient.search(makeFetch(404, null, false));
  if (r6.isOk !== false || r6.status !== 404 || r6.value !== null) {
    throw new Error('Expected UnknownErr with null value on HTML 404: ' + JSON.stringify(r6));
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
        )
        res_fetch = subprocess.run(
            ["node", "-e", fetch_script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert res_fetch.returncode == 0

        axios_script = (
            axios_code
            + """
(async () => {
  const makeAxios = (status, data) => ({
    request: async () => ({
      status,
      headers: { 'content-type': 'application/json' },
      data,
    }),
  });

  // 1. Nested positional key "error.code" matches
  const r1 = await SearchClient.search(
    makeAxios(200, { error: { code: 321, message: 'axios err' } })
  );
  if (r1.isOk !== false || r1.status !== 200 || r1.value.code !== 321) {
    throw new Error('Axios expected 200 ApiError match: ' + JSON.stringify(r1));
  }

  // 2. SpecificError condition matches, projection fails -> falls through to GenericError
  const r2 = await SearchClient.search(
    makeAxios(404, { error: 'Ничего не найдено', message: 'Axios generic fallback' })
  );
  if (r2.isOk !== false || r2.status !== 404 || r2.value.message !== 'Axios generic fallback') {
    throw new Error('Axios expected fallthrough to GenericError: ' + JSON.stringify(r2));
  }

  // 3. Schema-mismatching JSON `{}` -> falls through to UnknownErr
  const r3 = await SearchClient.search(makeAxios(404, {}));
  if (r3.isOk !== false || r3.status !== 404 || JSON.stringify(r3.value) !== '{}') {
    throw new Error('Axios expected UnknownErr on {}: ' + JSON.stringify(r3));
  }

  // 4. Non-JSON HTML string or null data in axios -> falls through to UnknownErr
  const r4 = await SearchClient.search(makeAxios(404, '<html>404 Not Found</html>'));
  if (r4.isOk !== false || r4.status !== 404 || r4.value !== '<html>404 Not Found</html>') {
    throw new Error('Axios expected UnknownErr on HTML string: ' + JSON.stringify(r4));
  }
  const r5 = await SearchClient.search(makeAxios(404, null));
  if (r5.isOk !== false || r5.status !== 404 || r5.value !== null) {
    throw new Error('Axios expected UnknownErr on null: ' + JSON.stringify(r5));
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
        )
        res_axios = subprocess.run(
            ["node", "-e", axios_script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert res_axios.returncode == 0
