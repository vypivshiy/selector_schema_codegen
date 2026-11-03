"""Tests for the Web Playground worker bridge (`ssc_codegen.playground_bridge`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ssc_codegen.core.format import diagnostic_to_dict
from ssc_codegen.core.reader import parse_module
from ssc_codegen.playground_bridge import compile_and_lint, test_html

PRESETS_JSON_PATH = (
    Path(__file__).resolve().parent.parent
    / "playground"
    / "src"
    / "presets.json"
)


def _load_playground_presets() -> list[dict[str, Any]]:
    return json.loads(PRESETS_JSON_PATH.read_text(encoding="utf-8"))


SAMPLE_QUOTES_HTML = """\
<div class="catalogue">
  <div class="quote">
    <span class="text">Simplicity is prerequisite for reliability.</span>
    <span class="author">Edsger W. Dijkstra</span>
    <div class="tags">
      <a class="tag">cs</a>
      <a class="tag">reliability</a>
    </div>
  </div>
  <div class="quote">
    <span class="text">Programs must be written for people to read.</span>
    <span class="author">Harold Abelson</span>
    <div class="tags">
      <a class="tag">programming</a>
    </div>
  </div>
</div>
"""

HTML_SCHEMA = """\
(item)struct QuoteItem {
    author { css ".author"; text }
    tags { css-all ".tag"; text }
}

(list)struct QuoteCatalogue {
    @split-doc { css-all ".quote" }
    text { css ".text"; text }
    details { nested QuoteItem }
}
"""

ALL_STRUCT_TYPES_SCHEMA = """\
(item)struct ItemModel {
    title { css "h1"; text }
}

(list)struct ListModel {
    @split-doc { css-all "li" }
    label { css "span"; text }
}

(table)struct TableModel {
    @table { css "table.specs" }
    @rows { css-all "tr" }
    @match { css "th"; text }
    @value { css "td"; text }
    brand { match { eq "Brand" } }
}

(dict)struct DictModel {
    @split-doc { css-all "dl > div" }
    @key { css "dt"; text }
    @value { css "dd"; text }
}

(flat)struct FlatModel {
    links { css-all "a"; attr "href" }
}

