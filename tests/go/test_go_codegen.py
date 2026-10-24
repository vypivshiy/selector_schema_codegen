"""Go codegen smoke tests via pytest.

Generates Go code from .kdl schemas and verifies it via the Go toolchain:
  gofmt -l  (should list no files)
  go vet    (should pass)
  go build  (should compile)

All tests are skipped if the Go binary is not found in PATH.

REST schemas (08-22) require an HTTP-mock layer and are out of scope here.
Only HTML-parsing schemas are exercised.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from kdlquery import Severity
from ssc_codegen.core import parse_module
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.targets.golang import GO_CONVERTER

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = ROOT / "tests" / "integration" / "schemas"

pytestmark = [
    pytest.mark.skipif(
        shutil.which("go") is None,
        reason="Go toolchain not found in PATH",
    ),
    pytest.mark.toolchain,
]

# HTML-only schemas. REST (08-22) skipped — needs HTTP mock infra.
_SMOKES = [
    "00_full.kdl",
    "01_strings_basic.kdl",
    "02_arrays_and_conversions.kdl",
    "03_filters_and_predicates.kdl",
    "04_json_and_nested.kdl",
    "05_flat.kdl",
    "06_dict.kdl",
    "07_table.kdl",
    "18_json_basic.kdl",
    "19_json_mixed.kdl",
    # REST schemas — compile-only (no HTTP mock), validates method/error gen.
    "08_rest_basic.kdl",
    "09_rest_void.kdl",
    "10_rest_err_404.kdl",
    "11_rest_err_404_500.kdl",
    "12_rest_err_404_keys.kdl",
    "13_rest_err_200_field.kdl",
    "14_rest_int_placeholder.kdl",
    "15_rest_query_opt.kdl",
    "16_rest_header.kdl",
    "17_rest_post.kdl",
    "20_rest_prefix_form.kdl",
    "21_rest_multi_method.kdl",
    "22_rest_response_path.kdl",
    # HTML struct with @request — exercises MethodFetch codegen.
    "23_html_fetch.kdl",
    # REST with form-urlencoded body — exercises dict body path.
    "24_rest_form_body.kdl",
    # Two REST structs in one module — collision regression for
    # receiver-namespaced methods (default "Fetch" must not clash).
    "26_multi_rest_namespace.kdl",
    # REST query-string placeholders — regression for params dropped.
    "27_rest_query_params.kdl",
    # REST DSL cookies — regression for cookies dropped.
    "28_rest_cookies.kdl",
    # HTML @request with params + cookies — regression for both paths.
    "29_html_fetch_params_cookies.kdl",
    # (raw)struct with @request — raw constructor returns single value,
    # wrapper must append `, nil` to satisfy (*Name, error) signature.
    "30_raw_struct_request.kdl",
    # css-all + index/first/last — *goquery.Selection is not directly
    # indexable in Go, must emit .Eq(...).
    "31_css_all_indexing.kdl",
    # JSON key alias remapping (from="...") struct tags in Go structs.
    "32_json_aliased_remapping.kdl",
]


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


@pytest.fixture(scope="session")
def _go_module_template(tmp_path_factory):
    """Set up a Go module once per session: go.mod + downloaded deps.

    Each test copies go.mod/go.sum from here into its own tmp dir, so
    we never pay for `go mod tidy` more than once but get full isolation.
    """
    tmp = tmp_path_factory.mktemp("gomod_template")
    (tmp / "go.mod").write_text(
        "module sscgen_test\n\ngo 1.26\n", encoding="utf-8"
    )
    proc = subprocess.run(
        [
            "go",
            "get",
            "github.com/PuerkitoBio/goquery@v1.12.0",
            "github.com/tidwall/gjson@v1.18.0",
        ],
        cwd=tmp,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        pytest.skip(f"go get failed (no network?): {proc.stderr[:500]}")
    return tmp


@pytest.fixture
def go_module(_go_module_template, tmp_path):
    """Per-test isolated Go module sharing the session GOMODCACHE."""
    mod_dir = tmp_path / "gomod"
    mod_dir.mkdir()
    shutil.copy(_go_module_template / "go.mod", mod_dir / "go.mod")
    go_sum = _go_module_template / "go.sum"
    if go_sum.exists():
        shutil.copy(go_sum, mod_dir / "go.sum")
    return mod_dir


def _generate_and_write(go_module: Path, schema_file: str) -> Path:
    """Parse KDL, generate Go code, write parser + runtime to module dir.

    Uses ``write_bytes`` to force LF line endings — gofmt rejects CRLF.
    """
    ast = _parse_kdl(SCHEMAS_DIR / schema_file)
    code = GO_CONVERTER.convert(ast, package="sscgen_test")
    out = go_module / f"{Path(schema_file).stem}.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )
    return out


def _attribute_tool_output(
    output: str, pkg_to_schema: dict[str, str]
) -> dict[str, list[str]]:
    attributed: dict[str, list[str]] = {s: [] for s in pkg_to_schema.values()}
    current_schema: str | None = None
    for line in output.splitlines():
        found = False
        for pkg, s in pkg_to_schema.items():
            if pkg in line:
                current_schema = s
                attributed[s].append(line)
                found = True
                break
        if not found and current_schema:
            attributed[current_schema].append(line)
    return attributed


@pytest.fixture(scope="module")
def _go_batch_results(_go_module_template, tmp_path_factory):
    batch_dir = tmp_path_factory.mktemp("gobatch")
    shutil.copy(_go_module_template / "go.mod", batch_dir / "go.mod")
    go_sum = _go_module_template / "go.sum"
    if go_sum.exists():
        shutil.copy(go_sum, batch_dir / "go.sum")

    pkg_to_schema: dict[str, str] = {}
    for schema_file in _SMOKES:
        pkg_name = f"pkg_{Path(schema_file).stem}"
        pkg_to_schema[pkg_name] = schema_file
        pkg_dir = batch_dir / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ast = _parse_kdl(SCHEMAS_DIR / schema_file)
        code = GO_CONVERTER.convert(ast, package=pkg_name)
        (pkg_dir / f"{Path(schema_file).stem}.go").write_bytes(
            code.encode("utf-8")
        )
        (pkg_dir / "sscgen_runtime.go").write_bytes(
            GO_CONVERTER.emit_runtime(pkg_name).encode("utf-8")
        )

    # 1. gofmt -l .
    fmt = subprocess.run(
        ["gofmt", "-l", "."],
        cwd=batch_dir,
        capture_output=True,
        text=True,
    )
    unformatted = [
        line.strip() for line in fmt.stdout.splitlines() if line.strip()
    ]
    fmt_errors = _attribute_tool_output("\n".join(unformatted), pkg_to_schema)

    # 2. go vet ./...
    vet = subprocess.run(
        ["go", "vet", "./..."],
        cwd=batch_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    vet_errors = _attribute_tool_output(vet.stderr, pkg_to_schema)

    # 3. go build ./...
    build = subprocess.run(
        ["go", "build", "./..."],
        cwd=batch_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    build_errors = _attribute_tool_output(build.stderr, pkg_to_schema)

    results = {}
    for pkg_name, schema_file in pkg_to_schema.items():
        results[schema_file] = {
            "fmt_clean": len(fmt_errors[schema_file]) == 0,
            "fmt_output": "\n".join(fmt_errors[schema_file]),
            "vet_ok": vet.returncode == 0 or len(vet_errors[schema_file]) == 0,
            "vet_error": "\n".join(vet_errors[schema_file]) or vet.stderr,
            "build_ok": build.returncode == 0
            or len(build_errors[schema_file]) == 0,
            "build_error": "\n".join(build_errors[schema_file]) or build.stderr,
        }
        if vet.returncode != 0 and not any(vet_errors.values()):
            results[schema_file]["vet_ok"] = False
        if build.returncode != 0 and not any(build_errors.values()):
            results[schema_file]["build_ok"] = False

    return results


@pytest.mark.parametrize("schema_file", _SMOKES)
def test_go_smoke_compile(schema_file, _go_batch_results):
    """Schema generates Go that passes gofmt + go vet + go build."""
    res = _go_batch_results[schema_file]
    assert res["fmt_clean"], (
        f"gofmt would reformat files in {schema_file}:\n{res['fmt_output']}"
    )
    assert res["vet_ok"], (
        f"go vet failed for {schema_file}:\n{res['vet_error']}"
    )
    assert res["build_ok"], (
        f"go build failed for {schema_file}:\n{res['build_error']}"
    )


def test_go_dotpath_unmarshal_compiles(go_module):
    """Verify that a Go schema with dot-path navigation generates valid UnmarshalJSON."""
    src = """
