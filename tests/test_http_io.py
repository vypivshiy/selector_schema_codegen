"""Tests for HTTP I/O mode parameterization (--http-io)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
import respx
from typer.testing import CliRunner

from ssc_codegen.core import parse_module
from ssc_codegen.generation.runtime import runtime_module_content
from ssc_codegen.main import app
from ssc_codegen.targets.python.html_libs.bs4 import Bs4DomSpelling
from ssc_codegen.targets.python.http_libs.aiohttp import AioHttpStrategy
from ssc_codegen.targets.python.http_libs.httpx import (
    Httpx2Strategy,
    HttpxStrategy,
)
from ssc_codegen.targets.python.http_libs.requests import RequestsStrategy
from ssc_codegen.targets.python.rest import runtime_export_names
from ssc_codegen.targets.python.visitor import PythonVisitor
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.spec import TargetSpec
from tests.test_rest_api import _exec_with_runtime

runner = CliRunner()

_REST_KDL = """
json Item { id int; title str }
struct Api type=rest {
    @request response=Item \"\"\"
    GET /items/1 HTTP/1.1
    Host: api.example.com
    \"\"\"
}
"""

_FETCH_HTML_KDL = """
struct Page {
    @request \"\"\"
    GET /page HTTP/1.1
    Host: example.com
    \"\"\"
    title {
        css "h1"
        text
    }
}
"""


def _converter(http_io: str = "both") -> PythonVisitor:
    return PythonVisitor(dom_spelling_cls=Bs4DomSpelling, http_io=http_io)


class TestTargetSpecAndResolution:
    def test_http_io_defaults_to_none_on_spec(self) -> None:
        spec = TargetSpec(lang="python")
        assert spec.http_io is None

    def test_resolve_python_defaults_to_both(self) -> None:
        profile = resolve(TargetSpec(lang="python"))
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.http_io == "both"

    @pytest.mark.parametrize("mode", ["both", "sync", "async"])
    def test_resolve_python_with_valid_http_io(self, mode: str) -> None:
        profile = resolve(TargetSpec(lang="python", http_io=mode))
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.http_io == mode

    def test_resolve_python_rejects_invalid_http_io(self) -> None:
        with pytest.raises(
            ResolutionError, match="Invalid --http-io 'invalid'"
        ):
            resolve(TargetSpec(lang="python", http_io="invalid"))

    def test_resolve_python_rejects_aiohttp_sync(self) -> None:
        with pytest.raises(
            ResolutionError,
            match="aiohttp does not support synchronous I/O",
        ):
            resolve(
                TargetSpec(lang="python", http_client="aiohttp", http_io="sync")
            )

    @pytest.mark.parametrize("mode", ["both", "async"])
    def test_resolve_python_permits_aiohttp_async_and_both(
        self, mode: str
    ) -> None:
        profile = resolve(
            TargetSpec(lang="python", http_client="aiohttp", http_io=mode)
        )
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.http_io == mode

    def test_resolve_python_permits_requests_async(self) -> None:
        profile = resolve(
            TargetSpec(lang="python", http_client="requests", http_io="async")
        )
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.http_io == "async"

    @pytest.mark.parametrize("lang", ["javascript", "js", "go", "rust"])
    @pytest.mark.parametrize("mode", ["both", "sync", "async", "invalid"])
    def test_resolve_rejects_http_io_for_non_python(
        self, lang: str, mode: str
    ) -> None:
        with pytest.raises(
            ResolutionError, match="--http-io is not applicable"
        ):
            resolve(TargetSpec(lang=lang, http_io=mode))

    def test_resolve_rejects_http_io_both_for_javascript(self) -> None:
        with pytest.raises(
            ResolutionError,
            match=r"--http-io is not applicable for JavaScript\.",
        ):
            resolve(TargetSpec(lang="javascript", http_io="both"))


class TestCliOptions:
    def test_cli_generate_python_accepts_http_io(self, tmp_path: Path) -> None:
        schema = tmp_path / "api.kdl"
        schema.write_text(_REST_KDL, encoding="utf-8")
        out_sync = tmp_path / "out_sync"
        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(out_sync),
                "--http-io",
                "sync",
            ],
        )
        assert result.exit_code == 0, result.output
        code = (out_sync / "api.py").read_text(encoding="utf-8")
        assert "def fetch(cls," in code
        assert "async def async_fetch(" not in code

    def test_cli_rejects_invalid_http_io(self, tmp_path: Path) -> None:
        schema = tmp_path / "api.kdl"
        schema.write_text(_REST_KDL, encoding="utf-8")
        output = tmp_path / "out"
        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(output),
                "--http-io",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid --http-io 'invalid'" in result.output

    def test_cli_rejects_aiohttp_sync(self, tmp_path: Path) -> None:
        schema = tmp_path / "api.kdl"
        schema.write_text(_REST_KDL, encoding="utf-8")
        output = tmp_path / "out"
        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(output),
                "--http-client",
                "aiohttp",
                "--http-io",
                "sync",
            ],
        )
        assert result.exit_code == 1
        assert "aiohttp does not support synchronous I/O" in result.output


class TestCodegenMethodFilteringFetch:
    def test_httpx_fetch_both(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("both")
        code = converter.convert(module, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client" in code
        assert "async def async_fetch(cls, client: httpx.AsyncClient" in code

    def test_httpx_fetch_sync_only(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("sync")
        code = converter.convert(module, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client" in code
        assert "async_fetch" not in code
        assert "httpx.AsyncClient" not in code

    def test_httpx_fetch_async_only(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("async")
        code = converter.convert(module, http_client="httpx")
        assert "async def async_fetch(cls, client: httpx.AsyncClient" in code
        assert "def fetch(" not in code
        assert "httpx.Client" not in code

    def test_requests_fetch_both(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("both")
        code = converter.convert(module, http_client="requests")
        assert "def fetch(cls, client: requests.Session" in code
        assert "async def async_fetch(cls, client: requests.Session" in code
        assert "cls.fetch" in code

    def test_requests_fetch_sync_only(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("sync")
        code = converter.convert(module, http_client="requests")
        assert "def fetch(cls, client: requests.Session" in code
        assert "async_fetch" not in code

    def test_requests_fetch_async_delegation_preserves_sync_implementation(
        self,
    ) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("async")
        code = converter.convert(module, http_client="requests")
        # Public fetch is omitted
        assert "def fetch(cls," not in code
        # Private _fetch is emitted
        assert "def _fetch(cls, client: requests.Session" in code
        assert "async def async_fetch(cls, client: requests.Session" in code
        # async_fetch delegates to cls._fetch
        assert "cls._fetch" in code

    def test_aiohttp_fetch_async_only(self) -> None:
        module, _ = parse_module(_FETCH_HTML_KDL)
        converter = _converter("async")
        code = converter.convert(module, http_client="aiohttp")
        assert (
            "async def async_fetch(cls, client: aiohttp.ClientSession" in code
        )
        assert "def fetch(" not in code


class TestCodegenMethodFilteringRest:
    def test_httpx_rest_both(self) -> None:
        module, _ = parse_module(_REST_KDL)
        converter = _converter("both")
        code = converter.convert(module, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client" in code
        assert "async def async_fetch(cls, client: httpx.AsyncClient" in code
        assert "ssc_rest_call(" in code
        assert "ssc_rest_call_async(" in code

    def test_httpx_rest_sync_only(self) -> None:
        module, _ = parse_module(_REST_KDL)
        converter = _converter("sync")
        code = converter.convert(module, http_client="httpx")
        assert "def fetch(cls, client: httpx.Client" in code
        assert "async_fetch" not in code
        assert "httpx.AsyncClient" not in code
        assert "ssc_rest_call(" in code
        assert "ssc_rest_call_async" not in code

    def test_httpx_rest_async_only(self) -> None:
        module, _ = parse_module(_REST_KDL)
        converter = _converter("async")
        code = converter.convert(module, http_client="httpx")
        assert "async def async_fetch(cls, client: httpx.AsyncClient" in code
        assert "def fetch(" not in code
        assert "httpx.Client" not in code
        assert "ssc_rest_call_async(" in code
        assert "def ssc_rest_call(" not in code

    def test_httpx2_rest_sync_and_async_types(self) -> None:
        module, _ = parse_module(_REST_KDL)
        code_sync = _converter("sync").convert(module, http_client="httpx2")
        assert "import httpx2" in code_sync
        assert "client: httpx2.Client" in code_sync
        assert "httpx2.AsyncClient" not in code_sync

        code_async = _converter("async").convert(module, http_client="httpx2")
        assert "import httpx2" in code_async
        assert "client: httpx2.AsyncClient" in code_async
        assert "client: httpx2.Client" not in code_async


class TestRuntimeExportNamesAndSeparateRuntime:
    def test_runtime_export_names_filtering(self) -> None:
        module, _ = parse_module(_REST_KDL)
        names_both = runtime_export_names(module, http_io="both")
        assert "ssc_rest_call" in names_both
        assert "ssc_rest_call_async" in names_both

        names_sync = runtime_export_names(module, http_io="sync")
        assert "ssc_rest_call" in names_sync
        assert "ssc_rest_call_async" not in names_sync

        names_async = runtime_export_names(module, http_io="async")
        assert "ssc_rest_call_async" in names_async
        assert "ssc_rest_call" not in names_async

    def test_runtime_module_content_always_retains_both_helpers(self) -> None:
        module, _ = parse_module(_REST_KDL)
        # Even when called directly or for any strategy, runtime_module_content retains both
        rt_httpx = runtime_module_content(module, http_strategy=HttpxStrategy())
        assert "def ssc_rest_call(" in rt_httpx
        assert "async def ssc_rest_call_async(" in rt_httpx

        rt_aiohttp = runtime_module_content(
            module, http_strategy=AioHttpStrategy()
        )
        assert "def ssc_rest_call(" in rt_aiohttp
        assert "async def ssc_rest_call_async(" in rt_aiohttp

        rt_requests = runtime_module_content(
            module, http_strategy=RequestsStrategy()
        )
        assert "def ssc_rest_call(" in rt_requests
        assert "async def ssc_rest_call_async(" in rt_requests

    def test_separate_runtime_parser_imports_only_needed_helper(
        self, tmp_path: Path
    ) -> None:
        module, _ = parse_module(_REST_KDL)
        converter_sync = _converter("sync")
        res_sync = converter_sync.convert_all(
            module,
            http_client="httpx",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        parser_sync = res_sync[""]
        assert "from .sscgen_runtime import " in parser_sync
        assert "ssc_rest_call" in parser_sync
        assert "ssc_rest_call_async" not in parser_sync

        converter_async = _converter("async")
        res_async = converter_async.convert_all(
            module,
            http_client="httpx",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        parser_async = res_async[""]
        assert "from .sscgen_runtime import " in parser_async
        assert "ssc_rest_call_async" in parser_async
        assert "ssc_rest_call," not in parser_async
        assert "ssc_rest_call " not in parser_async


class TestInlineModeRuntimeFiltering:
    def test_inline_mode_httpx_filtering(self) -> None:
        module, _ = parse_module(_REST_KDL)
        code_sync = _converter("sync").convert(module, http_client="httpx")
        assert "def ssc_rest_call(" in code_sync
        assert "async def ssc_rest_call_async(" not in code_sync

        code_async = _converter("async").convert(module, http_client="httpx")
        assert "async def ssc_rest_call_async(" in code_async
        assert "def ssc_rest_call(" not in code_async

    def test_inline_mode_aiohttp_filtering(self) -> None:
        module, _ = parse_module(_REST_KDL)
        code_async = _converter("async").convert(module, http_client="aiohttp")
        assert "async def ssc_rest_call_async(" in code_async
        assert "def ssc_rest_call(" not in code_async

    def test_inline_mode_requests_filtering(self) -> None:
        module, _ = parse_module(_REST_KDL)
        code_sync = _converter("sync").convert(module, http_client="requests")
        assert "def ssc_rest_call(" in code_sync
        assert "async def ssc_rest_call_async(" not in code_sync

        code_async = _converter("async").convert(module, http_client="requests")
        assert "async def ssc_rest_call_async(" in code_async
        # requests async delegates to ssc_rest_call so it is preserved
        assert "def ssc_rest_call(" in code_async


class TestRuntimeExecution:
    @respx.mock
    def test_exec_httpx_sync_and_async_with_runtime(self) -> None:
        respx.get("https://api.example.com/items/1").respond(
            200, json={"id": 1, "title": "Widget"}
        )
        import httpx

        module, _ = parse_module(_REST_KDL)
        rt_src = runtime_module_content(module, http_strategy=HttpxStrategy())

        # Sync execution
        p_sync = _converter("sync").convert(
            module,
            http_client="httpx",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        ns_sync = _exec_with_runtime(p_sync, rt_src)
        ApiSync = ns_sync["Api"]
        assert hasattr(ApiSync, "fetch")
        assert not hasattr(ApiSync, "async_fetch")
        with httpx.Client() as client:
            res = ApiSync.fetch(client)
        assert res.is_ok is True
        assert res.value == {"id": 1, "title": "Widget"}

        # Async execution
        p_async = _converter("async").convert(
            module,
            http_client="httpx",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        ns_async = _exec_with_runtime(p_async, rt_src)
        ApiAsync = ns_async["Api"]
        assert not hasattr(ApiAsync, "fetch")
        assert hasattr(ApiAsync, "async_fetch")

        async def _run():
            async with httpx.AsyncClient() as client:
                return await ApiAsync.async_fetch(client)

        res_a = asyncio.run(_run())
        assert res_a.is_ok is True
        assert res_a.value == {"id": 1, "title": "Widget"}

    def test_exec_httpx2_sync_and_async_with_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpx

        monkeypatch.setitem(sys.modules, "httpx2", httpx)
        with respx.mock:
            respx.get("https://api.example.com/items/1").respond(
                200, json={"id": 1, "title": "Gadget"}
            )
            module, _ = parse_module(_REST_KDL)
            rt_src = runtime_module_content(
                module, http_strategy=Httpx2Strategy()
            )

            # Sync
            p_sync = _converter("sync").convert(
                module,
                http_client="httpx2",
                separate_runtime=True,
                runtime_module="sscgen_runtime",
            )
            ns_sync = _exec_with_runtime(p_sync, rt_src)
            ApiSync = ns_sync["Api"]
            assert hasattr(ApiSync, "fetch")
            assert not hasattr(ApiSync, "async_fetch")
            with httpx.Client() as client:
                res = ApiSync.fetch(client)
            assert res.is_ok is True
            assert res.value == {"id": 1, "title": "Gadget"}

            # Async
            p_async = _converter("async").convert(
                module,
                http_client="httpx2",
                separate_runtime=True,
                runtime_module="sscgen_runtime",
            )
            ns_async = _exec_with_runtime(p_async, rt_src)
            ApiAsync = ns_async["Api"]
            assert not hasattr(ApiAsync, "fetch")
            assert hasattr(ApiAsync, "async_fetch")

            async def _run():
                async with httpx.AsyncClient() as client:
                    return await ApiAsync.async_fetch(client)

            res_a = asyncio.run(_run())
            assert res_a.is_ok is True
            assert res_a.value == {"id": 1, "title": "Gadget"}

    def test_exec_aiohttp_async_with_runtime(self) -> None:
        aiohttp = pytest.importorskip("aiohttp")
        aioresponses = pytest.importorskip("aioresponses")

        module, _ = parse_module(_REST_KDL)
        rt_src = runtime_module_content(module, http_strategy=AioHttpStrategy())
        parser_src = _converter("async").convert(
            module,
            http_client="aiohttp",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        ns = _exec_with_runtime(parser_src, rt_src)
        Api = ns["Api"]
        assert not hasattr(Api, "fetch")
        assert hasattr(Api, "async_fetch")

        async def _run():
            with aioresponses.aioresponses() as mocked:
                mocked.get(
                    "https://api.example.com/items/1",
                    status=200,
                    body=b'{"id": 1, "title": "Aio"}',
                    headers={"Content-Type": "application/json"},
                )
                async with aiohttp.ClientSession() as session:
                    return await Api.async_fetch(session)

        res = asyncio.run(_run())
        assert res.is_ok is True
        assert res.value == {"id": 1, "title": "Aio"}

    def test_exec_requests_sync_and_async_with_runtime(self) -> None:
        import requests
        from responses import RequestsMock

        module, _ = parse_module(_REST_KDL)
        rt_src = runtime_module_content(
            module, http_strategy=RequestsStrategy()
        )

        # Sync
        p_sync = _converter("sync").convert(
            module,
            http_client="requests",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        ns_sync = _exec_with_runtime(p_sync, rt_src)
        ApiSync = ns_sync["Api"]
        assert hasattr(ApiSync, "fetch")
        assert not hasattr(ApiSync, "async_fetch")
        with RequestsMock() as rsps:
            rsps.add(
                rsps.GET,
                "https://api.example.com/items/1",
                json={"id": 1, "title": "ReqSync"},
                status=200,
            )
            with requests.Session() as s:
                res_sync = ApiSync.fetch(s)
        assert res_sync.is_ok is True
        assert res_sync.value == {"id": 1, "title": "ReqSync"}

        # Async delegation via worker thread
        p_async = _converter("async").convert(
            module,
            http_client="requests",
            separate_runtime=True,
            runtime_module="sscgen_runtime",
        )
        ns_async = _exec_with_runtime(p_async, rt_src)
        ApiAsync = ns_async["Api"]
        assert not hasattr(ApiAsync, "fetch")
        assert hasattr(ApiAsync, "async_fetch")

        async def _run():
            with RequestsMock() as rsps:
                rsps.add(
                    rsps.GET,
                    "https://api.example.com/items/1",
                    json={"id": 1, "title": "ReqAsync"},
                    status=200,
                )
                with requests.Session() as s:
                    return await ApiAsync.async_fetch(s)

        res_async = asyncio.run(_run())
        assert res_async.is_ok is True
        assert res_async.value == {"id": 1, "title": "ReqAsync"}

    def test_exec_requests_html_fetch_async_delegation(self) -> None:
        import requests
        from responses import RequestsMock

        module, _ = parse_module(_FETCH_HTML_KDL)
        code = _converter("async").convert(module, http_client="requests")
        ns: dict[str, Any] = {}
        exec(compile(code, "<inline>", "exec"), ns)  # noqa: S102
        Page = ns["Page"]
        assert not hasattr(Page, "fetch")
        assert hasattr(Page, "_fetch")
        assert hasattr(Page, "async_fetch")

        async def _run():
            with RequestsMock() as rsps:
                rsps.add(
                    rsps.GET,
                    "https://example.com/page",
                    body="<html><body><h1>Scraped</h1></body></html>",
                    status=200,
                )
                with requests.Session() as s:
                    return await Page.async_fetch(s)

        res_page = asyncio.run(_run())
        data = res_page.parse()
        assert data["title"] == "Scraped"
