"""Tests for REST API struct support (struct type=rest).

Covers:
- Parser: StructType.REST, @request on REST, @error parsing
- Linter: REST-specific rule validation
- Converters: py_bs4 and js_pure code generation
"""

from __future__ import annotations

import ast as pyast

import pytest

from ssc_codegen.ast import (
    ErrorResponse,
    RequestConfig,
    Struct,
)
from ssc_codegen.ast.types import StructType
from ssc_codegen.linter.format_errors import lint_string
from ssc_codegen.parser import PARSER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lint_messages(src: str) -> list[str]:
    return [e.message for e in lint_string(src).errors]


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


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestRestParser:
    def test_rest_struct_type(self):
        module = PARSER.parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, Struct))
        assert struct.struct_type == StructType.REST
        assert struct.is_rest is True

    def test_request_config_name_and_response(self):
        module = PARSER.parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, Struct))
        reqs = [n for n in struct.body if isinstance(n, RequestConfig)]
        assert len(reqs) == 1
        assert reqs[0].name == "get-user"
        assert reqs[0].response_schema == "User"

    def test_error_response_parsed(self):
        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = PARSER.parse(src)
        struct = next(n for n in module.body if isinstance(n, Struct))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert len(errors) == 2
        assert errors[0].status == 404
        assert errors[0].schema_name == "Err"
        assert errors[0].discriminator_field is None
        assert errors[1].status == 500

    def test_error_with_discriminator_field(self):
        src = _rest_src(errors='    @error 200 field="error_code" Err\n')
        module = PARSER.parse(src)
        struct = next(n for n in module.body if isinstance(n, Struct))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert errors[0].status == 200
        assert errors[0].discriminator_field == "error_code"

    def test_no_start_parse_for_rest(self):
        from ssc_codegen.ast import StartParse

        module = PARSER.parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, Struct))
        assert not any(isinstance(n, StartParse) for n in struct.body)


# ---------------------------------------------------------------------------
# Linter tests
# ---------------------------------------------------------------------------


class TestRestLinter:
    def test_valid_rest_struct_no_errors(self):
        msgs = _lint_messages(_rest_src(errors="    @error 404 Err\n"))
        assert msgs == []

    def test_multiple_requests_require_name(self):
        src = (
            "json User { id int }\n"
            "struct API type=rest {\n"
            '    @request response=User """\n'
            "    GET /a HTTP/1.1\n"
            "    Host: x.com\n"
            '    """\n'
            '    @request response=User """\n'
            "    GET /b HTTP/1.1\n"
            "    Host: x.com\n"
            '    """\n'
            "}\n"
        )
        msgs = _lint_messages(src)
        assert any("requires name=" in m for m in msgs)

    def test_duplicate_error_status(self):
        src = _rest_src(errors="    @error 404 Err\n    @error 404 Err\n")
        msgs = _lint_messages(src)
        assert any("duplicate @error" in m for m in msgs)

    def test_2xx_error_requires_field(self):
        src = _rest_src(errors="    @error 200 Err\n")
        msgs = _lint_messages(src)
        assert any("requires field= discriminator" in m for m in msgs)

    def test_invalid_status_range(self):
        src = _rest_src(errors="    @error 99 Err\n")
        msgs = _lint_messages(src)
        assert any("status" in m.lower() for m in msgs)

    def test_single_request_no_name_ok(self):
        src = (
            "json User { id int }\n"
            "struct API type=rest {\n"
            '    @request response=User """\n'
            "    GET /a HTTP/1.1\n"
            "    Host: x.com\n"
            '    """\n'
            "}\n"
        )
        msgs = _lint_messages(src)
        assert msgs == []


# ---------------------------------------------------------------------------
# Converter tests (smoke)
# ---------------------------------------------------------------------------


