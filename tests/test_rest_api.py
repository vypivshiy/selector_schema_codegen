"""Tests for REST API struct support (struct type=rest).

Covers:
- Parser: StructType.REST, @request on REST, @error parsing
- Converters: py_bs4 and js_pure code generation
"""

from __future__ import annotations

import ast as pyast

import pytest

from ssc_codegen.ast import (
    ErrorResponse,
    MethodRest,
    StructRest,
)
from ssc_codegen.core import parse_module
from kdlquery import Severity


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


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestRestParser:
    def test_rest_struct_type(self):
        module = _parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, StructRest))
        assert isinstance(struct, StructRest)

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

    def test_no_start_parse_for_rest(self):
        from ssc_codegen.ast import StartParse

        module = _parse(_rest_src())
        struct = next(n for n in module.body if isinstance(n, StructRest))
        assert not any(isinstance(n, StartParse) for n in struct.body)

    def test_error_required_keys_parsed(self):
        src = _rest_src(errors="    @error 404 Err error detail\n")
        module = _parse(src)
        struct = next(n for n in module.body if isinstance(n, StructRest))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert len(errors) == 1
        assert errors[0].required_keys == ["error", "detail"]
        assert errors[0].conditions == {}

    def test_error_mixed_conditions_parsed(self):
        src = _rest_src(errors='    @error 404 Err error detail="msg"\n')
        module = _parse(src)
        struct = next(n for n in module.body if isinstance(n, StructRest))
        errors = [n for n in struct.body if isinstance(n, ErrorResponse)]
        assert len(errors) == 1
        assert errors[0].required_keys == ["error"]
        assert errors[0].conditions == {"detail": "msg"}


# ---------------------------------------------------------------------------
# Converter tests (smoke)
# ---------------------------------------------------------------------------


