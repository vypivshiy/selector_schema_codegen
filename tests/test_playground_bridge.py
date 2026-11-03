"""Tests for the Web Playground worker bridge (`ssc_codegen.playground_bridge`)."""

from __future__ import annotations

import json

import pytest

from ssc_codegen.core.format import diagnostic_to_dict
from ssc_codegen.core.reader import parse_module
from ssc_codegen.playground_bridge import compile_and_lint

HTML_SCHEMA = """\
(item)struct QuoteItem {
    author { css ".author"; text }
    tags { css-all ".tag"; text }
}

(list)struct QuoteCatalogue {
    @split-doc ".quote"
    text { css ".text"; text }
    details { nested QuoteItem }
}
"""

ALL_STRUCT_TYPES_SCHEMA = """\
(item)struct ItemModel {
    title { css "h1"; text }
}

(list)struct ListModel {
    @split-doc "li"
    label { css "span"; text }
}

(table)struct TableModel {
    @table "table.specs"
    @rows "tr"
    @match "th" { text }
    @value "td" { text }
    brand { match { eq "Brand" } }
}

(dict)struct DictModel {
    @split-doc "dl > div"
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