json GeoLocation {
    latitude float from="coords.lat"
    longitude float from="coords.lng"
}

json UserProfile {
    user_id str from="meta.id"
    avatar_url str? from="profile.avatar.url"
    top_badge str? from="badges.0.icon"
    location GeoLocation?
}

struct UserParser {
    user {
        css "script#data"
        text
        jsonify UserProfile
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    out = go_module / "dotpath_test.go"
    out.write_bytes(code.encode("utf-8"))

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"


def test_runtime_gofmt_clean(go_module):
    """sscgen_runtime.go must be gofmt-clean after emitting helpers."""
    # Trigger helper accumulation by compiling one HTML + one REST schema.
    _generate_and_write(go_module, "01_strings_basic.kdl")
    _generate_and_write(go_module, "08_rest_basic.kdl")
    runtime = go_module / "sscgen_runtime.go"
    fmt = subprocess.run(
        ["gofmt", "-l", str(runtime)],
        capture_output=True,
        text=True,
    )
    assert not fmt.stdout.strip(), (
        f"gofmt would reformat runtime:\n{fmt.stdout}"
    )


def test_gofmt_failure_is_not_silenced(monkeypatch):
    from ssc_codegen.targets.golang import visitor

    monkeypatch.setattr(visitor.shutil, "which", lambda _: "gofmt")
    monkeypatch.setattr(
        visitor.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["gofmt"], returncode=2, stdout=b"", stderr=b"syntax error"
        ),
    )