class TestRestPyConverter:
    def test_py_bs4_generates_valid_python(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
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
        assert "import httpx" in code

    def test_py_bs4_no_typeddict_for_rest(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # no APIType or similar for the REST struct
        assert "APIType" not in code

    def test_py_bs4_status_error_routing(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # matchers list routes status codes to Err subclasses
        assert "ErrMatcher(404, None, APIErr404)," in code
        assert "ErrMatcher(500, None, APIErr500)," in code
        # no raise in method bodies (errors are returned, not raised)
        assert "raise" not in _method_bodies(code)

    def test_py_bs4_method_return_type_union(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # type alias is emitted at module level
        assert (
            "GetUserResult = Union[Ok[UserJson], APIErr404, UnknownErr, TransportErr]"
            in code
        )
        # method signature uses the alias
        assert "-> GetUserResult:" in code

    def test_py_bs4_transport_error_wrapped(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # httpx-specific exception handling inside ssc_rest_call
        assert "except httpx.HTTPError as _exc:" in code
        assert "return TransportErr(cause=repr(_exc))" in code

    def test_py_bs4_headers_captured(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # Headers extraction centralized in ssc_rest_call
        assert (
            "_headers = {k.lower(): v for k, v in _resp.headers.items()}"
            in code
        )

    def test_py_bs4_unknown_status_returns_unknown_err(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # UnknownErr fallback inside ssc_dispatch_err
        assert (
            "return UnknownErr("
            "status=_status, headers=_headers, value=_body)" in code
        )

    def test_py_bs4_emits_ssc_rest_call_helpers(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "def ssc_rest_call(" in code
        assert "def ssc_rest_call_async(" in code
        # Method body calls ssc_rest_call
        assert "return ssc_rest_call(" in code

    def test_py_bs4_emits_ssc_dispatch_err_module_level(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # ssc_dispatch_err is now a module-level function
        assert "def ssc_dispatch_err(_matchers, _status" in code
        # Method body delegates to ssc_rest_call (not cls.ssc_dispatch_err)
        assert "cls.ssc_dispatch_err" not in code
        # No inline `if _status == NNN` checks in @classmethods
        import re

        for match in re.finditer(r"@classmethod\s*\n(?:    [^\n]*\n)+", code):
            assert "if _status ==" not in match.group(0)

    def test_py_bs4_httpx_transport_exception(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "except httpx.HTTPError as _exc:" in code

    def test_py_bs4_post_body_is_dict_not_fstring(self):
        """Regression: POST json body used to emit `json=f'{...}'` which
        double-encoded the body. Must now emit a native dict literal."""
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
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
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "json={'name': name, 'active': active}" in code
        # And no leftover f-string style
        assert 'json=f"' not in code
        assert "json=f'" not in code

    def test_py_required_keys_dispatch(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err error detail\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # conditions are now lambdas in matchers list (body var is _b)
        assert "'error' in _b" in code
        assert "'detail' in _b" in code
        assert "class APIErr404ErrorDetail" in code

    def test_py_mixed_conditions_dispatch(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors='    @error 404 Err error detail="msg"\n')
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "'error' in _b" in code
        assert "_b.get('detail') == 'msg'" in code
        assert "class APIErr404ErrorDetail" in code

    def test_py_required_keys_routed_as_field_error(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err error\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # isinstance check now inside ErrMatcher.match (body var is _b)
        assert "isinstance(_b, dict)" in code


class TestRestJsConverter:
    def test_js_generates_class(self):
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
        assert "RestApiError" not in code

    def test_js_method_return_type_jsdoc(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert (
            "@returns {Promise<Ok<UserJson> | APIErr404 | UnknownErr"
            " | TransportErr>}" in code
        )

    def test_js_transport_error_wrapped(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "} catch (e) {" in code
        assert (
            "isOk: false, status: 0, headers: {}, value: null, "
            "cause: String(e)" in code
        )

    def test_js_headers_captured(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        # Header extraction centralized in sscRestCall helper
        assert "Object.fromEntries([..._resp.headers.entries()])" in code
        # Ok return carries _headers + _value
        assert "headers: _headers, value: _value" in code

    def test_js_axios_variant(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="axios")
        assert "client.request" in code
        # Axios uses dedicated sscRestCallAxios helper
        assert "sscRestCallAxios" in code

    def test_js_emits_ssc_rest_call_helpers(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "async function sscRestCall(" in code
        assert "async function sscRestCallAxios(" in code
        assert "function sscDispatchErr(" in code
        # Method body delegates to sscRestCall
        assert "return sscRestCall(" in code

    def test_js_emits_matchers_and_dispatch(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        # Matchers list emitted at module level
        assert "const _apiMatchers = [" in code
        assert "status: 404" in code
        assert "status: 500" in code
        # sscDispatchErr is module-level (not a static method)
        assert "function sscDispatchErr(_matchers" in code
        assert "static sscDispatchErr" not in code

    def test_js_required_keys_dispatch(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err error detail\n")
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        # Condition lambda uses _b (not _body)
        assert "'error' in _b" in code
        assert "'detail' in _b" in code
        assert "APIErr404ErrorDetail" in code


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

    def test_rest_only_no_html_unescape(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = PY_BASE_CONVERTER.convert(module, http_client="httpx")
        assert "_html_unescape" not in code

    def test_rest_only_no_html_utilities(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = PY_BASE_CONVERTER.convert(module, http_client="httpx")
        assert "unescape_text" not in code
        assert "normalize_text" not in code
        assert "repl_map" not in code
        assert "_UnmatchedTableRow" not in code
        assert "UNMATCHED_TABLE_ROW" not in code
        assert "_RE_HEX_ENTITY" not in code

    def test_rest_only_has_rest_utilities(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = PY_BASE_CONVERTER.convert(module, http_client="httpx")
        assert "class Ok(Generic[_T]):" in code
        assert "class Err(Generic[_E]):" in code
        assert "def ssc_rest_call(" in code

    def test_rest_only_valid_python(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as PY_BASE_CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = PY_BASE_CONVERTER.convert(module, http_client="httpx")
        pyast.parse(code)

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


def _get_all_converters():
    from ssc_codegen.targets.python import (
        PY_BS4_CONVERTER,
        PY_LXML_CONVERTER,
        PY_PARSEL_CONVERTER,
        PY_SLAX_CONVERTER,
    )

    return {
        "PyBs4": PY_BS4_CONVERTER,
        "PyLxml": PY_LXML_CONVERTER,
        "PyParsel": PY_PARSEL_CONVERTER,
        "PySlax": PY_SLAX_CONVERTER,
    }


class TestSeparateRuntime:
    """Verify -R (separate runtime) works correctly for all Python targets."""

    RUNTIME_NAME = "sscgen_runtime"

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_runtime_file_has_rest_helpers(self, converter_attr):
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(converter, self.RUNTIME_NAME)
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        assert "class Ok(Generic[_T]):" in runtime
        assert "class Err(Generic[_E]):" in runtime
        assert "class UnknownErr(Err[Any]):" in runtime
        assert "class TransportErr(Err[None]):" in runtime
        assert "def ssc_rest_call(" in runtime

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_main_imports_from_runtime(self, converter_attr):
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(converter, self.RUNTIME_NAME)
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        code = generated[""]
        assert f"from .{self.RUNTIME_NAME} import" in code
        assert "Ok" in code.split(f"from .{self.RUNTIME_NAME} import")[1]

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_main_no_inline_rest_helpers(self, converter_attr):
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(converter, self.RUNTIME_NAME)
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        code = generated[""]
        # Ok/Err as class definitions should NOT be in the main module
        assert "class Ok(Generic[_T]):" not in code
        assert "class Err(Generic[_E]):" not in code
        assert "def ssc_rest_call(" not in code

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_main_no_redundant_rest_imports(self, converter_attr):
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(converter, self.RUNTIME_NAME)
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        code = generated[""]
        assert (
            "from typing import Generic, Literal, Mapping, TypeVar" not in code
        )

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_main_valid_python(self, converter_attr):
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(converter, self.RUNTIME_NAME)
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        pyast.parse(generated[""])
        pyast.parse(generated[f"{self.RUNTIME_NAME}.py"])

    def test_ref_ast_picks_rest_module(self):
        """The ref_ast selection must not crash on modules with non-REST structs."""
        from ssc_codegen.generation.runtime import register_runtime_file

        non_rest_src = 'struct Item { field_name { css "div" } }'
        module = _parse(non_rest_src)
        converter = _get_all_converters()["PyBs4"]
        register_runtime_file(converter, self.RUNTIME_NAME)
        converter.convert_all(module, runtime_module=self.RUNTIME_NAME)


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
