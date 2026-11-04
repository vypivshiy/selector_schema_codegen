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
    exec(code, namespace)
    return namespace


@pytest.fixture(scope="module")
def schema_src() -> str:
    return (SCHEMAS_DIR / "23_html_fetch.kdl").read_text()


@pytest.fixture(scope="module")
def query_ph_src() -> str:
    return (SCHEMAS_DIR / "24_html_fetch_query_placeholder.kdl").read_text()


# ---------------------------------------------------------------------------
# 1. Runtime — httpx (respx)
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
            with (
                httpx.Client() as client,
                pytest.raises(httpx.HTTPStatusError),
            ):
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
        assert not hasattr(SimplePage, "fetch")

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
            with (
                requests.Session() as session,
                pytest.raises(requests.HTTPError),
            ):
                SimplePage.fetch(session, id="1")


# ---------------------------------------------------------------------------
# 7. Query-string placeholder (bare-value form: ?32-{{username}})
# ---------------------------------------------------------------------------


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


class TestHtmlFetchMergeKwargsAndSeparateRuntime:
    """Verify MethodFetch delegates to ssc_fetch/ssc_fetch_async + ssc_merge_kwargs,
    filtering None optional params/headers and shallow-merging caller kwargs."""

    _SCHEMA = '''
struct SearchPage {
    @request """
    GET /search?q={{q:str}}&lang={{lang:str?}} HTTP/1.1
    Host: example.com
    X-Static: 1
    X-Opt: {{opt_hdr:str?}}
    """
    title { css "h1"; text }
}
'''

    def test_fetch_filters_none_and_merges_caller_kwargs(self):
        import httpx
        import respx

        ns = _exec(self._SCHEMA, http_client="httpx")
        SearchPage = ns["SearchPage"]

        with respx.mock as mock:
            route = mock.get("https://example.com/search").respond(
                status_code=200, text=HTML_BODY
            )
            with httpx.Client() as client:
                page = SearchPage.fetch(
                    client,
                    q="rust",
                    headers={"X-Caller": "2"},
                    params={"page": "3"},
                )

            assert page.parse()["title"] == "Hello World"
            sent = route.calls.last.request
            assert dict(sent.url.params) == {"q": "rust", "page": "3"}
            assert sent.headers["x-static"] == "1"
            assert sent.headers["x-caller"] == "2"
            assert "x-opt" not in sent.headers