    with pytest.raises(BuildTimeError, match="syntax error"):
        visitor._gofmt("package main\ninvalid")


def test_go_top_level_dict_json(go_module):
    """Verify Go codegen for top-level (dict)json schemas."""
    src = """
(dict)json Translations {
    @key str
    @value (array)str
}

(dict)json NumericLookup {
    @key int
    @value bool
}

json AnimeResponse {
    id str
    translations Translations
    lookup NumericLookup? @omitempty
}

struct AnimeParser {
    anime {
        css "script#data"
        text
        jsonify AnimeResponse
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert "type TranslationsJson = map[string][]string" in code
    assert "type NumericLookupJson = map[int64]bool" in code
    assert re.search(
        r'Translations\s+TranslationsJson\s+`json:"translations"`', code
    )
    assert re.search(
        r'Lookup\s+\*NumericLookupJson\s+`json:"lookup,omitempty"`', code
    )

    out = go_module / "toplevel_dict.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "toplevel_dict_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestTopLevelDictUnmarshal(t *testing.T) {
	raw := []byte(`{"id":"a1","translations":{"1":["jap","en"]},"lookup":{"100":true}}`)
	var resp AnimeResponseJson
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if resp.Id != "a1" {
		t.Errorf("expected id a1, got %s", resp.Id)
	}
	if len(resp.Translations["1"]) != 2 {
		t.Errorf("expected 2 translations, got %v", resp.Translations["1"])
	}
	if resp.Lookup == nil || !(*resp.Lookup)[100] {
		t.Errorf("expected lookup[100] == true, got %v", resp.Lookup)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_parent_struct_inline_dict_field(go_module):
    """Verify Go codegen for parent struct with inline (dict) fields."""
    src = """
json Catalog {
    name str
    translations (dict) {
        @key str
        @value (array)str
    }
    meta (dict)? @omitempty {
        @key str
        @value str
    }
    flags (dict) from="custom_flags" {
        @key int
        @value bool
    }
}

struct CatalogParser {
    catalog {
        css "script#catalog"
        text
        jsonify Catalog
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert re.search(
        r'Translations\s+map\[string\]\[\]string\s+`json:"translations"`', code
    )
    assert re.search(
        r'Meta\s+\*map\[string\]string\s+`json:"meta,omitempty"`', code
    )
    assert re.search(r'Flags\s+map\[int64\]bool\s+`json:"custom_flags"`', code)

    out = go_module / "inline_dict.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "inline_dict_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestInlineDictUnmarshal(t *testing.T) {
	raw := []byte(`{"name":"test","translations":{"10":["ru","en"]},"meta":{"author":"alice"},"custom_flags":{"42":true}}`)
	var c CatalogJson
	if err := json.Unmarshal(raw, &c); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if c.Name != "test" {
		t.Errorf("expected name test, got %s", c.Name)
	}
	if len(c.Translations["10"]) != 2 {
		t.Errorf("expected 2 translations, got %v", c.Translations["10"])
	}
	if c.Meta == nil || (*c.Meta)["author"] != "alice" {
		t.Errorf("expected author alice, got %v", c.Meta)
	}
	if !c.Flags[42] {
		t.Errorf("expected flags[42] to be true")
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_parent_struct_hoisted_inline_schemas(go_module):
    """Verify Go codegen for parent struct with hoisted inline object and array blocks."""
    src = """
json AnimeResponse {
    id str
    material_data {
        anime_title str
        year int
    }
    nodes (array)Node {
        id int
        name str
    }
    extra ExtraInfo? from="extra_info" @omitempty {
        details str
    }
}

struct AnimeResponseParser {
    anime {
        css "script#anime"
        text
        jsonify AnimeResponse
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert "type AnimeResponseMaterialDataJson struct" in code
    assert "type NodeJson struct" in code
    assert "type ExtraInfoJson struct" in code
    assert re.search(
        r'MaterialData\s+AnimeResponseMaterialDataJson\s+`json:"material_data"`',
        code,
    )
    assert re.search(r'Nodes\s+\[\]NodeJson\s+`json:"nodes"`', code)
    assert re.search(
        r'Extra\s+\*ExtraInfoJson\s+`json:"extra_info,omitempty"`', code
    )

    out = go_module / "hoisted_inline.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "hoisted_inline_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestHoistedInlineUnmarshal(t *testing.T) {
	raw := []byte(`{"id":"a2","material_data":{"anime_title":"Title","year":2024},"nodes":[{"id":1,"name":"Hero"}],"extra_info":{"details":"Extra"}}`)
	var resp AnimeResponseJson
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if resp.Id != "a2" {
		t.Errorf("expected id a2, got %s", resp.Id)
	}
	if resp.MaterialData.AnimeTitle != "Title" || resp.MaterialData.Year != 2024 {
		t.Errorf("unexpected material data: %+v", resp.MaterialData)
	}
	if len(resp.Nodes) != 1 || resp.Nodes[0].Name != "Hero" {
		t.Errorf("unexpected nodes: %+v", resp.Nodes)
	}
	if resp.Extra == nil || resp.Extra.Details != "Extra" {
		t.Errorf("unexpected extra: %+v", resp.Extra)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_top_level_dict_with_inline_value_schema(go_module):
    """Verify Go codegen for top-level (dict)json with inline @value block."""
    src = """
(dict)json Translations {
    @key str
    @value TranslationValue {
        title str from="display_title"
        count int
        notes @skip
    }
}

json Catalog {
    name str
    translations Translations
}

struct CatalogParser {
    catalog {
        css "script#catalog"
        text
        jsonify Catalog
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert "type TranslationValueJson struct" in code
    assert "type TranslationsJson = map[string]TranslationValueJson" in code
    assert re.search(r'Title\s+string\s+`json:"display_title"`', code)
    assert re.search(r'Count\s+int64\s+`json:"count"`', code)
    assert "Notes" not in code
    assert re.search(
        r'Translations\s+TranslationsJson\s+`json:"translations"`', code
    )

    out = go_module / "toplevel_dict_inline_value.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "toplevel_dict_inline_value_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestTopLevelDictWithInlineValueUnmarshal(t *testing.T) {
	raw := []byte(`{"name":"summer-season","translations":{"rus":{"display_title":"Русский","count":12,"notes":"ignore"},"eng":{"display_title":"English","count":24}}}`)
	var c CatalogJson
	if err := json.Unmarshal(raw, &c); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if c.Name != "summer-season" {
		t.Errorf("expected name summer-season, got %s", c.Name)
	}
	if len(c.Translations) != 2 {
		t.Fatalf("expected 2 translations, got %d", len(c.Translations))
	}
	rus := c.Translations["rus"]
	if rus.Title != "Русский" || rus.Count != 12 {
		t.Errorf("unexpected rus translation: %+v", rus)
	}
	eng := c.Translations["eng"]
	if eng.Title != "English" || eng.Count != 24 {
		t.Errorf("unexpected eng translation: %+v", eng)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_nested_dict_value_schema_multi_level(go_module):
    """Verify Go codegen for multi-level nested dictionary value schemas (e.g. anime translations)."""
    src = """
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
            season int
            kind str from="type"
        }
    }
}

struct AnimeParser {
    anime {
        css "script#anime"
        text
        jsonify AnimeResponse
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    # Verify hoisted struct definitions exist with expected fields and JSON tags
    assert "type EpisodeValueJson struct" in code
    assert re.search(r'Link\s+string\s+`json:"stream_url"`', code)
    assert "Screenshots" not in code

    assert "type TranslationValueJson struct" in code
    assert re.search(
        r'Episodes\s+map\[int64\]EpisodeValueJson\s+`json:"episodes"`', code
    )
    assert re.search(r'IsActive\s+bool\s+`json:"is_active"`', code)
    assert re.search(r'Season\s+int64\s+`json:"season"`', code)
    assert re.search(r'Kind\s+string\s+`json:"type"`', code)

    assert "type AnimeResponseJson struct" in code
    assert re.search(
        r'Translations\s+map\[string\]TranslationValueJson\s+`json:"translations"`',
        code,
    )

    out = go_module / "nested_dict_multi_level.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "nested_dict_multi_level_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestNestedDictMultiLevelUnmarshal(t *testing.T) {
	raw := []byte(`{
		"translations": {
			"sub": {
				"episodes": {
					"1": {"stream_url": "https://cdn.example.com/ep1.mp4", "screenshots": ["s1.jpg"]},
					"2": {"stream_url": "https://cdn.example.com/ep2.mp4"}
				},
				"is_active": true,
				"season": 2,
				"type": "tv"
			}
		}
	}`)
	var resp AnimeResponseJson
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(resp.Translations) != 1 {
		t.Fatalf("expected 1 translation, got %d", len(resp.Translations))
	}
	sub, ok := resp.Translations["sub"]
	if !ok {
		t.Fatalf("missing key 'sub'")
	}
	if !sub.IsActive || sub.Season != 2 || sub.Kind != "tv" {
		t.Errorf("unexpected sub translation metadata: %+v", sub)
	}
	if len(sub.Episodes) != 2 {
		t.Fatalf("expected 2 episodes, got %d", len(sub.Episodes))
	}
	ep1, ok1 := sub.Episodes[1]
	if !ok1 || ep1.Link != "https://cdn.example.com/ep1.mp4" {
		t.Errorf("unexpected ep1: %+v", ep1)
	}
	ep2, ok2 := sub.Episodes[2]
	if !ok2 || ep2.Link != "https://cdn.example.com/ep2.mp4" {
		t.Errorf("unexpected ep2: %+v", ep2)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_inline_dict_anonymous_value_and_array_value(go_module):
    """Verify Go codegen for anonymous @value block and @value (array)ItemModel."""
    src = """
json Project {
    groups (dict) {
        @key str
        @value (array)GroupItem {
            id int
            name str
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

struct ProjectParser {
    project {
        css "script#proj"
        text
        jsonify Project
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert "type GroupItemJson struct" in code
    assert re.search(r'Id\s+int64\s+`json:"id"`', code)
    assert re.search(r'Name\s+string\s+`json:"name"`', code)

    assert "type ProjectSettingsValueJson struct" in code
    assert re.search(r'Enabled\s+bool\s+`json:"enabled"`', code)
    assert re.search(r'Priority\s+\*int64\s+`json:"priority,omitempty"`', code)

    assert re.search(
        r'Groups\s+map\[string\]\[\]GroupItemJson\s+`json:"groups"`', code
    )
    assert re.search(
        r'Settings\s+map\[string\]ProjectSettingsValueJson\s+`json:"settings"`',
        code,
    )

    out = go_module / "inline_dict_anon_and_array.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "inline_dict_anon_and_array_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"testing"
)

func TestInlineDictAnonAndArrayUnmarshal(t *testing.T) {
	raw := []byte(`{
		"groups": {
			"dev": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
		},
		"settings": {
			"general": {"enabled": true, "priority": 10},
			"advanced": {"enabled": false}
		}
	}`)
	var proj ProjectJson
	if err := json.Unmarshal(raw, &proj); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	devGroup, ok := proj.Groups["dev"]
	if !ok || len(devGroup) != 2 {
		t.Fatalf("expected 2 dev group items, got %+v", devGroup)
	}
	if devGroup[0].Name != "Alice" || devGroup[1].Name != "Bob" {
		t.Errorf("unexpected dev group items: %+v", devGroup)
	}
	genSettings, ok := proj.Settings["general"]
	if !ok || !genSettings.Enabled || genSettings.Priority == nil || *genSettings.Priority != 10 {
		t.Errorf("unexpected general settings: %+v", genSettings)
	}
	advSettings, ok := proj.Settings["advanced"]
	if !ok || advSettings.Enabled || advSettings.Priority != nil {
		t.Errorf("unexpected advanced settings: %+v", advSettings)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_gjson_path_subset_escaped_dots_hash_len_and_projection(go_module):
    """Verify Go codegen and runtime execution for GJSON path subset:
    escaped dots (from="os\\.version"), array length (from="items.#"),
    and array element projection (from="tags.#.name") via gjson.
    """
    src = r"""
json ReleaseManifest {
    os_version str from="os\\.version"
    item_count int from="items.#"
    tag_names (array)str from="tags.#.name"
    first_tag str from="tags.0.name"
}

(raw)struct ManifestEnvelope {
    manifest {
        jsonify ReleaseManifest path="envelope\\.data"
    }
}
"""
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert 'gjson.GetBytes(raw, "os\\\\.version")' in code
    assert 'gjson.GetBytes(raw, "items.#")' in code
    assert 'gjson.GetBytes(raw, "tags.#.name")' in code
    assert 'gjson.GetBytes(raw, "tags.0.name")' in code

    out = go_module / "gjson_subset.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out)], capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    vet = subprocess.run(
        ["go", "vet", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert vet.returncode == 0, f"go vet failed:\n{vet.stderr}"

    build = subprocess.run(
        ["go", "build", "./..."], cwd=go_module, capture_output=True, text=True
    )
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    test_go = go_module / "gjson_subset_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestGjsonPathSubsetUnmarshal(t *testing.T) {
	raw := []byte(`{
		"os.version": "24.04",
		"items": ["a", "b", "c"],
		"tags": [
			{"name": "action", "id": 1},
			{"other": "skipped"},
			{"name": "sci-fi", "id": 2}
		]
	}`)
	var manifest ReleaseManifestJson
	if err := json.Unmarshal(raw, &manifest); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if manifest.OsVersion != "24.04" {
		t.Errorf("expected OsVersion '24.04', got %q", manifest.OsVersion)
	}
	if manifest.ItemCount != 3 {
		t.Errorf("expected ItemCount 3, got %d", manifest.ItemCount)
	}
	expectedTags := []string{"action", "sci-fi"}
	if !reflect.DeepEqual(manifest.TagNames, expectedTags) {
		t.Errorf("expected TagNames %v, got %v", expectedTags, manifest.TagNames)
	}
	if manifest.FirstTag != "action" {
		t.Errorf("expected FirstTag 'action', got %q", manifest.FirstTag)
	}

	envelopeRaw := `{"envelope.data": {"os.version": "14.2.1", "items": [10, 20], "tags": [{"name": "drama"}]}}`
	envRes := NewManifestEnvelope(envelopeRaw).Parse()
	if envRes.Manifest.OsVersion != "14.2.1" || envRes.Manifest.ItemCount != 2 {
		t.Errorf("unexpected envelope parse result: %+v", envRes.Manifest)
	}
	if !reflect.DeepEqual(envRes.Manifest.TagNames, []string{"drama"}) {
		t.Errorf("unexpected envelope tag names: %v", envRes.Manifest.TagNames)
	}
}
""",
        encoding="utf-8",
    )
    test_run = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_runtime_http_delegation_docstrings_and_null_body(go_module):
    """Verify Go multi-line @doc comments, sscRestCallValue delegation,
    JSON body null preservation, and sscReqOpt merge."""
    src = '''
@doc """
    Go delegation test module.
    Second line of module doc.
    """

json User {
    id int
    name str
    nickname str?
}

(rest)struct DelegatedAPI {
    @doc """
        DelegatedAPI client struct.
        Handles user updates.
        """
    @request name=update-user response=User doc="""
        Update user via POST.
        Preserves null nickname in JSON body.
        """ """
    POST {{base_url}}/users?tag={{tag:str}} HTTP/1.1
    Content-Type: application/json
    X-App: ssc-go

    {"name": "{{name:str}}", "nickname": null}
    """
}
'''
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert (
        "// Go delegation test module.\n// Second line of module doc." in code
    )
    assert "// DelegatedAPI client struct.\n// Handles user updates." in code
    assert (
        "// Update user via POST.\n// Preserves null nickname in JSON body."
        in code
    )
    assert "sscRestCallValue[UserJson]" in code

    out = go_module / "delegated_api.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out), str(runtime)],
        capture_output=True,
        text=True,
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    test_go = go_module / "delegated_api_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGoDelegatedRestNullBodyAndOptsMerge(t *testing.T) {
	var gotQuery string
	var gotAppHdr string
	var gotCustomHdr string
	var gotBody map[string]any

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotQuery = r.URL.RawQuery
		gotAppHdr = r.Header.Get("X-App")
		gotCustomHdr = r.Header.Get("X-Custom")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id": 1, "name": "Alice", "nickname": null}`))
	}))
	defer srv.Close()

	api := NewDelegatedAPI()
	withCustom := func(o *sscReqOpts) {
		if o.Headers == nil {
			o.Headers = sscHeaders{}
		}
		o.Headers["X-Custom"] = []string{"caller-opt"}
	}

	user, err := api.UpdateUser(srv.Client(), srv.URL, "v1", "Alice", withCustom)
	if err != nil {
		t.Fatalf("UpdateUser failed: %v", err)
	}
	if user.Id != 1 || user.Name != "Alice" || user.Nickname != nil {
		t.Fatalf("unexpected user: %+v", user)
	}
	if gotQuery != "tag=v1" {
		t.Errorf("expected query 'tag=v1', got %q", gotQuery)
	}
	if gotAppHdr != "ssc-go" || gotCustomHdr != "caller-opt" {
		t.Errorf("expected merged headers X-App=ssc-go & X-Custom=caller-opt, got %q / %q", gotAppHdr, gotCustomHdr)
	}
	nickVal, hasNick := gotBody["nickname"]
	if !hasNick || nickVal != nil {
		t.Errorf("expected JSON body to preserve nickname: null, got %+v", gotBody)
	}
}
""",
        encoding="utf-8",
    )

    test_run = subprocess.run(
        [
            "go",
            "test",
            "-v",
            "-run",
            "TestGoDelegatedRestNullBodyAndOptsMerge",
            "./...",
        ],
        cwd=go_module,
        capture_output=True,
        text=True,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )


def test_go_rest_error_matcher_fallthrough_and_suffix(go_module):
    """Verify Go @error:<suffix>, 2-leaf-key auto-naming, dot-path key checks,
    and safe runtime fallthrough on schema mismatch or non-JSON responses."""
    src = '''
json User {
    id int
    name str
}

json SearchError {
    error str
    reason str
}

json GenericError {
    message str
}

json ApiError {
    detail_code int
}

(rest)struct AnimeVostAPI {
    @error:not-found 404 SearchError error="Ничего не найдено"
    @error 404 GenericError
    @error 400 GenericError "a.b.first" "c.d.second" third="x"
    @error 200 ApiError "error.code"

    @request name=get-user response=User """
    GET {{base_url}}/users/{{id:int}} HTTP/1.1
    """
}
'''
    module_ast, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors

    code = GO_CONVERTER.convert(module_ast, package="sscgen_test")
    assert "type AnimeVostAPIErr404NotFound struct {" in code
    assert "type AnimeVostAPIErr404 struct {" in code
    assert "type AnimeVostAPIErr400FirstSecond struct {" in code
    assert "type AnimeVostAPIErr200Code struct {" in code

    out = go_module / "err_fallthrough.go"
    out.write_bytes(code.encode("utf-8"))

    runtime = go_module / "sscgen_runtime.go"
    runtime.write_bytes(
        GO_CONVERTER.emit_runtime("sscgen_test").encode("utf-8")
    )

    fmt = subprocess.run(
        ["gofmt", "-l", str(out), str(runtime)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fmt.returncode == 0
    assert not fmt.stdout.strip()

    test_go = go_module / "err_fallthrough_test.go"
    test_go.write_text(
        """package sscgen_test

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGoRestErrorMatcherFallthrough(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/users/1":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"error": "Ничего не найдено", "reason": "removed"}`))
		case "/users/2":
			// Matches first 404 condition (error="Ничего не найдено") but misses required "reason",
			// so SearchErrorJson unmarshal fails and falls through to second 404 rule (GenericErrorJson).
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"error": "Ничего не найдено", "message": "fallback generic"}`))
		case "/users/3":
			// Empty JSON object {} fails both 404 schemas -> falls through to UnknownErr.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{}`))
		case "/users/4":
			// Non-JSON HTML 404 body -> falls through to UnknownErr.
			w.Header().Set("Content-Type", "text/html")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`<html>404 Not Found</html>`))
		case "/users/5":
			// Matches 400 rule with 3 keys (capped at 2 leaf segments: FirstSecond).
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"a": {"b": {"first": 1}}, "c": {"d": {"second": true}}, "third": "x", "message": "invalid params"}`))
		case "/users/6":
			// Matches 200 nested positional key "error.code" and ApiErrorJson.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"error": {"code": 123}, "detail_code": 99}`))
		case "/users/7":
			// 200 with "error": {} (no "code") -> does not match @error 200, decodes UserJson.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"error": {}, "id": 7, "name": "Alice"}`))
		case "/users/8":
			// 200 with "error.code" present, but missing "detail_code" for ApiErrorJson -> falls through to UserJson!
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"error": {"code": 123}, "id": 8, "name": "Bob"}`))
		}
	}))
	defer srv.Close()

	api := NewAnimeVostAPI()

	// 1. Explicit suffix @error:not-found
	_, err := api.GetUser(srv.Client(), srv.URL, 1)
	var errNotFound *AnimeVostAPIErr404NotFound
	if !errors.As(err, &errNotFound) {
		t.Fatalf("expected *AnimeVostAPIErr404NotFound, got %T: %v", err, err)
	}
	if errNotFound.Body.Reason != "removed" {
		t.Errorf("expected Reason 'removed', got %q", errNotFound.Body.Reason)
	}

	// 2. Fallthrough from first 404 rule to second 404 rule on schema mismatch
	_, err = api.GetUser(srv.Client(), srv.URL, 2)
	var errGeneric404 *AnimeVostAPIErr404
	if !errors.As(err, &errGeneric404) {
		t.Fatalf("expected fallthrough to *AnimeVostAPIErr404, got %T: %v", err, err)
	}
	if errGeneric404.Body.Message != "fallback generic" {
		t.Errorf("expected Message 'fallback generic', got %q", errGeneric404.Body.Message)
	}

	// 3. Fallthrough to UnknownErr on empty JSON {}
	_, err = api.GetUser(srv.Client(), srv.URL, 3)
	var unknownErr *UnknownErr
	if !errors.As(err, &unknownErr) {
		t.Fatalf("expected *UnknownErr for empty JSON 404, got %T: %v", err, err)
	}
	if unknownErr.Status != 404 || unknownErr.Body != "{}" {
		t.Errorf("unexpected UnknownErr: %+v", unknownErr)
	}

	// 4. Fallthrough to UnknownErr on HTML 404
	_, err = api.GetUser(srv.Client(), srv.URL, 4)
	unknownErr = nil
	if !errors.As(err, &unknownErr) {
		t.Fatalf("expected *UnknownErr for HTML 404, got %T: %v", err, err)
	}
	if unknownErr.Status != 404 || unknownErr.Body != "<html>404 Not Found</html>" {
		t.Errorf("unexpected UnknownErr for HTML 404: %+v", unknownErr)
	}

	// 5. 2-leaf-key auto-naming cap on 400
	_, err = api.GetUser(srv.Client(), srv.URL, 5)
	var err400 *AnimeVostAPIErr400FirstSecond
	if !errors.As(err, &err400) {
		t.Fatalf("expected *AnimeVostAPIErr400FirstSecond, got %T: %v", err, err)
	}
	if err400.Body.Message != "invalid params" {
		t.Errorf("expected Message 'invalid params', got %q", err400.Body.Message)
	}

	// 6. Nested positional key "error.code" on 200 matches ApiErrorJson
	_, err = api.GetUser(srv.Client(), srv.URL, 6)
	var err200 *AnimeVostAPIErr200Code
	if !errors.As(err, &err200) {
		t.Fatalf("expected *AnimeVostAPIErr200Code, got %T: %v", err, err)
	}
	if err200.Body.DetailCode != 99 {
		t.Errorf("expected DetailCode 99, got %d", err200.Body.DetailCode)
	}

	// 7. Nested positional key "error.code" rejects {"error": {}}
	u7, err := api.GetUser(srv.Client(), srv.URL, 7)
	if err != nil {
		t.Fatalf("expected nil error for user 7, got %v", err)
	}
	if u7.Id != 7 || u7.Name != "Alice" {
		t.Errorf("unexpected user 7: %+v", u7)
	}

	// 8. 200 error matcher falls through when ApiErrorJson projection fails
	u8, err := api.GetUser(srv.Client(), srv.URL, 8)
	if err != nil {
		t.Fatalf("expected nil error for user 8 after 200 matcher fallthrough, got %v", err)
	}
	if u8.Id != 8 || u8.Name != "Bob" {
		t.Errorf("unexpected user 8: %+v", u8)
	}
}
""",
        encoding="utf-8",
    )

    test_run = subprocess.run(
        [
            "go",
            "test",
            "-v",
            "-run",
            "TestGoRestErrorMatcherFallthrough",
            "./...",
        ],
        cwd=go_module,
        capture_output=True,
        text=True,
        check=False,
    )
    assert test_run.returncode == 0, (
        f"go test failed:\n{test_run.stderr}\n{test_run.stdout}"
    )