(raw)struct RawModel {
    version { re #"v([0-9]+\\.[0-9]+)"# }
}
"""

REST_SCHEMA = """\
json ApiError {
    code int
    message str
}

(dict)json TagMap {
    @key str
    @value int
}

json UserProfile {
    id int
    username str from="user.name"
    tags TagMap?
}

(rest)struct UserApi {
    @request "curl https://api.example.com/users/{{user_id:int}}" response=UserProfile
    @error 404 ApiError
}
"""


class TestCompileAndLintSchemas:
    """Verify `compile_and_lint` across HTML, Raw, and REST schemas."""

    def test_html_schema_valid_and_json_serializable(self) -> None:
        result = compile_and_lint(HTML_SCHEMA, {"lang": "python", "lib": "bs4"})
        assert result["ok"] is True
        assert result["target_error"] is None
        assert result["diagnostics"] == []
        assert result["structs"] == [
            {"name": "QuoteItem", "type": "item", "is_rest": False},
            {"name": "QuoteCatalogue", "type": "list", "is_rest": False},
        ]
        assert "parser.py" in result["files"]
        assert "class QuoteCatalogue:" in result["files"]["parser.py"]
        # Ensure full contract is JSON-serializable for WebWorker postMessage
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_enumerates_all_struct_types(self) -> None:
        result = compile_and_lint(ALL_STRUCT_TYPES_SCHEMA)
        assert result["ok"] is True
        assert result["structs"] == [
            {"name": "ItemModel", "type": "item", "is_rest": False},
            {"name": "ListModel", "type": "list", "is_rest": False},
            {"name": "TableModel", "type": "table", "is_rest": False},
            {"name": "DictModel", "type": "dict", "is_rest": False},
            {"name": "FlatModel", "type": "flat", "is_rest": False},
            {"name": "RawModel", "type": "raw", "is_rest": False},
        ]

    def test_rest_schema_valid(self) -> None:
        result = compile_and_lint(
            REST_SCHEMA,
            {"lang": "python", "http_client": "httpx", "http_io": "both"},
        )
        assert result["ok"] is True
        assert result["target_error"] is None
        assert result["diagnostics"] == []
        assert result["structs"] == [
            {"name": "UserApi", "type": "rest", "is_rest": True},
        ]
        assert "parser.py" in result["files"]
        assert "class UserApi:" in result["files"]["parser.py"]


class TestCompileAndLintDiagnosticsAndImports:
    """Verify diagnostic spans and single-buffer `imports` / `import` warnings."""

    def test_lint_error_matches_diagnostic_to_dict_1_based_spans(self) -> None:
        bad_kdl = """\
(item)struct Broken {
    price {
        css ".price"
        to-int
        text
    }
}
"""
        _, raw_diags = parse_module(bad_kdl, targets=("python",))
        expected = [diagnostic_to_dict(d) for d in raw_diags]

        result = compile_and_lint(bad_kdl, {"lang": "python"})
        assert result["ok"] is False
        assert result["files"] == {}
        assert len(result["diagnostics"]) == len(expected)
        for actual_diag, expected_diag in zip(
            result["diagnostics"], expected, strict=True
        ):
            assert actual_diag["code"] == expected_diag["code"]
            assert actual_diag["severity"] == "error"
            assert actual_diag["message"] == expected_diag["message"]
            assert actual_diag["hint"] == expected_diag["hint"]
            assert actual_diag["span"] == expected_diag["span"]
            assert actual_diag["span"]["start"]["line"] == 4
            assert actual_diag["span"]["start"]["column"] >= 1

    def test_syntax_error_emits_1_based_diagnostic(self) -> None:
        syntax_err_kdl = '(item)struct Unclosed {\n    title { css "h1"\n'
        result = compile_and_lint(syntax_err_kdl)
        assert result["ok"] is False
        assert result["files"] == {}
        assert len(result["diagnostics"]) == 1
        diag = result["diagnostics"][0]
        assert diag["code"] == "E000"
        assert diag["severity"] == "error"
        assert diag["span"]["start"]["line"] >= 1
        assert diag["span"]["start"]["column"] >= 1

    @pytest.mark.parametrize(
        "import_decl",
        [
            'imports "./shared.kdl"',
            'imports {\n    "./shared.kdl"\n}',
            'import "./shared.kdl" { (struct)Shared }',
        ],
    )
    def test_imports_declaration_emits_non_fatal_warning(
        self, import_decl: str
    ) -> None:
        schema = f"""\
{import_decl}

(item)struct Article {{
    title {{ css "h1"; text }}
}}
"""
        result = compile_and_lint(schema, {"lang": "python"})
        assert result["ok"] is True
        assert "parser.py" in result["files"]
        assert "class Article:" in result["files"]["parser.py"]
        warnings = [
            d for d in result["diagnostics"] if d["severity"] == "warning"
        ]
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning["code"] == "W003"
        assert "single-buffer" in warning["message"]
        assert warning["hint"]
        assert warning["span"]["start"]["line"] == 1
        assert warning["span"]["start"]["column"] == 1

    def test_imports_masking_preserves_subsequent_error_line_numbers(
        self,
    ) -> None:
        schema = """\
imports {
    "./shared.kdl"
}
(item)struct Article {
    title { css "h1"; to-int }
}
"""
        result = compile_and_lint(schema, {"lang": "python"})
        assert result["ok"] is False
        codes = [d["code"] for d in result["diagnostics"]]
        assert "W003" in codes
        err = next(d for d in result["diagnostics"] if d["severity"] == "error")
        assert err["span"]["start"]["line"] == 5


class TestCompileAndLintTargets:
    """Verify multi-target codegen across Python, JavaScript, Go, and Rust."""

    @pytest.mark.parametrize("lib", ["bs4", "lxml", "parsel", "slax"])
    def test_python_html_backends(self, lib: str) -> None:
        result = compile_and_lint(HTML_SCHEMA, {"lang": "python", "lib": lib})
        assert result["ok"] is True
        assert list(result["files"].keys()) == ["parser.py"]
        assert len(result["files"]["parser.py"]) > 0

    @pytest.mark.parametrize("bs4_parser", ["lxml", "html.parser", "html5lib"])
    def test_python_bs4_parser_engines(self, bs4_parser: str) -> None:
        result = compile_and_lint(
            HTML_SCHEMA,
            {"lang": "python", "lib": "bs4", "bs4_parser": bs4_parser},
        )
        assert result["ok"] is True
        assert (
            f'BS4_FEATURES: Literal["html.parser", "lxml", "html5lib"] = \'{bs4_parser}\''
            in result["files"]["parser.py"]
        )

    @pytest.mark.parametrize(
        ("http_client", "http_io"),
        [
            ("httpx", "both"),
            ("httpx2", "sync"),
            ("aiohttp", "async"),
            ("requests", "sync"),
        ],
    )
    def test_python_http_clients_and_io_modes(
        self, http_client: str, http_io: str
    ) -> None:
        result = compile_and_lint(
            REST_SCHEMA,
            {
                "lang": "python",
                "http_client": http_client,
                "http_io": http_io,
            },
        )
        assert result["ok"] is True
        assert "parser.py" in result["files"]

    def test_python_separate_runtime_emits_two_files(self) -> None:
        result = compile_and_lint(
            REST_SCHEMA,
            {
                "lang": "python",
                "lib": "bs4",
                "http_client": "httpx",
                "separate_runtime": True,
            },
        )
        assert result["ok"] is True
        assert set(result["files"].keys()) == {
            "parser.py",
            "sscgen_runtime.py",
        }
        assert "from .sscgen_runtime import" in result["files"]["parser.py"]
        assert "def ssc_expect_dict" in result["files"]["sscgen_runtime.py"]

    @pytest.mark.parametrize("http_client", ["fetch", "axios"])
    def test_javascript_target_and_http_clients(self, http_client: str) -> None:
        result = compile_and_lint(
            REST_SCHEMA,
            {"lang": "js", "http_client": http_client},
        )
        assert result["ok"] is True
        assert list(result["files"].keys()) == ["parser.js"]
        assert "class UserApi {" in result["files"]["parser.js"]

    def test_go_target_emits_parser_and_runtime(self) -> None:
        result = compile_and_lint(REST_SCHEMA, {"lang": "go"})
        assert result["ok"] is True
        assert set(result["files"].keys()) == {
            "parser.go",
            "sscgen_runtime.go",
        }
        assert "package main" in result["files"]["parser.go"]
        assert "package main" in result["files"]["sscgen_runtime.go"]

    def test_rust_target_emits_parser_and_runtime(self) -> None:
        result = compile_and_lint(REST_SCHEMA, {"lang": "rust"})
        assert result["ok"] is True
        assert set(result["files"].keys()) == {
            "parser.rs",
            "sscgen_runtime.rs",
        }
        assert "pub struct UserApi" in result["files"]["parser.rs"]
        assert len(result["files"]["sscgen_runtime.rs"]) > 0

    def test_invalid_target_spec_returns_target_error(self) -> None:
        result = compile_and_lint(
            REST_SCHEMA,
            {
                "lang": "python",
                "http_client": "aiohttp",
                "http_io": "sync",
            },
        )
        assert result["ok"] is False
        assert result["files"] == {}
        assert result["target_error"] is not None
        assert "aiohttp" in result["target_error"]
        assert result["structs"] == [
            {"name": "UserApi", "type": "rest", "is_rest": True},
        ]


class TestTestHtml:
    """Verify `test_html` parser execution, struct selection, and selector health."""

    def test_auto_selects_primary_non_rest_struct_and_extracts_list(
        self,
    ) -> None:
        result = test_html(HTML_SCHEMA, SAMPLE_QUOTES_HTML)
        assert result["ok"] is True
        assert result["struct_name"] == "QuoteCatalogue"
        assert result["run_error"] is None
        assert isinstance(result["elapsed_ms"], float)
        assert result["elapsed_ms"] >= 0.0
        assert result["run_result"] == [
            {
                "text": "Simplicity is prerequisite for reliability.",
                "details": {
                    "author": "Edsger W. Dijkstra",
                    "tags": ["cs", "reliability"],
                },
            },
            {
                "text": "Programs must be written for people to read.",
                "details": {
                    "author": "Harold Abelson",
                    "tags": ["programming"],
                },
            },
        ]
        health = result["health"]
        assert health is not None
        assert health["struct_name"] == "QuoteCatalogue"
        assert health["passed"] is True
        checks_by_path = {c["path"]: c for c in health["checks"]}
        assert checks_by_path["QuoteCatalogue.@split-doc"] == {
            "path": "QuoteCatalogue.@split-doc",
            "selector_type": "css-all",
            "query": ".quote",
            "matches": 2,
            "status": "ok",
            "message": "(2 matches)",
        }
        assert checks_by_path["QuoteCatalogue.text"]["status"] == "ok"
        assert (
            checks_by_path["QuoteCatalogue.details[QuoteItem].author"]["status"]
            == "ok"
        )
        assert (
            checks_by_path["QuoteCatalogue.details[QuoteItem].tags"]["matches"]
            == 3
        )
        assert isinstance(json.dumps(result), str)

    def test_nested_struct_selection_in_isolation(self) -> None:
        result = test_html(
            HTML_SCHEMA,
            SAMPLE_QUOTES_HTML,
            struct_name="QuoteItem",
        )
        assert result["ok"] is True
        assert result["struct_name"] == "QuoteItem"
        assert result["run_error"] is None
        assert result["run_result"] == {
            "author": "Edsger W. Dijkstra",
            "tags": ["cs", "reliability", "programming"],
        }
        health = result["health"]
        assert health is not None
        assert health["struct_name"] == "QuoteItem"
        assert health["passed"] is True
        assert [c["path"] for c in health["checks"]] == [
            "QuoteItem.author",
            "QuoteItem.tags",
        ]

    def test_broken_selector_reports_health_failure(self) -> None:
        schema_with_broken = """\
(item)struct ProductCard {
    title { css "h1.title"; text }
    badges { css-all ".nonexistent-badge"; text }
    discount { css ".missing-discount"; text; fallback "0%" }
}
"""
        sample_html = '<div class="card"><h1 class="title">Keyboard</h1></div>'
        result = test_html(schema_with_broken, sample_html)
        assert result["ok"] is True
        assert result["struct_name"] == "ProductCard"
        assert result["run_result"] == {
            "title": "Keyboard",
            "badges": [],
            "discount": "0%",
        }
        health = result["health"]
        assert health is not None
        assert health["struct_name"] == "ProductCard"
        assert health["passed"] is False
        checks = {c["path"]: c for c in health["checks"]}
        assert checks["ProductCard.title"]["status"] == "ok"
        assert checks["ProductCard.title"]["matches"] == 1
        assert checks["ProductCard.badges"] == {
            "path": "ProductCard.badges",
            "selector_type": "css-all",
            "query": ".nonexistent-badge",
            "matches": 0,
            "status": "fail",
            "message": "(0 matches)",
        }
        assert checks["ProductCard.discount"]["status"] == "warn"
        assert checks["ProductCard.discount"]["matches"] == 0

    def test_raw_struct_extraction_and_health(self) -> None:
        raw_text = "Release bundle v2.45 (build 901)"
        result = test_html(
            ALL_STRUCT_TYPES_SCHEMA,
            raw_text,
            struct_name="RawModel",
        )
        assert result["ok"] is True
        assert result["struct_name"] == "RawModel"
        assert result["run_error"] is None
        assert result["run_result"] == {"version": "2.45"}
        health = result["health"]
        assert health is not None
        assert health["struct_name"] == "RawModel"
        assert health["passed"] is True
        assert len(health["checks"]) == 1
        assert health["checks"][0]["selector_type"] == "raw"
        assert health["checks"][0]["status"] == "warn"

    @pytest.mark.parametrize("explicit_struct", ["UserApi", None])
    def test_rejects_rest_struct_gracefully(
        self, explicit_struct: str | None
    ) -> None:
        result = test_html(
            REST_SCHEMA,
            "<html><body>ignored</body></html>",
            struct_name=explicit_struct,
        )
        assert result["ok"] is False
        assert result["struct_name"] == "UserApi"
        assert result["run_result"] is None
        assert result["health"] is None
        assert result["run_error"] is not None
        assert "(rest)struct" in result["run_error"]

    def test_unknown_struct_and_invalid_schema_errors(self) -> None:
        unknown = test_html(
            HTML_SCHEMA,
            SAMPLE_QUOTES_HTML,
            struct_name="MissingStruct",
        )
        assert unknown["ok"] is False
        assert unknown["struct_name"] == "MissingStruct"
        assert unknown["run_result"] is None
        assert unknown["health"] is None
        assert "MissingStruct" in (unknown["run_error"] or "")

        invalid = test_html(
            '(item)struct Broken { field { css "h1"; to-int } }',
            SAMPLE_QUOTES_HTML,
        )
        assert invalid["ok"] is False
        assert invalid["run_result"] is None
        assert invalid["health"] is None
        assert invalid["run_error"] is not None


class TestCuratedPresets:
    """Verify every curated preset in `playground/src/presets.json`."""

    def test_presets_collection_covers_required_categories(self) -> None:
        presets = _load_playground_presets()
        assert 5 <= len(presets) <= 6
        categories = {p["category"] for p in presets}
        assert {"html", "table", "raw", "rest"}.issubset(categories)

    @pytest.mark.parametrize(
        "preset",
        _load_playground_presets(),
        ids=lambda p: str(p["id"]),
    )
    @pytest.mark.parametrize("lang", ["python", "js", "go", "rust"])
    def test_every_preset_compiles_cleanly_across_targets(
        self, preset: dict[str, Any], lang: str
    ) -> None:
        result = compile_and_lint(preset["kdl"], {"lang": lang})
        errors = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert result["ok"] is True, (
            f"Preset {preset['id']} failed on {lang}: "
            f"diagnostics={result['diagnostics']}, target_error={result['target_error']}"
        )
        assert errors == []
        assert result["target_error"] is None
        assert len(result["structs"]) >= 1
        assert len(result["files"]) >= 1

    @pytest.mark.parametrize(
        "preset",
        [p for p in _load_playground_presets() if p["category"] != "rest"],
        ids=lambda p: str(p["id"]),
    )
    def test_non_rest_presets_pass_test_html_and_health(
        self, preset: dict[str, Any]
    ) -> None:
        result = test_html(preset["kdl"], preset["html"])
        assert result["ok"] is True, (
            f"Preset {preset['id']} failed test_html: {result['run_error']}"
        )
        assert result["run_error"] is None
        assert result["run_result"] is not None
        assert bool(result["run_result"]) is True
        health = result["health"]
        assert health is not None
        assert health["passed"] is True, (
            f"Preset {preset['id']} failed health check: {health['checks']}"
        )

        # Also verify every individual non-REST struct in the preset
        compiled = compile_and_lint(preset["kdl"])
        for struct_info in compiled["structs"]:
            if struct_info["is_rest"]:
                continue
            sub_res = test_html(
                preset["kdl"],
                preset["html"],
                struct_name=struct_info["name"],
            )
            assert sub_res["ok"] is True
            assert bool(sub_res["run_result"]) is True
            assert sub_res["health"] is not None
            assert sub_res["health"]["passed"] is True
