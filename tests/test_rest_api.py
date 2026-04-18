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
        "    @request name=get-user response=User \"\"\"\n"
        "    GET /users/{{id}} HTTP/1.1\n"
        "    Host: api.example.com\n"
        "    \"\"\"\n"
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
            "    @request response=User \"\"\"\n"
            "    GET /a HTTP/1.1\n"
            "    Host: x.com\n"
            "    \"\"\"\n"
            "    @request response=User \"\"\"\n"
            "    GET /b HTTP/1.1\n"
            "    Host: x.com\n"
            "    \"\"\"\n"
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
        assert any(
            "requires field= discriminator" in m for m in msgs
        )

    def test_invalid_status_range(self):
        src = _rest_src(errors="    @error 99 Err\n")
        msgs = _lint_messages(src)
        assert any("status" in m.lower() for m in msgs)

    def test_single_request_no_name_ok(self):
        src = (
            "json User { id int }\n"
            "struct API type=rest {\n"
            "    @request response=User \"\"\"\n"
            "    GET /a HTTP/1.1\n"
            "    Host: x.com\n"
            "    \"\"\"\n"
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
        assert "RestApiError" in code
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


class TestRestJsConverter:
    def test_js_generates_class(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src(errors="    @error 404 Err\n")
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="fetch")
        assert "class API" in code
        assert "static async getUser" in code
        assert "RestApiError" in code

    def test_js_axios_variant(self):
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        src = _rest_src()
        module = PARSER.parse(src)
        code = JS_CONVERTER.convert(module, http_client="axios")
        assert "client.request" in code
