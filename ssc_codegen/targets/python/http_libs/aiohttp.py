"""aiohttp HTTP client transport strategy for Python code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.python.http_libs.base import (
    HttpLibStrategy,
    _REST_SHARED_RUNTIME,
)


class AioHttpStrategy(HttpLibStrategy):
    """HTTP transport strategy using `aiohttp` (async-only).

    Attributes:
        import_line: ``"import aiohttp"``.
        sync_client_type: ``"aiohttp.ClientSession"``.
        async_client_type: ``"aiohttp.ClientSession"``.
        transport_exception: ``"aiohttp.ClientError"``.
        supports_sync_fetch: `False` (aiohttp only supports async I/O).
    """

    import_line = "import aiohttp"
    sync_client_type = "aiohttp.ClientSession"
    async_client_type = "aiohttp.ClientSession"
    transport_exception = "aiohttp.ClientError"

    # aiohttp is async-only: no synchronous ``fetch`` is generated.
    supports_sync_fetch = False

    def fetch_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate async fetch runtime source lines (`ssc_fetch_async`) for aiohttp.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).

        Returns:
            list[str]: Python source lines implementing `ssc_fetch_async`.
        """
        lines: list[str] = []
        if http_io in ("both", "async"):
            lines.extend(
                inspect.cleandoc(
                    """
                    async def ssc_fetch_async(
                        client: aiohttp.ClientSession,
                        method: str,
                        url: str,
                        response_path: str = '',
                        response_join: str = '',
                        **kw: Any,
                    ) -> str:
                        async with client.request(method, url, **kw) as _resp:
                            _resp.raise_for_status()
                            if response_path:
                                _data = await _resp.json(content_type=None)
                                for _p in response_path.split('.'):
                                    _data = _data[_p]
                                _body = response_join.join(_data) if response_join else _data
                            else:
                                _body = await _resp.text()
                            return _body
                    """
                ).splitlines()
            )
            lines.append("")
        return lines

    def rest_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate REST runtime source lines with aiohttp transport exception handling.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).
                Controls which call helpers (`ssc_rest_call` and/or `ssc_rest_call_async`)
                are included in the returned lines. Defaults to `"both"`.

        Returns:
            list[str]: List of Python code lines implementing REST runtime helpers with
            aiohttp-specific exception catching.
        """
        exc = self.transport_exception
        lines = [*_REST_SHARED_RUNTIME.splitlines(), "", ""]
        if http_io in ("both", "sync"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    def ssc_rest_call(
                        client: aiohttp.ClientSession,
                        matchers: List[ErrMatcher],
                        method: str,
                        url: str,
                        value_fn: Optional[Callable[[Any], _T]] = None,
                        **kw: Any,
                    ) -> Union[Ok[_T], Err]:
                        async def go() -> Union[Ok[_T], Err]:
                            try:
                                async with client.request(method, url, **kw) as resp:
                                    status = resp.status
                                    headers = {{k.lower(): v for k, v in resp.headers.items()}}
                                    try:
                                        body = await resp.json(content_type=None)
                                    except Exception:
                                        body = None
                            except {exc} as exc:
                                return TransportErr(cause=repr(exc))
                            err = ssc_dispatch_err(matchers, status, headers, body)
                            if err is not None:
                                return err
                            value = body if value_fn is None else value_fn(body)
                            return Ok(status=status, headers=headers, value=value)
                        try:
                            asyncio.get_running_loop()
                        except RuntimeError:
                            return asyncio.run(go())
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            return pool.submit(asyncio.run, go()).result()
                    """
                ).splitlines()
            )
            lines.extend(["", ""])
        if http_io in ("both", "async"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    async def ssc_rest_call_async(
                        client: aiohttp.ClientSession,
                        matchers: List[ErrMatcher],
                        method: str,
                        url: str,
                        value_fn: Optional[Callable[[Any], _T]] = None,
                        **kw: Any,
                    ) -> Union[Ok[_T], Err]:
                        try:
                            async with client.request(method, url, **kw) as resp:
                                status = resp.status
                                headers = {{k.lower(): v for k, v in resp.headers.items()}}
                                try:
                                    body = await resp.json(content_type=None)
                                except Exception:
                                    body = None
                        except {exc} as exc:
                            return TransportErr(cause=repr(exc))
                        err = ssc_dispatch_err(matchers, status, headers, body)
                        if err is not None:
                            return err
                        value = body if value_fn is None else value_fn(body)
                        return Ok(status=status, headers=headers, value=value)
                    """
                ).splitlines()
            )
            lines.append("")
        return lines
