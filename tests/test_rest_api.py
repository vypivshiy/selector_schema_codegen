"""Tests for REST API struct support (struct type=rest).

Covers:
- Parser: StructType.REST, @request on REST, @error parsing
- Converters: py_bs4 and js_pure code generation
"""

from __future__ import annotations

import ast as pyast
from base64 import b64encode

import pytest
from kdlquery import Severity

from ssc_codegen.ast import (
    ErrorResponse,
    MethodRest,
    StructRest,
)
from ssc_codegen.core import parse_module
from ssc_codegen.request_spec import parse_to_http
from ssc_codegen.targets.python import PY_BS4_CONVERTER

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(src: str):
    module, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError("; ".join(d.message for d in errors))
    return module


def _rest_src(*, extra_requests: str = "", errors: str = "") -> str:
    return (
        "json User { id int; name str }\n"
        "json Err { code int; message str }\n"
        "struct API type=rest {\n"
        '    @request name=get-user response=User """\n'
        "    GET /users/{{id}} HTTP/1.1\n"
        "    Host: api.example.com\n"
        '    """\n'
        f"{extra_requests}"
        f"{errors}"
        "}\n"
    )


def _exec_with_runtime(parser_src: str, runtime_src: str) -> dict:
    """Exec the generated parser file with its sibling runtime module.

    The parser file uses a relative import (``from .sscgen_runtime import
    ...``); we satisfy it by registering a synthetic parent package in
    ``sys.modules`` so Python's import machinery can resolve the relative
    name. Returns the parser module's namespace dict.
    """
    import sys
    import types

    pkg_name = "_ssc_test_pkg"
    rt_dotted = f"{pkg_name}.sscgen_runtime"
    parser_dotted = f"{pkg_name}.parser"
    # Clear stale registrations from previous parametrize iterations.
    sys.modules.pop(pkg_name, None)
    sys.modules.pop(rt_dotted, None)
    sys.modules.pop(parser_dotted, None)

    rt_ns: dict = {}
    exec(compile(runtime_src, "<rt>", "exec"), rt_ns)
    rt_mod = types.ModuleType(rt_dotted)
    for k, v in rt_ns.items():
        setattr(rt_mod, k, v)
    rt_mod.__package__ = pkg_name
    pkg_mod = types.ModuleType(pkg_name)
    pkg_mod.__path__ = []  # mark as package
    pkg_mod.sscgen_runtime = rt_mod
    sys.modules[pkg_name] = pkg_mod
    sys.modules[rt_dotted] = rt_mod

    parser_mod = types.ModuleType(parser_dotted)
    parser_mod.__package__ = pkg_name
    parser_ns = parser_mod.__dict__
    # Register the parser module BEFORE exec so dataclasses on Python 3.10
    # can resolve ``cls.__module__`` for the Literal[...] field annotation.
    sys.modules[parser_dotted] = parser_mod
    exec(compile(parser_src, "<parser>", "exec"), parser_ns)
    return parser_ns


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestRestParser:
    def test_request_config_name_and_response(self):
        module = _parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, StructRest))
        reqs = [n for n in struct.body if isinstance(n, MethodRest)]
        assert len(reqs) == 1
        assert reqs[0].name == "get-user"
        assert reqs[0].response_schema == "User"

    def test_error_response_parsed(self):
        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = _parse(src)
        struct = next(n for n in module.body if isinstance(n, StructRest))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert len(errors) == 2
        assert errors[0].status == 404
        assert errors[0].schema_name == "Err"
        assert errors[1].status == 500
        assert errors[1].schema_name == "Err"

    def test_curl_body_implies_post_and_keeps_json_placeholders(self):
        request = parse_to_http(
            "curl --json "
            '\'{"name": "{{name}}", "active": {{active:bool}}}\' '
            "https://example.com/users"
        )

        assert request.method == "POST"
        assert request.body_kind == "json"
        assert {p.name for p in request.placeholders} == {"name", "active"}

    def test_curl_auth_and_data_urlencode_are_preserved(self):
        request = parse_to_http(
            "curl -u user:pass --data-urlencode 'query=hello world' "
            "https://example.com/search"
        )
        token = b64encode(b"user:pass").decode()

        assert request.method == "POST"
        assert request.headers["Authorization"].source == f"Basic {token}"
        assert request.body_kind == "form"
        assert request.payload["query"].source == "hello world"

    def test_raw_http_headers_are_case_insensitive(self):
        request = parse_to_http(
            "POST /users HTTP/1.1\n"
            "host: api.example.com\n"
            "content-type: application/json\n"
            "cookie: session=abc\n\n"
            '{"name": "Ada"}'
        )

        assert request.url.source == "https://api.example.com/users"
        assert request.body_kind == "json"
        assert request.cookies["session"].source == "abc"

    def test_error_mixed_conditions_parsed(self):
        src = _rest_src(errors='    @error 404 Err error detail="msg"\n')
        module = _parse(src)
        struct = next(n for n in module.body if isinstance(n, StructRest))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert len(errors) == 1
        assert errors[0].required_keys == ["error"]
        assert errors[0].conditions == {"detail": "msg"}

    @pytest.mark.parametrize("status", [0, 99, 600, 999])
    def test_error_status_must_be_http_status(self, status):
        _, diagnostics = parse_module(
            _rest_src(errors=f"    @error {status} Err\n")
        )

        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].code == "E002"
        assert "100..599" in errors[0].message


# ---------------------------------------------------------------------------
# Converter tests (smoke)
# ---------------------------------------------------------------------------


