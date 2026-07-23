"""Integration tests for ``MethodFetch`` (HTML struct with ``@request``).

Verifies the generated ``fetch`` / ``async_fetch`` classmethods are
library-correct for all three Python HTTP strategies:

* httpx  — sync ``fetch`` + async ``async_fetch`` (``raise_for_status``,
  ``.text`` / ``.json()`` with no ``await``).
* aiohttp — async-only ``async_fetch`` (``async with ... as resp``,
  ``await raise_for_status`` / ``await text()`` / ``await json()``); no
  synchronous ``fetch`` emitted.
* requests — sync ``fetch`` + ``async_fetch`` delegating to the sync one via
  ``loop.run_in_executor``.

Codegen smoke tests inspect the generated source. Runtime tests exec the
generated module and exercise the network layer through respx (httpx),
aioresponses (aiohttp) and responses (requests).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from kdlquery import Severity

from ssc_codegen.core import parse_module
from ssc_codegen.targets.python import PY_BS4_CONVERTER as CONVERTER

SCHEMAS_DIR = Path(__file__).parent / "schemas"

HTML_BODY = "<html><body><h1>Hello World</h1></body></html>"
URL = "https://example.com/posts/1"

QUERY_PH_BODY = "<html><body><img src='x'></body></html>"
QUERY_PH_URL = "https://example.com/?32-alice"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(src: str):
    module, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError("; ".join(d.message for d in errors))
    return module


def _generate_code(src: str, *, http_client: str) -> str:
    module = _parse(src)
    return CONVERTER.convert(module, http_client=http_client)


def _exec(src: str, *, http_client: str) -> dict:
    code = _generate_code(src, http_client=http_client)
    namespace: dict = {}
    exec(code, namespace)  # noqa: S102
    return namespace


@pytest.fixture(scope="module")
def schema_src() -> str:
    return (SCHEMAS_DIR / "23_html_fetch.kdl").read_text()


@pytest.fixture(scope="module")
def query_ph_src() -> str:
    return (SCHEMAS_DIR / "24_html_fetch_query_placeholder.kdl").read_text()


# ---------------------------------------------------------------------------
# 1. Codegen smoke — httpx
# ---------------------------------------------------------------------------


class TestHttpxCodegen:
    def test_emits_both_sync_and_async(self, schema_src: str):
        code = _generate_code(schema_src, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client" in code
        assert "async def async_fetch(cls, client: httpx.AsyncClient" in code

    def test_uses_httpx_response_semantics(self, schema_src: str):
        code = _generate_code(schema_src, http_client="httpx")
        # httpx: raise_for_status + .text are sync (no await)
        assert "_resp.raise_for_status()" in code
        assert "_body = _resp.text" in code
        assert "await _resp.raise_for_status()" not in code
        assert "await _resp.text()" not in code
        assert "async with client.request(" not in code


# ---------------------------------------------------------------------------
# 2. Codegen smoke — aiohttp
# ---------------------------------------------------------------------------


class TestAioHttpCodegen:
    def test_does_not_emit_sync_fetch(self, schema_src: str):
        code = _generate_code(schema_src, http_client="aiohttp")
        assert "def fetch(cls, client" not in code
        assert "client: aiohttp.ClientSession" in code

    def test_emits_async_with_context_manager(self, schema_src: str):
        code = _generate_code(schema_src, http_client="aiohttp")
        assert "async def async_fetch" in code
        assert "async with client.request(" in code
        assert ") as _resp:" in code

    def test_awaits_coroutine_api(self, schema_src: str):
        code = _generate_code(schema_src, http_client="aiohttp")
        # text()/json() are coroutines in aiohttp → must be awaited
        assert "await _resp.text()" in code
        # raise_for_status() is a regular sync method in aiohttp → NOT awaited
        assert "_resp.raise_for_status()" in code
        assert "await _resp.raise_for_status()" not in code


# ---------------------------------------------------------------------------
# 3. Codegen smoke — requests
# ---------------------------------------------------------------------------


class TestRequestsCodegen:
    def test_emits_both_sync_and_async(self, schema_src: str):
        code = _generate_code(schema_src, http_client="requests")
        assert "def fetch(cls, client: requests.Session" in code
        assert "async def async_fetch(cls, client: requests.Session" in code

    def test_async_delegates_via_to_thread(self, schema_src: str):
        code = _generate_code(schema_src, http_client="requests")
        assert "asyncio.to_thread(cls.fetch" in code
        assert "loop.run_in_executor" not in code

    def test_sync_uses_requests_semantics(self, schema_src: str):
        code = _generate_code(schema_src, http_client="requests")
        assert "_resp = client.request(" in code
        assert "_resp.raise_for_status()" in code
        assert "_body = _resp.text" in code


# ---------------------------------------------------------------------------
# 4. Runtime — httpx (respx)
# ---------------------------------------------------------------------------


class TestHttpxRuntime:
    def test_fetch_returns_parseable_instance(self, schema_src: str):
        import httpx
        import respx

        ns = _exec(schema_src, http_client="httpx")
        SimplePage = ns["SimplePage"]

        with respx.mock:
            respx.get(URL).respond(status_code=200, text=HTML_BODY)
            with httpx.Client() as client:
                page = SimplePage.fetch(client, id="1")

        assert page.parse()["title"] == "Hello World"

    def test_async_fetch_returns_parseable_instance(self, schema_src: str):
        import httpx
        import respx

        ns = _exec(schema_src, http_client="httpx")
        SimplePage = ns["SimplePage"]

        async def _run():
            with respx.mock:
                respx.get(URL).respond(status_code=200, text=HTML_BODY)
                async with httpx.AsyncClient() as client:
                    return await SimplePage.async_fetch(client, id="1")

        page = asyncio.run(_run())
        assert page.parse()["title"] == "Hello World"

    def test_404_raises_http_status_error(self, schema_src: str):
        import httpx
        import respx

        ns = _exec(schema_src, http_client="httpx")
        SimplePage = ns["SimplePage"]

        with respx.mock:
            respx.get(URL).respond(status_code=404, text="not found")
            with httpx.Client() as client:
                with pytest.raises(httpx.HTTPStatusError):
                    SimplePage.fetch(client, id="1")


# ---------------------------------------------------------------------------
# 5. Runtime — aiohttp (aioresponses)
# ---------------------------------------------------------------------------


class TestAioHttpRuntime:
    def test_async_fetch_returns_parseable_instance(self, schema_src: str):
        aiohttp = pytest.importorskip("aiohttp")
        aioresponses = pytest.importorskip("aioresponses")

        ns = _exec(schema_src, http_client="aiohttp")
        SimplePage = ns["SimplePage"]

        async def _run():
            with aioresponses.aioresponses() as mocked:
                mocked.get(URL, status=200, body=HTML_BODY)
                async with aiohttp.ClientSession() as session:
                    return await SimplePage.async_fetch(session, id="1")

        page = asyncio.run(_run())
        assert page.parse()["title"] == "Hello World"

    def test_404_raises_client_response_error(self, schema_src: str):
        aiohttp = pytest.importorskip("aiohttp")
        aioresponses = pytest.importorskip("aioresponses")

        ns = _exec(schema_src, http_client="aiohttp")
        SimplePage = ns["SimplePage"]

        async def _run():
            with aioresponses.aioresponses() as mocked:
                mocked.get(URL, status=404, body="not found")
                async with aiohttp.ClientSession() as session:
                    return await SimplePage.async_fetch(session, id="1")

        with pytest.raises(aiohttp.ClientResponseError):
            asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. Runtime — requests (responses)
# ---------------------------------------------------------------------------


class TestRequestsRuntime:
    def test_fetch_returns_parseable_instance(self, schema_src: str):
        import requests
        from responses import RequestsMock

        ns = _exec(schema_src, http_client="requests")
        SimplePage = ns["SimplePage"]

        with RequestsMock() as rsps:
            rsps.add(rsps.GET, URL, body=HTML_BODY, status=200)
            with requests.Session() as session:
                page = SimplePage.fetch(session, id="1")

        assert page.parse()["title"] == "Hello World"

    def test_async_fetch_delegates_to_sync(self, schema_src: str):
        import requests
        from responses import RequestsMock

        ns = _exec(schema_src, http_client="requests")
        SimplePage = ns["SimplePage"]

        async def _run():
            with RequestsMock() as rsps:
                rsps.add(rsps.GET, URL, body=HTML_BODY, status=200)
                with requests.Session() as session:
                    return await SimplePage.async_fetch(session, id="1")

        page = asyncio.run(_run())
        assert page.parse()["title"] == "Hello World"

    def test_404_raises_http_error(self, schema_src: str):
        import requests
        from responses import RequestsMock

        ns = _exec(schema_src, http_client="requests")
        SimplePage = ns["SimplePage"]

        with RequestsMock() as rsps:
            rsps.add(rsps.GET, URL, body="not found", status=404)
            with requests.Session() as session:
                with pytest.raises(requests.HTTPError):
                    SimplePage.fetch(session, id="1")


# ---------------------------------------------------------------------------
# 7. Query-string placeholder (bare-value form: ?32-{{username}})
# ---------------------------------------------------------------------------


class TestQueryPlaceholderCodegen:
    """Regression: placeholder inside a bare-value query string was lost.

    ``parse_qs("32-{{username}}")`` classified the token as a dict key with
    empty value; dict keys are never tokenized → no signature param and a
    literal ``params={'32-{{username}}': ''}`` in the body. Fixed by keeping
    the full URL when the query contains a placeholder.
    """

    def test_signature_has_username_kwarg_httpx(self, query_ph_src: str):
        code = _generate_code(query_ph_src, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client, *, username: str)" in code
        assert (
            "async def async_fetch(cls, client: httpx.AsyncClient, *, username: str)"
            in code
        )

    def test_signature_has_username_kwarg_aiohttp(self, query_ph_src: str):
        code = _generate_code(query_ph_src, http_client="aiohttp")
        assert (
            "async def async_fetch(cls, client: aiohttp.ClientSession, *, username: str)"
            in code
        )

    def test_url_fstring_renders_placeholder(self, query_ph_src: str):
        code = _generate_code(query_ph_src, http_client="httpx")
        assert 'f"https://example.com/?32-{username}"' in code

    def test_no_literal_placeholder_in_params(self, query_ph_src: str):
        code = _generate_code(query_ph_src, http_client="httpx")
        assert "{{username}}" not in code
        assert "params=" not in code


class TestQueryPlaceholderRuntime:
    def test_async_fetch_hits_templated_url(self, query_ph_src: str):
        httpx = pytest.importorskip("httpx")
        respx = pytest.importorskip("respx")

        ns = _exec(query_ph_src, http_client="httpx")
        ForumPage = ns["ForumPage"]

        with respx.mock:
            route = respx.get(QUERY_PH_URL).respond(
                status_code=200, text=QUERY_PH_BODY
            )
            with httpx.Client() as client:
                page = ForumPage.fetch(client, username="alice")

        assert route.called
        assert page.exists() is True
