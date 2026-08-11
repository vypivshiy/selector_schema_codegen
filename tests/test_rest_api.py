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
        assert "except httpx.HTTPError as exc:" in code
        assert "return TransportErr(cause=repr(exc))" in code

    def test_py_bs4_headers_captured(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # Headers extraction centralized in ssc_rest_call
        assert (
            "headers = {k.lower(): v for k, v in resp.headers.items()}" in code
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
            "status=status, headers=headers, value=body)" in code
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
        # Method body calls ssc_rest_call (wrapped in cast())
        assert "return cast(" in code
        assert "ssc_rest_call(" in code

    def test_py_bs4_emits_ssc_dispatch_err_module_level(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src(errors="    @error 404 Err\n    @error 500 Err\n")
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        # ssc_dispatch_err is now a module-level function
        assert "def ssc_dispatch_err(" in code
        # Method body delegates to ssc_rest_call (not cls.ssc_dispatch_err)
        assert "cls.ssc_dispatch_err" not in code
        # No inline `if status == NNN` checks in @classmethods
        import re

        for match in re.finditer(r"@classmethod\s*\n(?:    [^\n]*\n)+", code):
            assert "if status ==" not in match.group(0)

    def test_py_bs4_httpx_transport_exception(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = _rest_src()
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "except httpx.HTTPError as exc:" in code

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
        assert "_kw[\"json\"] = {'name': name, 'active': active}" in code
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
        # isinstance check now inside ErrMatcher.match (body var is body)
        assert "isinstance(body, dict)" in code


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

    def test_js_rest_accepts_opts(self):
        """JS REST method signature has ``opts = {}`` for per-call overrides."""
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "opts = {}" in code
        assert "const _kw =" in code
        assert "Object.entries(opts)" in code

    def test_js_fetch_accepts_opts(self):
        """JS HTML fetch method also accepts ``opts = {}``."""
        from ssc_codegen.targets.javascript import JS_CONVERTER

        src = _rest_src()
        module = _parse(src)
        code = JS_CONVERTER.convert(module, http_client="axios")
        assert "opts = {}" in code


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
        assert "std_unescape_text" not in code
        assert "std_normalize_text" not in code
        assert "std_repl_map" not in code
        assert "UnmatchedTableRow" not in code
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
        # Runtime-internal helpers (Ok/Err/ErrMatcher factory definitions)
        # must NOT be inlined into the parser file under -R. The parser file
        # only declares @dataclass Err subclasses consuming those types.
        assert "class Ok(Generic[_T]):" not in code
        assert "class Err(Generic[_E]):" not in code
        assert "def ssc_rest_call(" not in code
        assert "def ssc_dispatch_err(" not in code
        # Imports only needed by the runtime's internal generic/dataclass
        # machinery must not leak into the parser file.
        for runtime_only in ("Generic", "TypeVar", "Mapping", "Callable"):
            assert runtime_only not in code

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
        # pyast.parse checks syntax only — does not catch NameError caused
        # by dropped imports. exec(compile(...)) actually resolves names.
        pyast.parse(generated[""])
        pyast.parse(generated[f"{self.RUNTIME_NAME}.py"])
        _exec_with_runtime(generated[""], generated[f"{self.RUNTIME_NAME}.py"])

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_main_imports_present_under_runtime(self, converter_attr):
        """Regression: -R mode must not drop typing/dataclass/httpx imports.

        Pre-fix the parser file lost every non-runtime import under -R,
        producing code that referenced ``TypedDict``, ``Optional``,
        ``@dataclass``, ``Literal[404]``, ``httpx.Client`` etc. with none of
        them bound. This test pins the required import surface.
        """
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
        assert "from typing import" in code
        assert "TypedDict" in code
        assert "from dataclasses import dataclass" in code
        assert "from typing import Literal" in code
        assert "import httpx" in code
        # Err subclasses need Literal for status field; should NOT be dropped
        # just because runtime mode is on.
        assert "Literal[404]" in code

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_runtime_file_imports_httpx_when_rest(self, converter_attr):
        """Regression: runtime file references ``httpx.HTTPError`` in
        ``ssc_rest_call``/``ssc_rest_call_async`` but pre-fix did not import
        httpx, causing NameError at the first transport exception.
        """
        from ssc_codegen.generation.runtime import register_runtime_file

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        # http_strategy is normally resolved by main.py via
        # PythonVisitor.http_strategy_for(http_client); here we emulate
        # the httpx case.
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy

        register_runtime_file(
            converter,
            self.RUNTIME_NAME,
            http_strategy=HttpxStrategy(),
        )
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        assert "import httpx" in runtime
        # And the generated runtime must be valid + executable in isolation.
        exec(compile(runtime, "<rt>", "exec"), {})

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
            (None, "HttpxStrategy", "import httpx"),
            ("httpx", "HttpxStrategy", "import httpx"),
            ("aiohttp", "AioHttpStrategy", "import aiohttp"),
            ("requests", "RequestsStrategy", "import requests"),
            ("<bogus>", "HttpxStrategy", "import httpx"),  # fallback to default
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
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy
        from ssc_codegen.targets.python.http_libs.requests import (
            RequestsStrategy,
        )
        from ssc_codegen.targets.python.visitor import PythonVisitor

        strategy = PythonVisitor.http_strategy_for(http_client)
        type_map = {
            "HttpxStrategy": HttpxStrategy,
            "AioHttpStrategy": AioHttpStrategy,
            "RequestsStrategy": RequestsStrategy,
        }
        assert isinstance(strategy, type_map[expected_strategy])
        assert isinstance(strategy, HttpLibStrategy)
        assert strategy.import_line == expected_import

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_runtime_file_imports_httpx_when_http_client_is_none(
        self, converter_attr
    ):
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

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        # Emulate main.py: resolve HTTP strategy via the shared resolver
        # without explicitly passing http_client.
        strategy = PythonVisitor.http_strategy_for(None)
        register_runtime_file(
            converter,
            self.RUNTIME_NAME,
            http_strategy=strategy,
        )
        # Also do not pass http_client to convert_all — emulates the user
        # not passing --http-client on the CLI.
        generated = converter.convert_all(
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

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_html_only_module_with_fetch_imports_httpx(self, converter_attr):
        """Regression: HTML-only module with a ``fetch`` shortcut method
        emits ``def fetch(cls, client: httpx.Client, ...)`` in the parser
        file. Pre-fix the visitor gated ``import httpx`` behind
        ``module_has_rest`` which is False for HTML structs, causing
        ``NameError: name 'httpx' is not defined`` at class definition
        time on the consumer side.

        ``module_uses_http`` is the broader gate that covers both REST
        structs and any struct with a MethodFetch / MethodRest in its body.
        """
        converter = _get_all_converters()[converter_attr]
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
        generated = converter.convert_all(module)
        code = generated[""]
        assert "def fetch" in code
        assert "client: httpx.Client" in code
        assert "import httpx" in code

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_runtime_functions_have_typed_signatures(self, converter_attr):
        """Pin the typed signatures on runtime functions: parameters and
        return types must be annotated, and the historical ``_`` prefix on
        public-ish parameters (matchers, status, headers, body, value_fn)
        must be gone.

        Pre-fix the runtime was untyped and used ``_matchers``, ``_status``,
        ``_value_fn`` etc. which obscured intent and made consumer-side
        typing weak.
        """
        from ssc_codegen.generation.runtime import register_runtime_file
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy

        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        register_runtime_file(
            converter,
            self.RUNTIME_NAME,
            http_strategy=HttpxStrategy(),
        )
        generated = converter.convert_all(
            module,
            http_client="httpx",
            runtime_module=self.RUNTIME_NAME,
        )
        runtime = generated[f"{self.RUNTIME_NAME}.py"]
        # Typed signature: ssc_dispatch_err
        assert "def ssc_dispatch_err(" in runtime
        assert "matchers: List[ErrMatcher]" in runtime
        assert "status: int" in runtime
        assert "headers: Dict[str, str]" in runtime
        assert "body: Any" in runtime
        assert ") -> Optional[Err]:" in runtime
        # Typed signature: ssc_rest_call
        assert "def ssc_rest_call(" in runtime
        assert "client: httpx.Client" in runtime
        assert "value_fn: Optional[Callable[[Any], _T]] = None" in runtime
        assert "**kw: Any" in runtime
        # Return type is Union[Ok[_T], Err] — stable monad annotation.
        # The exact Err subclass is determined by runtime dispatch over
        # the matchers list (heterogeneous — each matcher may produce a
        # different Err subclass). Parser-side call sites wrap the call
        # in ``cast(<ResultAlias>, ...)`` to narrow to the precise union
        # (Err400 | UnknownErr | TransportErr | ...) declared by the
        # parser's own type alias.
        assert ") -> Union[Ok[_T], Err]:" in runtime
        # Async variant
        assert "async def ssc_rest_call_async(" in runtime
        assert "client: httpx.AsyncClient" in runtime
        # ErrMatcher.match typed
        assert "def match(" in runtime
        # No underscore-prefixed parameters in the public runtime API.
        assert "_matchers" not in runtime
        assert "_status:" not in runtime
        assert "_headers:" not in runtime
        assert "_body:" not in runtime
        assert "_value_fn" not in runtime
        # Mapping replaced with Dict in dataclass fields.
        assert "Mapping[str, str]" not in runtime
        assert "Dict[str, str]" in runtime

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

    @pytest.mark.parametrize("converter_attr", list(_get_all_converters()))
    def test_parser_wraps_rest_call_in_cast(self, converter_attr):
        """Parser ``fetch``/``async_fetch``/``<method>`` return values
        are wrapped in ``cast(<ResultAlias>, ssc_rest_call(...))``.

        ssc_rest_call returns ``Union[Ok[_T], Err]`` (Err base) — honest
        about runtime dispatch but mypy-incompatible with the parser's
        specific result union (Err400 | UnknownErr | ...). cast()
        documents the intent at the call site without suppressing mypy
        via ``# type: ignore``; consumer code sees the stable monad
        annotation declared on the wrapping method.
        """
        converter = _get_all_converters()[converter_attr]
        src = _rest_src(errors="    @error 404 Err\n")
        module = _parse(src)
        code = converter.convert(module, http_client="httpx")
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

    def test_py_emits_value_fn_accessor(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        module = _parse(self._rest_path_src())
        code = CONVERTER.convert(module, http_client="httpx")
        # value_fn extracts via dict access chain using path segments
        assert "value_fn=lambda _b: _b['data']['user']," in code

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

    def test_py_void_without_path_emits_none(self):
        from ssc_codegen.targets.python import (
            PY_BS4_CONVERTER as CONVERTER,
        )

        src = (
            "struct API type=rest {\n"
            '    @request """\n'
            "    GET /ping HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            "}\n"
        )
        module = _parse(src)
        code = CONVERTER.convert(module, http_client="httpx")
        assert "value_fn=lambda _: None," in code

    def test_js_emits_value_fn_accessor(self):
        from ssc_codegen.targets.javascript import JS_CONVERTER

        module = _parse(self._rest_path_src())
        code = JS_CONVERTER.convert(module, http_client="fetch")
        # JS uses double-quoted JSON-style keys (json.dumps output)
        assert '(_b) => _b["data"]["user"]' in code

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
        # gjson.GetBytes(body, "data.user").Raw narrows body before Unmarshal
        assert 'gjson.GetBytes(body, "data.user").Raw' in code

    def test_go_renamed_body_var_no_underscore_prefix(self):
        """Patch B also renamed Go locals: _body → body, _err → err,
        _val → val, _perr → perr inside emit_method_rest."""
        from ssc_codegen.targets.golang import GO_CONVERTER

        module = _parse(self._rest_path_src())
        code = GO_CONVERTER.convert(module)
        assert "var val " in code  # was: var _val
        assert "if perr := json.Unmarshal(body, &val)" in code
        assert "if err != nil" in code
        # Old underscore-prefixed names must be gone from rest methods.
        # REST methods are receiver methods on the marker struct; match
        # the receiver-prefixed signature (e.g. "func (a API) Fetch(").
        rest_section = code[code.find("func (a API) Fetch(") :]
        assert "_body" not in rest_section
        assert "_val" not in rest_section
        assert "_err" not in rest_section
        assert "_perr" not in rest_section

    def test_go_rest_accepts_opts(self):
        """Go REST methods accept variadic ``opts ...sscReqOpt``."""
        from ssc_codegen.targets.golang import GO_CONVERTER

        module = _parse(self._rest_path_src())
        code = GO_CONVERTER.convert(module)
        assert "opts ...sscReqOpt" in code
        assert "for _, o := range opts {" in code
        assert "o(_opts)" in code

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


# ---------------------------------------------------------------------------
# aiohttp content_type=None — non-JSON Content-Type bug (TASK_MIGRATION §2.1)
# ---------------------------------------------------------------------------


class TestAiohttpContentTypeBypass:
    """aiohttp ``resp.json()`` raises ``ContentTypeError`` when the server
    returns JSON under a non-``application/json`` Content-Type (mixcloud
    sends ``text/javascript``). Codegen must emit ``content_type=None`` to
    disable the check on every aiohttp JSON path.

    Affects:
    - ``fetch_body_lines`` (MethodFetch with response-path)
    - ``ssc_rest_call`` and ``ssc_rest_call_async`` (REST runtime)

    httpx/requests are unaffected — their ``.json()`` ignores Content-Type.
    """

    @staticmethod
    def _fetch_with_path_src() -> str:
        return (
            "struct Page {\n"
            '    @request response-path="data" """\n'
            "    GET /p HTTP/1.1\n"
            "    Host: api.example.com\n"
            '    """\n'
            '    title { css "h1"; text }\n'
            "}\n"
        )

    def test_aiohttp_fetch_body_lines_bypass_content_type(self):
        """fetch path with response-path must pass content_type=None."""
        from ssc_codegen.targets.python.http_libs.aiohttp import (
            AioHttpStrategy,
        )

        strategy = AioHttpStrategy()
        lines = strategy.fetch_body_lines(
            is_async=True,
            request_call="async with client.request(",
            kwargs_lines=[],
            response_path="data",
            response_join="",
            i2="    ",
            i3="        ",
        )
        joined = "\n".join(lines)
        assert "await _resp.json(content_type=None)" in joined

    def test_aiohttp_rest_runtime_call_has_content_type_none(self):
        from ssc_codegen.targets.python.http_libs.aiohttp import (
            AioHttpStrategy,
        )

        runtime = "\n".join(AioHttpStrategy().rest_runtime_lines())
        # Both ssc_rest_call and ssc_rest_call_async must bypass CT check.
        assert runtime.count("await resp.json(content_type=None)") == 2

    def test_aiohttp_runtime_does_not_use_bare_json(self):
        """No ``await resp.json()`` (without content_type) must remain in
        the aiohttp runtime — bare call would re-introduce the CT bug."""
        from ssc_codegen.targets.python.http_libs.aiohttp import (
            AioHttpStrategy,
        )

        runtime = "\n".join(AioHttpStrategy().rest_runtime_lines())
        assert "await resp.json()" not in runtime
        assert "await _resp.json()" not in runtime

    def test_httpx_runtime_does_not_have_content_type_kwarg(self):
        """httpx is not affected — must NOT carry the aiohttp-specific
        kwarg (regression guard against copy-paste across strategies)."""
        from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy

        runtime = "\n".join(HttpxStrategy().rest_runtime_lines())
        assert "content_type=None" not in runtime
        assert "resp.json()" in runtime  # bare call is safe on httpx

    def test_requests_runtime_does_not_have_content_type_kwarg(self):
        from ssc_codegen.targets.python.http_libs.requests import (
            RequestsStrategy,
        )

        runtime = "\n".join(RequestsStrategy().rest_runtime_lines())
        assert "content_type=None" not in runtime
        assert "resp.json()" in runtime