class TestRestPyConverter:
    def test_json_body_escaping_is_structured_in_js_and_go(self):
        src = (
            "json User { id int; name str }\n"
            "struct API type=rest {\n"
            '    @request name=create response=User """\n'
            "    POST /users HTTP/1.1\n"
            "    Host: x.com\n"
            "    Content-Type: application/json\n\n"
            '    {"name": "{{name}}", "active": {{active:bool}}}\n'
            '    """\n'
            "}\n"
        )
        module = _parse(src)

        from ssc_codegen.targets.golang import GO_CONVERTER
        from ssc_codegen.targets.javascript import JS_CONVERTER

        js_code = JS_CONVERTER.convert(module, http_client="fetch")
        go_code = GO_CONVERTER.convert(module)

        assert 'JSON.stringify({"name": name, "active": active})' in js_code
        assert "stdJSONBody(map[string]any{" in go_code
        assert '{{\\"name\\"' not in go_code

    def test_go_raw_body_does_not_require_json(self):
        src = (
            "struct Page {\n"
            '    @request """\n'
            "    POST /submit HTTP/1.1\n"
            "    Host: x.com\n\n"
            "    raw={{value}}\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        module = _parse(src)

        from ssc_codegen.targets.golang import GO_CONVERTER

        code = GO_CONVERTER.convert(module)
        runtime = GO_CONVERTER.emit_runtime("main")

        assert 'Body: fmt.Sprintf("raw=%s", value)' in code
        assert "strings.NewReader(" in runtime


class TestRestJsConverter:
    def test_js_fetch_and_jsdoc_codegen(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "class API" in code
        assert "static async getUser" in code
        # Result-style JSDoc typedefs + plain object returns
        assert "@typedef {Object} Ok" in code
        assert "@typedef {Object} APIErr404" in code
        assert "@typedef {Object} UnknownErr" in code
        assert "@typedef {Object} TransportErr" in code
        assert "isOk: true" in code
        assert "isOk: false" in code
        assert (
            "@returns {Promise<Ok<UserJson> | APIErr404 | UnknownErr"
            " | TransportErr>}" in code
        )
        assert "} catch (e) {" in code
        assert (
            "isOk: false, status: 0, headers: {}, value: null, "
            "cause: String(e)" in code
        )
        assert "Object.fromEntries([..._resp.headers.entries()])" in code
        assert "headers: _headers, value: _value" in code
        assert "async function sscRestCall(" in code
        assert "async function sscRestCallAxios(" in code
        assert "function sscDispatchErr(" in code
        assert "return sscRestCall(" in code

    def test_js_axios_variant(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="axios")
        assert "client.request" in code
        # Axios uses dedicated sscRestCallAxios helper
        assert "sscRestCallAxios" in code


# ---------------------------------------------------------------------------
# Typed placeholders (§3 plan: type / array / optional / style)
# ---------------------------------------------------------------------------


def _typed_rest_src(request_line: str) -> str:
    return (
        "json User { id int }\n"
        "struct API type=rest {\n"
        '    @request response=User """\n'
        f"    {request_line}\n"
        "    Host: api.example.com\n"
        '    """\n'
        "}\n"
    )


class TestTypedPlaceholdersAst:
    def test_legacy_plain_name_is_str_scalar_required(self):
        from ssc_codegen.ast.struct import PlaceholderSpec

        ph = PlaceholderSpec.parse("{{name}}")
        assert ph is not None
        assert ph.name == "name"
        assert ph.type_name == "str"
        assert ph.is_array is False
        assert ph.is_optional is False
        assert ph.style is None

    @pytest.mark.parametrize(
        "placeholder,expected",
        [
            ("{{id:int}}", ("id", "int", False, False, None)),
            ("{{token?}}", ("token", "str", False, True, None)),
            ("{{page:int?}}", ("page", "int", False, True, None)),
            ("{{tags[]}}", ("tags", "str", True, False, None)),
            ("{{tags:int[]}}", ("tags", "int", True, False, None)),
            ("{{tags:int[]?}}", ("tags", "int", True, True, None)),
            ("{{tags:int[]?|csv}}", ("tags", "int", True, True, "csv")),
            ("{{tags:float[]|pipe}}", ("tags", "float", True, False, "pipe")),
            ("{{flag:bool}}", ("flag", "bool", False, False, None)),
            ("{{page-num:int?}}", ("page-num", "int", False, True, None)),
        ],
    )
    def test_parse_variants(self, placeholder, expected):
        from ssc_codegen.ast.struct import PlaceholderSpec

        ph = PlaceholderSpec.parse(placeholder)
        assert ph is not None, placeholder
        assert (
            ph.name,
            ph.type_name,
            ph.is_array,
            ph.is_optional,
            ph.style,
        ) == expected

    @pytest.mark.parametrize(
        "placeholder",
        [
            "{{_foo}}",
            "{{0foo}}",
            "{{-foo}}",
            "{{foo:unknown}}",
            "{{foo|unknown}}",
            "{{}}",
        ],
    )
    def test_invalid_placeholders_reject(self, placeholder):
        from ssc_codegen.ast.struct import PlaceholderSpec

        assert PlaceholderSpec.parse(placeholder) is None


class TestTypedPlaceholdersPyCodegen:
    def _gen(self, request_line: str) -> str:
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        module = _parse(_typed_rest_src(request_line))
        return PY_BASE_CONVERTER.convert(module, http_client="httpx")

    def test_scalar_typed_signature(self):
        code = self._gen("GET /u?id={{id:int}} HTTP/1.1")
        assert "id: int" in code

    def test_optional_has_none_default(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "q: Optional[str] = None" in code

    def test_array_annotation(self):
        code = self._gen("GET /u?tags={{tags:int[]}} HTTP/1.1")
        assert "tags: List[int]" in code

    def test_repeat_default_passes_list_native(self):
        # with repeat style (default) httpx accepts a list directly:
        # params={'tags': tags}  → ?tags=1&tags=2
        code = self._gen("GET /u?tags={{tags:int[]?}} HTTP/1.1")
        assert "'params': {'tags': tags}" in code

    def test_csv_style_joins_with_comma(self):
        code = self._gen("GET /u?tags={{tags:int[]?|csv}} HTTP/1.1")
        assert "','.join(str(_x) for _x in tags)" in code

    def test_optional_builds_params_conditionally(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "'params': {'q': q}" in code
        assert "ssc_merge_kwargs" in code

    def test_required_first_optional_last(self):
        # required 'id' must come before optional 'q' in the signature
        code = self._gen("GET /u/{{id:int}}?q={{q:str?}} HTTP/1.1")
        sig_idx = code.find("def fetch")
        sig_line = code[sig_idx : code.find("\n", sig_idx)]
        assert sig_line.find("id: int") < sig_line.find("q: Optional[str]")

    def test_kebab_name_normalised_with_suffixes(self):
        code = self._gen("GET /u?p={{page-num:int[]?|csv}} HTTP/1.1")
        # NAME renamed to snake_case but type/array/optional/style preserved
        assert "page_num: Optional[List[int]] = None" in code
        assert "','.join(str(_x) for _x in page_num)" in code

    def test_python_code_is_syntactically_valid(self):
        code = self._gen(
            "GET /u/{{id:int}}?q={{q:str?}}&tags={{tags:int[]?|csv}} HTTP/1.1"
        )
        pyast.parse(code)  # must not raise

    def test_legacy_untyped_still_str(self):
        code = self._gen("GET /u/{{id}} HTTP/1.1")
        assert "id: str" in code


class TestTypedPlaceholdersJsCodegen:
    def _gen(self, request_line: str, http_client: str = "fetch") -> str:
        from ssc_codegen.targets.javascript import JS_CONVERTER

        module = _parse(_typed_rest_src(request_line))
        return JS_CONVERTER.convert(module, http_client=http_client)

    def test_jsdoc_scalar_types(self):
        code = self._gen("GET /u?id={{id:int}}&q={{q:str?}} HTTP/1.1")
        assert "@param {number} params.id" in code
        assert "@param {string} [params.q]" in code

    def test_jsdoc_array_types(self):
        code = self._gen("GET /u?tags={{tags:int[]?}} HTTP/1.1")
        assert "@param {number[]} [params.tags]" in code

    def test_urlsearchparams_repeat_via_append(self):
        code = self._gen("GET /u?tags={{tags:int[]?}} HTTP/1.1")
        assert "params: {'tags': tags}" in code
        assert "sp.append(k, String(_v))" in code

    def test_urlsearchparams_csv_via_join(self):
        code = self._gen("GET /u?tags={{tags:int[]?|csv}} HTTP/1.1")
        assert "tags.map(String).join(',')" in code

    def test_bracket_style_rewrites_key(self):
        code = self._gen("GET /u?tags={{tags:int[]|bracket}} HTTP/1.1")
        assert "'tags[]': tags" in code

    def test_optional_conditional_set(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "params: {'q': q}" in code
        assert "if (v !== undefined && v !== null)" in code

    def test_legacy_untyped_stays_simple(self):
        code = self._gen("GET /u/{{id}} HTTP/1.1")
        cls_section = code[code.find("class API") :]
        # No params object needed for the simple path placeholder
        assert "params:" not in cls_section
        assert "${id}" in cls_section  # inline template substitution


# ---------------------------------------------------------------------------
# REST-only import elimination tests
# ---------------------------------------------------------------------------


def _mixed_src() -> str:
    """Schema with both HTML-parsing and REST structs."""
    return (
        "json User { id int; name str }\n"
        "json Err { code int; message str }\n"
        "struct HTMLPage type=item {\n"
        '    title { css "h1"; text }\n'
        "}\n"
        "struct API type=rest {\n"
        '    @request name=get-user response=User """\n'
        "    GET /users/{{id}} HTTP/1.1\n"
        "    Host: api.example.com\n"
        '    """\n'
        "}\n"
    )


class TestRestOnlyImports:
    """Verify HTML library imports are skipped for REST-only modules."""

    @pytest.mark.parametrize(
        "converter_attr,html_import",
        [
            ("PY_BASE_CONVERTER", "from bs4 import"),
            ("PY_LXML_CONVERTER", "from lxml import"),
            ("PY_PARSEL_CONVERTER", "from parsel import"),
            ("PY_SLAX_CONVERTER", "from selectolax.lexbor import"),
        ],
    )
    def test_rest_only_no_html_import(self, converter_attr, html_import):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER,
            PY_LXML_CONVERTER,
            PY_PARSEL_CONVERTER,
            PY_SLAX_CONVERTER,
        )

        converters = {
            "PY_BASE_CONVERTER": PY_BS4_CONVERTER,
            "PY_LXML_CONVERTER": PY_LXML_CONVERTER,
            "PY_PARSEL_CONVERTER": PY_PARSEL_CONVERTER,
            "PY_SLAX_CONVERTER": PY_SLAX_CONVERTER,
        }
        converter = converters[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = converter.convert(module, http_client="httpx")
        assert html_import not in code
        assert "_html_unescape" not in code
        assert "std_unescape_text" not in code
        assert "std_normalize_text" not in code
        assert "std_repl_map" not in code
        assert "UnmatchedTableRow" not in code
        assert "UNMATCHED_TABLE_ROW" not in code
        assert "_RE_HEX_ENTITY" not in code

    def test_mixed_module_keeps_html_imports(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        src = _mixed_src()
        module = _parse(src)
        code = PY_BASE_CONVERTER.convert(module, http_client="httpx")
        assert "from bs4 import" in code
        assert "BS4_FEATURES" in code
        assert "UNMATCHED_TABLE_ROW" in code


# ---------------------------------------------------------------------------
# Separate runtime (-R) tests
# ---------------------------------------------------------------------------


_NOT_REQUIRED_COMPAT_IMPORT = (
    "if sys.version_info >= (3, 11):\n"
    "    from typing import NotRequired\n"
    "else:\n"
    "    from typing_extensions import NotRequired"
)


class TestSeparateRuntime:
    """Verify -R (separate runtime) works correctly for all Python targets."""

    RUNTIME_NAME = "sscgen_runtime"

    def test_separate_runtime_rest_codegen_and_imports(self):
        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(
            PY_BS4_CONVERTER,
            self.RUNTIME_NAME,
            http_strategy=HttpxStrategy(),
        )
        generated = PY_BS4_CONVERTER.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        code = generated[""]
        runtime = generated[f"{self.RUNTIME_NAME}.py"]

        # Runtime file helpers & imports
        assert "class Ok(Generic[_T]):" in runtime
        assert "class Err(Generic[_E]):" in runtime
        assert "class UnknownErr(Err[Any]):" in runtime
        assert "class TransportErr(Err[None]):" in runtime
        assert "def ssc_rest_call(" in runtime
        assert "import httpx" in runtime

        # Main parser file imports from runtime & no redundant inline definitions
        assert f"from .{self.RUNTIME_NAME} import" in code
        assert "Ok" in code.split(f"from .{self.RUNTIME_NAME} import")[1]
        assert "class Ok(Generic[_T]):" not in code
        assert "class Err(Generic[_E]):" not in code
        assert "def ssc_rest_call(" not in code
        assert "def ssc_dispatch_err(" not in code
        for runtime_only in ("Generic", "TypeVar", "Mapping", "Callable"):
            assert runtime_only not in code

        # Required imports present in parser under -R
        assert "import sys" in code
        assert "from typing import" in code
        assert "TypedDict" in code
        assert _NOT_REQUIRED_COMPAT_IMPORT in code
        assert "from dataclasses import dataclass" in code
        assert "from typing import Literal" in code
        assert "import httpx" in code
        assert "Literal[404]" in code

        # Both files parse & execute cleanly
        pyast.parse(code)
        pyast.parse(runtime)
        exec(compile(runtime, "<rt>", "exec"), {})
        _exec_with_runtime(code, runtime)

    def test_combined_rest_and_html_module_under_runtime(self):
        """Regression for the cdnvideohub / kodik / aniboom anicli-api case:
        a single .kdl file with both a ``type=rest`` struct and an HTML
        struct. Under -R the parser file must keep lxml imports, the
        FALLBACK_HTML_STR import from runtime, AND httpx/typing/dataclass
        imports for the REST struct.
        """
        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python import PY_LXML_CONVERTER

        src = (
            "json Err { detail str }\n"
            "json Resp { id str }\n"
            "struct Page type=rest {\n"
            '    @request response=Resp """\n'
            "    GET /api/{{id}} HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "    @error 404 Err\n"
            "}\n"
            'struct Body { title { css "h1"; text } }\n'
        )
        module = _parse(src)
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy

        register_runtime_file(
            PY_LXML_CONVERTER,
            self.RUNTIME_NAME,
            include_fallback=True,
            http_strategy=HttpxStrategy(),
        )
        generated = PY_LXML_CONVERTER.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        code = generated[""]
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        # All import surfaces covered.
        assert "from lxml import html" in code
        assert "from lxml.html import HtmlElement" in code
        assert "from dataclasses import dataclass" in code
        assert "from typing import Literal" in code
        assert "import httpx" in code
        assert f"from .{self.RUNTIME_NAME} import" in code
        assert "FALLBACK_HTML_STR" in code  # in the runtime import list
        # Round-trip exec: runtime first, then parser with runtime injected.
        _exec_with_runtime(code, runtime)

    @pytest.mark.parametrize(
        "http_client, expected_strategy, expected_import",
        [
            (None, "HttpxStrategy", "fallback"),
            ("httpx", "HttpxStrategy", "fallback"),
            ("httpx2", "Httpx2Strategy", "import httpx2"),
            ("aiohttp", "AioHttpStrategy", "import aiohttp"),
            ("requests", "RequestsStrategy", "import requests"),
            ("<bogus>", "HttpxStrategy", "fallback"),  # fallback to default
        ],
    )
    def test_http_strategy_for_returns_correct_default(
        self, http_client, expected_strategy, expected_import
    ):
        """``PythonVisitor.http_strategy_for`` is the single resolver for
        which HTTP strategy applies given user input. Default is httpx;
        unknown values fall back to httpx instead of crashing.
        """
        from ssc_codegen.targets.python.http_libs.aiohttp import AioHttpStrategy
        from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
        from ssc_codegen.targets.python.http_libs.httpx import (
            HTTPX_FALLBACK_IMPORT,
            Httpx2Strategy,
            HttpxStrategy,
        )
        from ssc_codegen.targets.python.http_libs.requests import (
            RequestsStrategy,
        )
        from ssc_codegen.targets.python.visitor import PythonVisitor

        strategy = PythonVisitor.http_strategy_for(http_client)
        type_map = {
            "HttpxStrategy": HttpxStrategy,
            "Httpx2Strategy": Httpx2Strategy,
            "AioHttpStrategy": AioHttpStrategy,
            "RequestsStrategy": RequestsStrategy,
        }
        assert isinstance(strategy, type_map[expected_strategy])
        assert isinstance(strategy, HttpLibStrategy)
        if expected_import == "fallback":
            assert strategy.import_line == HTTPX_FALLBACK_IMPORT
        else:
            assert strategy.import_line == expected_import

    def test_runtime_file_imports_httpx_when_http_client_is_none(self):
        """Regression for the main.py integration bug: when user runs
        ``ssc-gen generate ... -R`` WITHOUT ``--http-client``, ``http_client``
        is ``None``. Pre-fix main.py gated strategy resolution behind
        ``if http_client:`` so ``transport_import_line`` stayed ``None`` and
        the runtime file (which references ``httpx.HTTPError`` in
        ``ssc_rest_call``) lacked ``import httpx`` entirely → NameError at
        the first transport exception.

        The parser file already received ``import httpx`` via the visitor's
        default ``HttpxStrategy()``; the runtime file did not. This test
        pins that both paths now go through ``http_strategy_for`` and
        produce consistent output.
        """
        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python.visitor import PythonVisitor

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        # Emulate main.py: resolve HTTP strategy via the shared resolver
        # without explicitly passing http_client.
        strategy = PythonVisitor.http_strategy_for(None)
        register_runtime_file(
            PY_BS4_CONVERTER,
            self.RUNTIME_NAME,
            http_strategy=strategy,
        )
        # Also do not pass http_client to convert_all — emulates the user
        # not passing --http-client on the CLI.
        generated = PY_BS4_CONVERTER.convert_all(
            module,
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        parser = generated[""]
        # Both files must reference httpx consistently.
        assert "import httpx" in runtime, (
            "runtime file missing import httpx — main.py integration bug"
        )
        assert "import httpx" in parser
        # Runtime must be executable in isolation.
        exec(compile(runtime, "<rt>", "exec"), {})

    @pytest.mark.parametrize(
        "http_client, expected_import",
        [
            ("httpx", "import httpx"),
            ("httpx2", "import httpx2"),
            ("aiohttp", "import aiohttp"),
            ("requests", "import requests"),
        ],
    )
    def test_runtime_file_strategy_matches_http_client_override(
        self, http_client, expected_import
    ):
        """``main.py`` resolves the HTTP strategy via
        ``PythonVisitor.http_strategy_for(http_client)`` and passes the whole
        strategy to ``register_runtime_file``. The strategy owns both the
        transport import line and the REST runtime source — single source
        of truth, no drift between parser and runtime.
        """
        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python import PY_LXML_CONVERTER
        from ssc_codegen.targets.python.visitor import PythonVisitor

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        strategy = PythonVisitor.http_strategy_for(http_client)
        register_runtime_file(
            PY_LXML_CONVERTER,
            self.RUNTIME_NAME,
            http_strategy=strategy,
        )
        generated = PY_LXML_CONVERTER.convert_all(
            module,
            http_client=http_client,
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        parser = generated[""]
        assert expected_import in runtime
        assert expected_import in parser

    def test_html_only_module_with_fetch_imports_httpx(self):
        """Regression: HTML-only module with a ``fetch`` shortcut method
        emits ``def fetch(cls, client: httpx.Client, ...)`` in the parser
        file. Pre-fix the visitor gated ``import httpx`` behind
        ``module_has_rest`` which is False for HTML structs, causing
        ``NameError: name 'httpx' is not defined`` at class definition
        time on the consumer side.

        ``module_uses_http`` is the broader gate that covers both REST
        structs and any struct with a MethodFetch / MethodRest in its body.
        """
        src = (
            "struct Page {\n"
            '    title { css "h1"; text }\n'
            '    @request """\n'
            "    GET / HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        generated = PY_BS4_CONVERTER.convert_all(module)
        code = generated[""]
        assert "def fetch" in code
        assert "client: httpx.Client" in code
        assert "import httpx" in code
        from ssc_codegen.targets.python.http_libs.httpx import (
            HTTPX_FALLBACK_IMPORT,
        )

        assert HTTPX_FALLBACK_IMPORT in code

    def test_html_only_module_with_fetch_imports_httpx2(self):
        """HTML-only module with a fetch method under httpx2 emits strict
        import httpx2 and client: httpx2.Client signatures.
        """
        src = (
            "struct Page {\n"
            '    title { css "h1"; text }\n'
            '    @request """\n'
            "    GET / HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        generated = PY_BS4_CONVERTER.convert_all(module, http_client="httpx2")
        code = generated[""]
        assert "def fetch" in code
        assert "client: httpx2.Client" in code
        assert "client: httpx2.AsyncClient" in code
        assert "import httpx2" in code
        assert "import httpx\n" not in code

    def test_httpx_fallback_separate_runtime_roundtrip(self, monkeypatch):
        """End-to-end code generation and runtime execution for httpx (fallback).
        Verifies both fallback execution paths:
        1. When httpx2 is not present, ImportError falls back to httpx.
        2. When httpx2 is present in sys.modules, import httpx2 as httpx succeeds.
        """
        import sys

        import httpx

        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python import PY_LXML_CONVERTER
        from ssc_codegen.targets.python.http_libs.httpx import (
            HTTPX_FALLBACK_IMPORT,
        )
        from ssc_codegen.targets.python.visitor import PythonVisitor

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        strategy = PythonVisitor.http_strategy_for("httpx")
        register_runtime_file(
            PY_LXML_CONVERTER,
            self.RUNTIME_NAME,
            http_strategy=strategy,
        )
        generated = PY_LXML_CONVERTER.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        parser = generated[""]

        assert HTTPX_FALLBACK_IMPORT in runtime
        assert HTTPX_FALLBACK_IMPORT in parser
        assert "client: httpx.Client" in parser
        assert "client: httpx.AsyncClient" in parser
        assert "client: httpx.Client" in runtime
        assert "client: httpx.AsyncClient" in runtime
        assert "except httpx.HTTPError as exc:" in runtime

        # Path 1: httpx2 is not installed -> executes via fallback to httpx
        ns = _exec_with_runtime(parser, runtime)
        assert "API" in ns

        # Path 2: httpx2 is installed/mocked -> executes via import httpx2 as httpx
        monkeypatch.setitem(sys.modules, "httpx2", httpx)
        ns2 = _exec_with_runtime(parser, runtime)
        assert "API" in ns2

    def test_matcher_list_has_type_annotation(self):
        """Empty matcher list must carry an explicit type annotation,
        otherwise mypy raises ``var-annotated`` on the consumer side.
        """
        from ssc_codegen.targets.python import PY_LXML_CONVERTER

        # Struct with @error but no required_keys → ErrMatcher with empty
        # check; struct without @error → empty matchers list.
        src = (
            "json Err { detail str }\n"
            "json Resp { id str }\n"
            "struct Page type=rest {\n"
            '    @request response=Resp """\n'
            "    GET /api HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        code = PY_LXML_CONVERTER.convert(module, http_client="httpx")
        assert ": List[ErrMatcher] = [" in code

    def test_parser_wraps_rest_call_in_cast(self):
        """Parser ``fetch``/``async_fetch``/``<method>`` return values
        are wrapped in ``cast(<ResultAlias>, ssc_rest_call(...))``.

        ssc_rest_call returns ``Union[Ok[_T], Err]`` (Err base) — honest
        about runtime dispatch but mypy-incompatible with the parser's
        specific result union (Err400 | UnknownErr | ...). cast()
        documents the intent at the call site without suppressing mypy
        via ``# type: ignore``; consumer code sees the stable monad
        annotation declared on the wrapping method.
        """
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = PY_BS4_CONVERTER.convert(module, http_client="httpx")
        # ``from typing import cast`` added to imports when has_rest.
        assert "from typing import cast" in code
        # Every rest method body uses cast() wrapping.
        assert "return cast(" in code
        # The cast target is the parser's result alias (monad union).
        # _rest_src produces struct "API" with method "get_user", so the
        # alias is GetUserResult. The cast spans multiple lines:
        #     return cast(
        #         GetUserResult,
        #     ssc_rest_call(...
        assert "GetUserResult," in code

    def test_ref_ast_picks_rest_module(self):
        """The ref_ast selection must not crash on modules with non-REST structs."""
        from ssc_codegen.generation.runtime import register_runtime_file

        non_rest_src = 'struct Item { field_name { css "div" } }'
        module = _parse(non_rest_src)
        register_runtime_file(PY_BS4_CONVERTER, self.RUNTIME_NAME)
        PY_BS4_CONVERTER.convert_all(module, runtime_module=self.RUNTIME_NAME)


# ---------------------------------------------------------------------------
# Placeholder linting in @request
# ---------------------------------------------------------------------------


class TestRequestPlaceholderLint:
    """Verify lint catches uppercase/malformed placeholders in @request."""

    @staticmethod
    def _lint(src: str):
        _, diagnostics = parse_module(src)
        return [d for d in diagnostics if d.severity == Severity.ERROR]

    def test_uppercase_placeholder_in_inline_request(self):
        src = (
            "struct S {\n"
            '    @request """\n'
            "    GET /search?q={{QUERY}} HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        assert len(errors) == 1
        assert "{{QUERY}}" in errors[0].message
        assert "must be lowercase" in errors[0].message

    def test_lowercase_placeholder_no_error(self):
        src = (
            "struct S {\n"
            '    @request """\n'
            "    GET /search?q={{query}} HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        assert not errors

    def test_mixed_upper_and_lower_flags_uppercase(self):
        src = (
            "struct S {\n"
            '    @request """\n'
            "    POST /api HTTP/1.1\n"
            "    Host: example.com\n"
            "    Content-Type: application/json\n"
            "\n"
            '    {"q": "{{query}}", "token": "{{TOKEN}}"}\n'
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        assert len(errors) == 1
        assert "{{TOKEN}}" in errors[0].message

    def test_define_with_resolved_uppercase_and_lowercase_runtime(self):
        """define resolves {{BASE-URL}} at parse time; only {{query}} remains."""
        src = (
            'define BASE-URL="https://example.com"\n'
            'define REQ="curl {{BASE-URL}}/search?q={{query}}"\n'
            "(list)struct S {\n"
            '    @split-doc { css-all ".item" }\n'
            "    @request REQ\n"
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        assert not errors

    def test_no_placeholders_no_error(self):
        src = (
            "struct S {\n"
            '    @request """\n'
            "    GET /page HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        assert not errors


# ---------------------------------------------------------------------------
# response-path / response-join linting on @request (Patch B)
# ---------------------------------------------------------------------------


class TestResponsePathLint:
    """Verify lint catches malformed response-path and response-join misuse.

    Patch B invariants:
    - response-path format: dot-notation, non-empty ASCII identifier segments
    - response-join forbidden on type=rest (Ok.value is extracted object)
    - response-join without response-path is meaningless
    """

    @staticmethod
    def _lint(src: str):
        _, diagnostics = parse_module(src)
        return [d for d in diagnostics if d.severity == Severity.ERROR]

    def test_valid_path_no_error_rest(self):
        src = (
            "json User { id int }\n"
            "struct API type=rest {\n"
            '    @request response=User response-path="data.user" """\n'
            "    GET /me HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        assert not self._lint(src)

    def test_valid_path_no_error_fetch(self):
        src = (
            "struct Page {\n"
            '    @request response-path="payload.html" """\n'
            "    GET /page HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        assert not self._lint(src)

    @pytest.mark.parametrize(
        "bad_path",
        [
            "data..user",  # empty segment
            ".data",  # leading dot
            "data.",  # trailing dot
            "data user",  # space (non-identifier)
        ],
    )
    def test_malformed_path_e001(self, bad_path):
        src = (
            "json User { id int }\n"
            "struct API type=rest {\n"
            f'    @request response=User response-path="{bad_path}" """\n'
            "    GET /me HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        errors = self._lint(src)
        assert len(errors) == 1
        assert errors[0].code == "E001"
        assert "response-path" in errors[0].message

    def test_response_join_forbidden_on_rest(self):
        src = (
            "json Log { line str }\n"
            "struct API type=rest {\n"
            '    @request response=Log response-path="lines" '
            'response-join="\\n" """\n'
            "    GET /log HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        errors = self._lint(src)
        join_errs = [e for e in errors if "response-join" in e.message]
        assert len(join_errs) == 1
        assert "forbidden" in join_errs[0].message

    def test_response_join_allowed_on_fetch(self):
        src = (
            "struct Page {\n"
            '    @request response-path="lines" response-join="\\n" """\n'
            "    GET /page HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        assert not self._lint(src)

    def test_response_join_without_path_e001(self):
        src = (
            "struct Page {\n"
            '    @request response-join="\\n" """\n'
            "    GET /page HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        errors = self._lint(src)
        join_errs = [e for e in errors if "response-join" in e.message]
        assert len(join_errs) == 1
        assert "requires response-path" in join_errs[0].message


class TestResponsePathCodegen:
    """Converter-level asserts: response-path emits value_fn/accessor that
    extracts the sub-object before Ok.value is constructed.

    Priority rule: when both response-path AND response-schema are set on
    a (rest)struct, path wins — the schema type-checks the *extracted*
    sub-object, not the whole envelope.
    """

    @staticmethod
    def _rest_path_src(path: str = "data.user") -> str:
        return (
            "json User { id int; name str }\n"
            "struct API type=rest {\n"
            f'    @request response=User response-path="{path}" """\n'
            "    GET /me HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )

    def test_py_path_dominates_over_void_when_no_schema(self):
        """response-path with no response-schema still emits value_fn
        (path wins over the old `void → lambda _: None` branch)."""
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = (
            "struct API type=rest {\n"
            '    @request response-path="status" """\n'
            "    GET /ping HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "value_fn=lambda _b: _b['status']," in code
        # Old void path must NOT fire when response_path is set.
        assert "value_fn=lambda _: None," not in code

    def test_js_emits_value_fn_accessor(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        module = _parse(self._rest_path_src())
        code = JS_CONVERTER.convert(module, http_client="fetch")
        # JS uses double-quoted JSON-style keys and projects into User schema
        assert '(_b) => _projectUser(_b["data"]["user"])' in code

    def test_js_void_without_path_emits_null(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = (
            "struct API type=rest {\n"
            '    @request """\n'
            "    GET /ping HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "(_b) => null" in code

    def test_go_emits_gjson_extraction(self):
        from ssc_codegen.targets.golang import GO_CONVERTER

        module = _parse(self._rest_path_src())
        code = GO_CONVERTER.convert(module)
        runtime = GO_CONVERTER.emit_runtime("main")
        assert (
            'sscRestCallValue[UserJson](client, apiMatchers, "GET", "https://api.example.com/me", "data.user", nil, opts...)'
            in code
        )
        # sscExtractJSONSlice narrows raw body via gjson.GetBytes(raw, responsePath).Raw before Unmarshal
        assert "sscExtractJSONSlice" in runtime
        assert "gjson.GetBytes(raw, responsePath).Raw" in runtime

    def test_go_rest_accepts_opts(self):
        """Go REST methods accept variadic ``opts ...sscReqOpt``."""
        from ssc_codegen.targets.golang import GO_CONVERTER

        module = _parse(self._rest_path_src())
        code = GO_CONVERTER.convert(module)
        runtime = GO_CONVERTER.emit_runtime("main")
        assert "opts ...sscReqOpt" in code
        assert "opts...)" in code
        assert "for _, o := range opts {" in runtime
        assert "o(_opts)" in runtime

    def test_go_rest_namespaces_via_receiver_and_factory(self):
        """Go REST codegen: empty struct + New<Name>() factory +
        receiver method namespaced by type.

        Without the receiver pattern, two REST structs in the same Go
        package would emit conflicting package-level ``Fetch`` functions.
        """
        from ssc_codegen.targets.golang import GO_CONVERTER

        module = _parse(self._rest_path_src())
        code = GO_CONVERTER.convert(module)
        # Empty marker struct.
        assert "type API struct {" in code
        # Zero-cost factory on the empty struct.
        assert "func NewAPI() API { return API{} }" in code
        # Receiver method — namespaced by type, not a free function.
        assert "func (a API) Fetch(" in code
        # The free-function form (the bug) must be gone.
        assert "\nfunc Fetch(" not in code

    def test_go_html_fetch_uses_newstruct_prefix(self):
        """Go HTML @request codegen: free function ``New<Struct>Fetch``.

        Struct-name prefix guarantees uniqueness across schemas in the
        same package (collision regression). Existing ``New<Struct>(input)``
        constructor for HTML parsing is left untouched.
        """
        from ssc_codegen.targets.golang import GO_CONVERTER

        src = (
            "struct Page {\n"
            '    @request """\n'
            "    GET / HTTP/1.1\n"
            "    Host: example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        module = _parse(src)
        code = GO_CONVERTER.convert(module)
        # HTML constructor for direct string input is preserved.
        assert "func NewPage(input string) (*Page, error)" in code
        # HTTP-entry constructor is namespaced by struct name.
        assert "func NewPageFetch(ctx context.Context" in code
        # Custom @request name=LoadPage → NewPageLoadPage.
        # (smoke: just verify default case here.)

    def test_go_array_query_styles(self):
        from ssc_codegen.targets.golang import GO_CONVERTER

        src = (
            "json R { x int }\n"
            "struct API type=rest {\n"
            '    @request response=R """\n'
            "    GET /items?tags={{tags:int[]}}&ids={{ids:int[]|csv}} HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )

        code = GO_CONVERTER.convert(_parse(src))

        assert "for _, _value := range tags" in code
        assert '_values.Add("tags", fmt.Sprint(_value))' in code
        assert "for _i, _value := range ids" in code
        assert 'strings.Join(_idsParts, ",")' in code

    def test_go_error_matcher_combines_keys_conditions_and_float(self):
        from ssc_codegen.targets.golang import GO_CONVERTER

        src = _rest_src(
            errors='    @error 404 Err error detail="msg" score=1.5\n'
        )
        code = GO_CONVERTER.convert(_parse(src))

        assert 'gjson.GetBytes(_b, "error").Exists()' in code
        assert 'gjson.GetBytes(_b, "detail").String() == "msg"' in code
        assert 'gjson.GetBytes(_b, "score").Float() == 1.5' in code

    def test_go_html_fetch_params_and_cookies(self):
        """Go HTML @request with query params + cookies in the same struct.

        Params are rendered as ``url.Values{...}.Encode()`` appended to the
        URL. Cookies are passed via ``sscReqOpts.Cookies`` and applied in
        the runtime via ``req.AddCookie``.
        Placeholders in cookie values interpolate via ``fmt.Sprintf``.
        """
        from ssc_codegen.targets.golang import GO_CONVERTER

        src = (
            "struct Page {\n"
            '    @request """\n'
            "    GET /p?id={{id:int}} HTTP/1.1\n"
            "    Host: h.example.com\n"
            "    Cookie: session=abc; tracking={{tid}}\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )
        module = _parse(src)
        code = GO_CONVERTER.convert(module)
        runtime = GO_CONVERTER.emit_runtime("main")
        # Query string built via url.Values.
        assert 'url.Values{"id": []string{fmt.Sprintf("%d", id)}' in code
        # Plain cookie literal and placeholder cookie in sscReqOpts.Cookies.
        assert '"session": []string{"abc"}' in code
        assert '"tracking": []string{fmt.Sprintf("%s", tid)}' in code
        assert "req.AddCookie(&http.Cookie{Name: name, Value: v})" in runtime
        # net/url import required for url.Values.
        assert '"net/url"' in code


# ---------------------------------------------------------------------------
# Ticket 01: @error:<suffix> variant naming, leaf-key auto-naming cap, E400
# ---------------------------------------------------------------------------


class TestErrorSuffixNamingAndCollisionLint:
    """Tests for `@error:<suffix>`, leaf-key auto-naming cap, and `E400` collision lint."""

    def test_explicit_error_suffix_parses_and_generates_across_all_targets(
        self,
    ):
        from ssc_codegen.targets.golang import GO_CONVERTER
        from ssc_codegen.targets.javascript import JS_CONVERTER
        from ssc_codegen.targets.python import PY_BS4_CONVERTER
        from ssc_codegen.targets.rust import RUST_CONVERTER

        src = (
            "json User { id int }\n"
            "json ResponseError { error str }\n"
            "struct AnimeVostAPI type=rest {\n"
            '    @error:not-found 404 ResponseError error="Ничего не найдено" extra="ignored"\n'
            '    @error 404 ResponseError "error"\n'
            '    @request name=get-user response=User """\n'
            "    GET /users/{{id:int}} HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        module, diags = parse_module(src)
        assert not any(d.severity == Severity.ERROR for d in diags), diags

        struct = next(n for n in module.body if isinstance(n, StructRest))
        errors = struct.errors
        assert len(errors) == 2
        assert errors[0].suffix == "not-found"
        assert errors[1].suffix == ""

        py_code = PY_BS4_CONVERTER.convert(module, http_client="httpx")
        assert (
            "class AnimeVostAPIErr404NotFound(Err[ResponseErrorJson]):"
            in py_code
        )
        assert (
            "class AnimeVostAPIErr404Error(Err[ResponseErrorJson]):" in py_code
        )
        assert "AnimeVostAPIErr404NotFound, AnimeVostAPIErr404Error" in py_code

        js_code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "@typedef {Object} AnimeVostAPIErr404NotFound" in js_code
        assert "@typedef {Object} AnimeVostAPIErr404Error" in js_code
        assert (
            "Ok<UserJson> | AnimeVostAPIErr404NotFound | AnimeVostAPIErr404Error"
            in js_code
        )

        go_code = GO_CONVERTER.convert(module)
        assert "type AnimeVostAPIErr404NotFound struct {" in go_code
        assert "type AnimeVostAPIErr404Error struct {" in go_code

        rust_code = RUST_CONVERTER.convert(module)
        assert "Err404NotFound(ResponseErrorJson)," in rust_code
        assert "Err404Error(ResponseErrorJson)," in rust_code
        assert (
            "pub type AnimeVostAPIErr404NotFound = ResponseErrorJson;"
            in rust_code
        )
        assert (
            "pub type AnimeVostAPIErr404Error = ResponseErrorJson;" in rust_code
        )

    def test_auto_naming_extracts_leaf_non_numeric_segment_and_caps_at_two_keys(
        self,
    ):
        from ssc_codegen.targets.golang import GO_CONVERTER
        from ssc_codegen.targets.javascript import JS_CONVERTER
        from ssc_codegen.targets.python import PY_BS4_CONVERTER
        from ssc_codegen.targets.rust import RUST_CONVERTER

        src = _rest_src(
            errors=(
                '    @error 404 Err "data.response.errors.0.detail"\n'
                '    @error 400 Err "a.b.first" second="x" third="y"\n'
                '    @error 422 Err "data.errors.0"\n'
            )
        )
        module = _parse(src)

        py_code = PY_BS4_CONVERTER.convert(module, http_client="httpx")
        assert "class APIErr404Detail(Err[ErrJson]):" in py_code
        assert "class APIErr400FirstSecond(Err[ErrJson]):" in py_code
        assert "APIErr400FirstSecondThird" not in py_code
        assert "class APIErr422Errors(Err[ErrJson]):" in py_code

        js_code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "@typedef {Object} APIErr404Detail" in js_code
        assert "@typedef {Object} APIErr400FirstSecond" in js_code
        assert "APIErr400FirstSecondThird" not in js_code

        go_code = GO_CONVERTER.convert(module)
        assert "type APIErr404Detail struct {" in go_code
        assert "type APIErr400FirstSecond struct {" in go_code

        rust_code = RUST_CONVERTER.convert(module)
        assert "Err404Detail(ErrJson)," in rust_code
        assert "Err400FirstSecond(ErrJson)," in rust_code

    @pytest.mark.parametrize(
        "directive",
        [
            "@error:",
            "@error:123bad",
            "@error:-bad",
            "@error:bad.name",
        ],
    )
    def test_malformed_error_suffix_emits_e002(self, directive: str):
        _, diags = parse_module(_rest_src(errors=f"    {directive} 404 Err\n"))
        errs = [d for d in diags if d.severity == Severity.ERROR]
        assert any(
            d.code == "E002"
            and "@error:<name> <status> <Schema>" in (d.hint or "")
            for d in errs
        ), errs

    def test_suffixed_error_enforces_struct_type_args_status_duplicates_and_e300(
        self,
    ):
        # 1. Forbidden outside (rest)struct -> E203
        _, diags_item = parse_module(
            'json Err { code int }\nstruct Page {\n    @error:not-found 404 Err\n    title { css "h1"; text }\n}\n'
        )
        assert any(d.code == "E203" for d in diags_item), diags_item

        # 2. Missing arguments -> E001
        _, diags_args = parse_module(
            _rest_src(errors="    @error:not-found 404\n")
        )
        assert any(d.code == "E001" for d in diags_args), diags_args

        # 3. Invalid HTTP status range -> E002
        _, diags_status = parse_module(
            _rest_src(errors="    @error:not-found 999 Err\n")
        )
        assert any(
            d.code == "E002" and "100..599" in d.message for d in diags_status
        ), diags_status

        # 4. Duplicate positional & property keys -> E400
        _, diags_dup_key = parse_module(
            _rest_src(errors='    @error:not-found 404 Err code code="x"\n')
        )
        assert any(
            d.code == "E400" and "duplicate keys" in d.message
            for d in diags_dup_key
        ), diags_dup_key

        # 5. Undefined schema -> E300
        _, diags_e300 = parse_module(
            _rest_src(errors="    @error:not-found 404 MissingSchema\n")
        )
        assert any(
            d.code == "E300" and "MissingSchema" in d.message
            for d in diags_e300
        ), diags_e300

    def test_suffixed_error_resolves_cross_file_schema_import(self, tmp_path):
        shared = tmp_path / "shared.kdl"
        shared.write_text("json SharedErr { message str }\n", encoding="utf-8")
        main = tmp_path / "main.kdl"
        main_src = (
            'import "./shared.kdl" { (json)SharedErr }\n'
            "json User { id int }\n"
            "struct API type=rest {\n"
            "    @error:not-found 404 SharedErr\n"
            '    @request name=get-user response=User """\n'
            "    GET /users/{{id:int}} HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        main.write_text(main_src, encoding="utf-8")
        module, diags = parse_module(main_src, source_path=main)
        assert not any(d.severity == Severity.ERROR for d in diags), diags
        struct = next(n for n in module.body if isinstance(n, StructRest))
        assert len(struct.errors) == 1
        assert struct.errors[0].suffix == "not-found"
        assert struct.errors[0].schema_name == "SharedErr"

    def test_duplicate_error_variant_name_collision_emits_e400(self):
        src = _rest_src(
            errors=(
                '    @error 404 Err error="Ничего не найдено"\n'
                '    @error 404 Err "error"\n'
            )
        )
        _, diags = parse_module(src)
        errs = [d for d in diags if d.severity == Severity.ERROR]
        assert len(errs) == 1
        assert errs[0].code == "E400"
        assert "APIErr404Error" in errs[0].message
        assert "@error:<name> <status> <Schema>" in (errs[0].hint or "")

        # Collision from 2-key cap also emits E400
        src_cap = _rest_src(
            errors=(
                '    @error 400 Err a b c="1"\n    @error 400 Err a b d="2"\n'
            )
        )
        _, diags_cap = parse_module(src_cap)
        errs_cap = [d for d in diags_cap if d.severity == Severity.ERROR]
        assert len(errs_cap) == 1
        assert errs_cap[0].code == "E400"
        assert "APIErr400AB" in errs_cap[0].message


# ---------------------------------------------------------------------------
# Ticket 02: Dot-path positional key checks & safe ErrMatcher fallthrough
# ---------------------------------------------------------------------------


class TestDotPathPositionalKeysAndSafeFallthroughCodegen:
    """Tests for Python and JS dot-path positional key checks and safe fallthrough via public converters."""

    def test_py_dotpath_positional_key_codegen_and_safe_evaluation(self):
        from ssc_codegen.targets.python import PY_BS4_CONVERTER

        src = _rest_src(
            errors=(
                '    @error 404 Err "error"\n'
                '    @error 400 Err detail="msg"\n'
                '    @error 200 Err "error.code"\n'
                '    @error 422 Err "data.errors.0.detail"\n'
            )
        )
        code = PY_BS4_CONVERTER.convert(_parse(src), http_client="httpx")

        assert "lambda _b: 'error' in _b" in code
        assert "lambda _b: _b.get('detail') == 'msg'" in code
        assert (
            "lambda _b: (_v1.get('code') if isinstance(_v1 := (_b.get('error') if isinstance(_b, dict) else None), dict) else None) is not None"
            in code
        )
        assert "if body is None or not isinstance(body, (dict, list)):" in code
        assert "except Exception:\n            return None" in code

        ns: dict = {}
        exec(compile(code, "<py_dotpath>", "exec"), ns)
        matchers = ns["API_MATCHERS"]
        dot_check = next(m.check for m in matchers if m.status == 200)
        assert dot_check is not None
        assert dot_check({"error": {"code": 123}}) is True
        assert dot_check({"error": {"code": 0}}) is True
        assert dot_check({"error": {}}) is False
        assert dot_check({}) is False
        assert dot_check({"error": None}) is False
        assert dot_check({"error": "scalar"}) is False
        assert dot_check({"error": [1, 2]}) is False

        deep_check = next(m.check for m in matchers if m.status == 422)
        assert deep_check is not None
        assert deep_check({"data": {"errors": [{"detail": "bad"}]}}) is True
        assert deep_check({"data": {"errors": [{}]}}) is False
        assert deep_check({"data": {"errors": []}}) is False
        assert deep_check({"data": {"errors": "not-a-list"}}) is False
        assert deep_check({"data": {"errors": [None]}}) is False
        assert deep_check({}) is False
