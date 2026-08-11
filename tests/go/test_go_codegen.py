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

import shutil
import subprocess
from pathlib import Path

import pytest

from kdlquery import Severity
from ssc_codegen.core import parse_module
from ssc_codegen.targets.golang import GO_CONVERTER

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = ROOT / "tests" / "integration" / "schemas"

pytestmark = pytest.mark.skipif(
    shutil.which("go") is None,
    reason="Go toolchain not found in PATH",
)

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


@pytest.mark.parametrize("schema_file", _SMOKES)
def test_go_smoke_compile(schema_file, go_module):
    """Schema generates Go that passes gofmt + go vet + go build."""
    out = _generate_and_write(go_module, schema_file)

    # gofmt -l: must list no files (empty stdout).
    fmt = subprocess.run(
        ["gofmt", "-l", str(out)],
        capture_output=True,
        text=True,
    )
    assert fmt.returncode == 0, f"gofmt failed: {fmt.stderr}"
    assert not fmt.stdout.strip(), (
        f"gofmt would reformat {out.name}:\n{fmt.stdout}"
    )

    # go vet ./...
    vet = subprocess.run(
        ["go", "vet", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert vet.returncode == 0, (
        f"go vet failed for {schema_file}:\n"
        f"STDOUT:\n{vet.stdout}\nSTDERR:\n{vet.stderr}"
    )

    # go build ./...
    build = subprocess.run(
        ["go", "build", "./..."],
        cwd=go_module,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert build.returncode == 0, (
        f"go build failed for {schema_file}:\n"
        f"STDOUT:\n{build.stdout}\nSTDERR:\n{build.stderr}"
    )


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
