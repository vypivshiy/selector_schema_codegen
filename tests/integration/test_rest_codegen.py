"""Integration tests: generate Python REST API code from KDL schemas, exec, and
verify fetch results with mock HTTP via respx.

Each test: KDL REST schema fixture → generate code → exec → call fetch
with respx-mocked httpx → assert Result objects.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx
import pytest
import respx

from ssc_codegen.core import parse_module
from kdlquery import Severity

SCHEMAS_DIR = Path(__file__).parent / "schemas"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(src: str):
    module, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError("; ".join(d.message for d in errors))
    return module


def _generate(src: str, *, http_client: str = "httpx") -> dict:
    """Parse KDL REST schema, generate py-bs4 code, exec, return namespace."""
    from ssc_codegen.converters.py_bs4 import PY_BASE_CONVERTER

    module = _parse(src)
    code = PY_BASE_CONVERTER.convert(module, http_client=http_client)
    namespace: dict = {}
    exec(code, namespace)  # noqa: S102
    return namespace


def _load_schema(filename: str) -> str:
    return (SCHEMAS_DIR / filename).read_text()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_ns():
    return _generate(_load_schema("08_rest_basic.kdl"))


@pytest.fixture
def void_ns():
    return _generate(_load_schema("09_rest_void.kdl"))


@pytest.fixture
def err_404_ns():
    return _generate(_load_schema("10_rest_err_404.kdl"))


@pytest.fixture
def err_404_500_ns():
    return _generate(_load_schema("11_rest_err_404_500.kdl"))


@pytest.fixture
def err_404_keys_ns():
    return _generate(_load_schema("12_rest_err_404_keys.kdl"))


@pytest.fixture
def err_200_field_ns():
    return _generate(_load_schema("13_rest_err_200_field.kdl"))


@pytest.fixture
def int_placeholder_ns():
    return _generate(_load_schema("14_rest_int_placeholder.kdl"))


@pytest.fixture
def query_opt_ns():
    return _generate(_load_schema("15_rest_query_opt.kdl"))


@pytest.fixture
def header_ns():
    return _generate(_load_schema("16_rest_header.kdl"))


@pytest.fixture
def post_ns():
    return _generate(_load_schema("17_rest_post.kdl"))


@pytest.fixture
def prefix_ns():
    return _generate(_load_schema("20_rest_prefix_form.kdl"))


@pytest.fixture
def multi_method_ns():
    return _generate(_load_schema("21_rest_multi_method.kdl"))


@pytest.fixture
def response_path_ns():
    return _generate(_load_schema("22_rest_response_path.kdl"))


# ---------------------------------------------------------------------------
# 1. Success responses
# ---------------------------------------------------------------------------


class TestRestSuccess:
    """GET → 200 with JSON → Ok[value] with parsed body."""

    def test_sync_200_returns_ok_with_body(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/42").respond(
                json={"id": 42, "name": "Alice"}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id="42")

        assert result.is_ok is True
        assert result.status == 200
        assert result.value == {"id": 42, "name": "Alice"}

    def test_async_200_returns_ok_with_body(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:

            async def _run():
                respx.get("https://api.example.com/users/42").respond(
                    json={"id": 42, "name": "Alice"}, status_code=200
                )
                async with httpx.AsyncClient() as client:
                    return await API.async_fetch(client, id="42")

            result = asyncio.run(_run())

        assert result.is_ok is True
        assert result.status == 200
        assert result.value == {"id": 42, "name": "Alice"}

    def test_ok_has_headers(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"id": 1, "name": "Bob"},
                status_code=200,
                headers={"X-Request-Id": "abc123"},
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert result.is_ok is True
        assert "x-request-id" in result.headers
        assert result.headers["x-request-id"] == "abc123"

    def test_void_response_schema_returns_none_value(self, void_ns):
        API = void_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/x").respond(
                json={"ok": True}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id="x")

        assert result.is_ok is True
        assert result.value is None


# ---------------------------------------------------------------------------
# 2. Error dispatch
# ---------------------------------------------------------------------------


class TestRestErrorDispatch:
    """REST with @error → status code routing → correct Err variant."""

    def test_404_returns_err_subclass(self, err_404_ns):
        API = err_404_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/99").respond(
                json={"code": 404, "message": "not found"}, status_code=404
            )
            client = httpx.Client()
            result = API.fetch(client, id="99")

        assert result.is_ok is False
        ErrCls = err_404_ns["APIErr404"]
        assert isinstance(result, ErrCls)
        assert result.status == 404
        assert result.value == {"code": 404, "message": "not found"}

    def test_500_returns_err_subclass(self, err_404_500_ns):
        API = err_404_500_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"code": 500, "message": "internal"}, status_code=500
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert result.is_ok is False
        assert isinstance(result, err_404_500_ns["APIErr500"])
        assert result.status == 500

    def test_unknown_status_returns_unknown_err(self, err_404_ns):
        API = err_404_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"error": "rate limited"}, status_code=429
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert result.is_ok is False
        assert isinstance(result, err_404_ns["UnknownErr"])
        assert result.status == 429

    def test_required_keys_dispatch(self, err_404_keys_ns):
        API = err_404_keys_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"error": "x", "detail": "y"}, status_code=404
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert result.is_ok is False
        ErrCls = err_404_keys_ns["APIErr404ErrorDetail"]
        assert isinstance(result, ErrCls)

    def test_required_keys_not_matched_falls_through(self, err_404_keys_ns):
        """If required keys are missing, falls through to UnknownErr."""
        API = err_404_keys_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"message": "not found"}, status_code=404
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert isinstance(result, err_404_keys_ns["UnknownErr"])

    def test_200_with_field_condition(self, err_200_field_ns):
        API = err_200_field_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/1").respond(
                json={"detail": "msg", "extra": 1}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert result.is_ok is False
        ErrCls = err_200_field_ns["APIErr200Detail"]
        assert isinstance(result, ErrCls)

    def test_async_error_dispatch(self, err_404_ns):
        API = err_404_ns["API"]

        with respx.mock:

            async def _run():
                respx.get("https://api.example.com/users/99").respond(
                    json={"code": 404, "message": "not found"}, status_code=404
                )
                async with httpx.AsyncClient() as client:
                    return await API.async_fetch(client, id="99")

            result = asyncio.run(_run())

        assert result.is_ok is False
        assert isinstance(result, err_404_ns["APIErr404"])


# ---------------------------------------------------------------------------
# 3. Transport errors
# ---------------------------------------------------------------------------


class TestRestTransportError:
    """Network failure → TransportErr."""

    def test_sync_transport_error(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:
            respx.get(re.compile(r".*")).mock(
                side_effect=httpx.HTTPError("connection timeout")
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert isinstance(result, basic_ns["TransportErr"])
        assert "connection timeout" in result.cause
        assert result.status == 0

    def test_async_transport_error(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:

            async def _run():
                respx.get(re.compile(r".*")).mock(
                    side_effect=httpx.HTTPError("async timeout")
                )
                async with httpx.AsyncClient() as client:
                    return await API.async_fetch(client, id="1")

            result = asyncio.run(_run())

        assert isinstance(result, basic_ns["TransportErr"])
        assert "async timeout" in result.cause

    def test_connect_error_is_transport_err(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:
            respx.get(re.compile(r".*")).mock(
                side_effect=httpx.ConnectError("refused")
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert isinstance(result, basic_ns["TransportErr"])
        assert "refused" in result.cause


# ---------------------------------------------------------------------------
# 4. Placeholder rendering
# ---------------------------------------------------------------------------


class TestRestPlaceholders:
    """Verify parameters are correctly substituted into URL/headers/body."""

    def test_string_placeholder_in_url(self, basic_ns):
        API = basic_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/users/42").respond(
                json={"id": 42, "name": "Test"}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id="42")

        assert result.is_ok is True
        assert route.called

    def test_typed_int_placeholder(self, int_placeholder_ns):
        API = int_placeholder_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/items/7").respond(
                json={"id": 7, "name": "Item"}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id=7)

        assert result.is_ok is True
        req = route.calls[0].request
        assert "/items/7" in str(req.url)

    def test_optional_param_not_sent_when_none(self, query_opt_ns):
        API = query_opt_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/search").respond(
                json={"id": 0, "name": ""}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, q=None)

        assert result.is_ok is True
        req = route.calls[0].request
        assert "q=" not in str(req.url)

    def test_optional_param_sent_when_provided(self, query_opt_ns):
        API = query_opt_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/search").respond(
                json={"id": 0, "name": ""}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, q="hello")

        assert result.is_ok is True
        req = route.calls[0].request
        assert "q=hello" in str(req.url)

    def test_header_placeholder_replaced(self, header_ns):
        API = header_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/me").respond(
                json={"id": 1, "name": "Me"}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, token="secret123")

        assert result.is_ok is True
        req = route.calls[0].request
        assert req.headers.get("authorization") == "Bearer secret123"

    def test_post_body_placeholders(self, post_ns):
        API = post_ns["API"]

        with respx.mock:
            route = respx.post("https://api.example.com/users").respond(
                json={"id": 99, "name": "NewUser"}, status_code=201
            )
            client = httpx.Client()
            result = API.fetch(client, name="NewUser", active=True)

        assert result.is_ok is True
        assert result.value == {"id": 99, "name": "NewUser"}
        req = route.calls[0].request
        body = req.content.decode()
        assert '"name":"NewUser"' in body
        assert '"active":true' in body


# ---------------------------------------------------------------------------
# 5. Prefix form (rest)struct
# ---------------------------------------------------------------------------


class TestRestPrefixForm:
    def test_sync_200_returns_ok(self, prefix_ns):
        API = prefix_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/42").respond(
                json={"id": 42, "name": "Alice"}, status_code=200
            )
            client = httpx.Client()
            result = API.fetch(client, id="42")

        assert result.is_ok is True
        assert result.value == {"id": 42, "name": "Alice"}

    def test_404_dispatches_to_err(self, prefix_ns):
        API = prefix_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/users/99").respond(
                json={"code": 404, "message": "not found"}, status_code=404
            )
            client = httpx.Client()
            result = API.fetch(client, id="99")

        assert result.is_ok is False
        assert isinstance(result, prefix_ns["APIErr404"])

    def test_transport_error(self, prefix_ns):
        API = prefix_ns["API"]

        with respx.mock:
            respx.get(re.compile(r".*")).mock(
                side_effect=httpx.HTTPError("timeout")
            )
            client = httpx.Client()
            result = API.fetch(client, id="1")

        assert isinstance(result, prefix_ns["TransportErr"])


# ---------------------------------------------------------------------------
# 6. Multi-method REST struct
# ---------------------------------------------------------------------------


class TestRestMultiMethod:
    def test_get_user_method(self, multi_method_ns):
        API = multi_method_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/users/7").respond(
                json={"id": 7, "name": "Test"}, status_code=200
            )
            client = httpx.Client()
            result = API.get_user(client, id="7")

        assert result.is_ok is True
        assert route.called

    def test_list_users_method(self, multi_method_ns):
        API = multi_method_ns["API"]

        with respx.mock:
            route = respx.get("https://api.example.com/users").respond(
                json={"id": 0, "name": ""}, status_code=200
            )
            client = httpx.Client()
            result = API.list_users(client)

        assert result.is_ok is True
        assert route.called

    def test_shared_error_dispatch(self, multi_method_ns):
        API = multi_method_ns["API"]

        with respx.mock:
            respx.get(re.compile(r".*")).respond(
                json={"code": 404, "message": "not found"}, status_code=404
            )
            client = httpx.Client()
            r1 = API.get_user(client, id="1")
            r2 = API.list_users(client)

        assert isinstance(r1, multi_method_ns["APIErr404"])
        assert isinstance(r2, multi_method_ns["APIErr404"])


# ---------------------------------------------------------------------------
# 7. response-path extraction
# ---------------------------------------------------------------------------


class TestRestResponsePath:
    def test_ok_returns_full_body(self, response_path_ns):
        API = response_path_ns["API"]

        with respx.mock:
            respx.get("https://api.example.com/me").respond(
                json={"id": 1, "name": "TestUser"},
                status_code=200,
            )
            client = httpx.Client()
            result = API.fetch(client)

        assert result.is_ok is True
        assert result.value == {"id": 1, "name": "TestUser"}