class TestRestPyConverter:
    def test_py_bs4_generates_valid_python(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        pyast.parse(code)  # must be syntactically valid
        assert "class API" in code
        assert "def get_user" in code
        # Result-style: Ok/Err base classes + per-status Err subclass
        assert "class Ok(Generic[_T]):" in code
        assert "class Err(Generic[_E]):" in code
        assert "class APIErr404(Err[ErrJson]):" in code
        assert "class UnknownErr(Err[Any]):" in code
        assert "class TransportErr(Err[None]):" in code
        assert "RestApiError" not in code
        assert "import requests" in code

    def test_py_bs4_no_typeddict_for_rest(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        # no APIType or similar for the REST struct
        assert "APIType" not in code

    def test_py_bs4_status_error_routing(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert "_status == 404" in code
        assert "_status == 500" in code
        # routed into typed Err subclasses (no raise)
        assert "return APIErr404(headers=_resp_headers, value=_body)" in code
        assert "return APIErr500(headers=_resp_headers, value=_body)" in code
        assert "raise" not in _method_bodies(code)

    def test_py_bs4_method_return_type_union(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert "-> Ok[UserJson] | APIErr404 | UnknownErr | TransportErr" in code

    def test_py_bs4_transport_error_wrapped(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert "except requests.exceptions.RequestException as _exc:" in code
        assert "return TransportErr(cause=repr(_exc))" in code

    def test_py_bs4_headers_captured(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert (
            "_resp_headers = {k.lower(): v for k, v in _resp.headers.items()}"
            in code
        )
        assert "headers=_resp_headers" in code

    def test_py_bs4_unknown_status_returns_unknown_err(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert (
            "return UnknownErr("
            "status=_status, headers=_resp_headers, value=_body)" in code
        )

    def test_py_bs4_httpx_transport_exception(self):
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "except httpx.HTTPError as _exc:" in code

    def test_py_bs4_post_body_is_dict_not_fstring(self):
        """Regression: POST json body used to emit `json=f'{...}'` which
        double-encoded the body. Must now emit a native dict literal."""
        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = (
            "json User { id int; name str }\n"
            "struct API type=rest {\n"
            '    @request name=create response=User """\n'
            "    POST /users HTTP/1.1\n"
            "    Host: x.com\n"
            "    Content-Type: application/json\n"
            "\n"
            '    {"name": "{{name}}", "active": {{active:bool}}}\n'
            '    """\n'
            "}\n"
        )
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")
        assert "json={'name': name, 'active': active}" in code
        # And no leftover f-string style
        assert 'json=f"' not in code
        assert "json=f'" not in code

    def test_py_bs4_runtime_dataclasses_usable(self):
        """Smoke: generated Ok/Err classes must construct and have is_ok."""
        import sys
        import types

        from ssc_codegen.converters.py_bs4 import (
            PY_BASE_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = CONVERTER.convert(module, http_client="requests")

        mod = types.ModuleType("_ssc_test_rest_module")
        sys.modules[mod.__name__] = mod
        try:
            exec(code, mod.__dict__)
            Ok = mod.__dict__["Ok"]
            Err = mod.__dict__["Err"]
            APIErr404 = mod.__dict__["APIErr404"]
            TransportErr = mod.__dict__["TransportErr"]

            ok = Ok(status=200, headers={"x-a": "1"}, value={"id": 1})
            err = APIErr404(headers={}, value={"message": "nope"})
            tr = TransportErr(cause="ConnectionError()")

            assert ok.is_ok is True and ok.status == 200
            assert err.is_ok is False and err.status == 404
            assert isinstance(err, Err)
            assert tr.is_ok is False and tr.status == 0 and tr.cause
        finally:
            sys.modules.pop(mod.__name__, None)


class TestRestJsConverter:
    def test_js_generates_class(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
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
        assert "RestApiError" not in code

    def test_js_method_return_type_jsdoc(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert (
            "@returns {Promise<Ok<UserJson> | APIErr404 | UnknownErr"
            " | TransportErr>}" in code
        )

    def test_js_transport_error_wrapped(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src()
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "} catch (e) {" in code
        assert (
            "isOk: false, status: 0, headers: {}, value: null, "
            "cause: String(e)" in code
        )

    def test_js_headers_captured(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src()
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "Object.fromEntries([..._resp.headers.entries()])" in code
        assert "headers: _respHeaders" in code

    def test_js_axios_variant(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src()
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="axios")
        assert "client.request" in code


def _method_bodies(code: str) -> str:
    """Return only method bodies (everything inside `def …:` through dedent)."""
    import re

    chunks = []
    in_method = False
    indent = 0
    for line in code.splitlines():
        stripped = line.lstrip()
        if re.match(r"(async\s+)?def \w", stripped):
            in_method = True
            indent = len(line) - len(stripped)
            continue
        if in_method:
            if not line.strip():
                chunks.append(line)
                continue
            if len(line) - len(line.lstrip()) <= indent:
                in_method = False
                continue
            chunks.append(line)
    return "\n".join(chunks)


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
        from ssc_codegen.ast.struct import _PLACEHOLDER_RE, _parse_placeholder

        m = _PLACEHOLDER_RE.fullmatch("{{name}}")
        assert m is not None
        ph = _parse_placeholder(m)
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
        from ssc_codegen.ast.struct import _PLACEHOLDER_RE, _parse_placeholder

        m = _PLACEHOLDER_RE.fullmatch(placeholder)
        assert m is not None, placeholder
        ph = _parse_placeholder(m)
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
        from ssc_codegen.ast.struct import _PLACEHOLDER_RE

        assert _PLACEHOLDER_RE.fullmatch(placeholder) is None


class TestTypedPlaceholdersLinter:
    def test_style_without_array_errors(self):
        src = _typed_rest_src("GET /u?q={{q:str|csv}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("requires array [] modifier" in m for m in msgs)

    def test_conflicting_types_error(self):
        src = _typed_rest_src("GET /u/{{id:int}}/p/{{id:str}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("conflicting types" in m for m in msgs)

    def test_unknown_type_error(self):
        src = _typed_rest_src("GET /u?a={{x:bogus}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("unknown type" in m for m in msgs)

    def test_unknown_style_error(self):
        src = _typed_rest_src("GET /u?a={{x:int[]|weird}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("unknown style" in m for m in msgs)

    def test_invalid_name_starts_with_underscore(self):
        src = _typed_rest_src("GET /u?a={{_bad}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("name must start with a letter" in m for m in msgs)

    def test_invalid_name_starts_with_digit(self):
        src = _typed_rest_src("GET /u?a={{1bad}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("name must start with a letter" in m for m in msgs)

    def test_array_in_path_errors(self):
        src = _typed_rest_src("GET /u/{{ids:int[]}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any(
            "array [] is not allowed inside the URL path" in m for m in msgs
        )

    def test_optional_in_path_errors(self):
        src = _typed_rest_src("GET /u/{{id?}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any(
            "optional ? is not allowed inside the URL path" in m for m in msgs
        )

    def test_keyword_name_errors(self):
        src = _typed_rest_src("GET /u?a={{class:int}} HTTP/1.1")
        msgs = _lint_messages(src)
        assert any("reserved keyword" in m for m in msgs)

    def test_legacy_untyped_is_clean(self):
        src = _typed_rest_src("GET /u/{{id}} HTTP/1.1")
        assert _lint_messages(src) == []

    def test_typed_scalar_in_path_is_clean(self):
        src = _typed_rest_src("GET /u/{{id:int}} HTTP/1.1")
        assert _lint_messages(src) == []


class TestTypedPlaceholdersPyCodegen:
    def _gen(self, request_line: str) -> str:
        from ssc_codegen.converters.py_bs4 import PY_BASE_CONVERTER

        module = PARSER.parse(_typed_rest_src(request_line))
        return PY_BASE_CONVERTER.convert(module, http_client="requests")

    def test_scalar_typed_signature(self):
        code = self._gen("GET /u?id={{id:int}} HTTP/1.1")
        assert "id: int" in code

    def test_optional_has_none_default(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "q: str | None = None" in code

    def test_array_annotation(self):
        code = self._gen("GET /u?tags={{tags:int[]}} HTTP/1.1")
        assert "tags: list[int]" in code

    def test_repeat_default_passes_list_native(self):
        # with repeat style (default) requests accepts a list directly:
        # params={'tags': tags}  → ?tags=1&tags=2
        code = self._gen("GET /u?tags={{tags:int[]?}} HTTP/1.1")
        assert "_params['tags'] = tags" in code

    def test_csv_style_joins_with_comma(self):
        code = self._gen("GET /u?tags={{tags:int[]?|csv}} HTTP/1.1")
        assert "','.join(str(_x) for _x in tags)" in code

    def test_optional_builds_params_conditionally(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "if q is not None:" in code
        assert "_params['q'] = q" in code

    def test_required_first_optional_last(self):
        # required 'id' must come before optional 'q' in the signature
        code = self._gen("GET /u/{{id:int}}?q={{q:str?}} HTTP/1.1")
        sig_idx = code.find("def fetch")
        sig_line = code[sig_idx : code.find("\n", sig_idx)]
        assert sig_line.find("id: int") < sig_line.find("q: str | None")

    def test_kebab_name_normalised_with_suffixes(self):
        code = self._gen("GET /u?p={{page-num:int[]?|csv}} HTTP/1.1")
        # NAME renamed to snake_case but type/array/optional/style preserved
        assert "page_num: list[int] | None = None" in code
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
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        module = PARSER.parse(_typed_rest_src(request_line))
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
        assert "for (const _v of tags)" in code
        assert "_params.append('tags', String(_v))" in code

    def test_urlsearchparams_csv_via_join(self):
        code = self._gen("GET /u?tags={{tags:int[]?|csv}} HTTP/1.1")
        assert "tags.map(String).join(',')" in code

    def test_bracket_style_rewrites_key(self):
        code = self._gen("GET /u?tags={{tags:int[]|bracket}} HTTP/1.1")
        assert "_params.append('tags[]', String(_v))" in code

    def test_optional_conditional_set(self):
        code = self._gen("GET /u?q={{q:str?}} HTTP/1.1")
        assert "if (q !== undefined && q !== null)" in code

    def test_legacy_untyped_stays_simple(self):
        code = self._gen("GET /u/{{id}} HTTP/1.1")
        # No URLSearchParams-builder needed for the simple path placeholder
        assert "new URLSearchParams();" not in code
        assert "${id}" in code  # inline template substitution
