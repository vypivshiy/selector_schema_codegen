"""httpx HTTP client transport strategy for Python code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.python.http_libs.base import (
    HttpLibStrategy,
    _REST_SHARED_RUNTIME,
)

HTTPX_FALLBACK_IMPORT = """try:
    import httpx2 as httpx
except ImportError:
    import httpx"""


class HttpxStrategy(HttpLibStrategy):
    """HTTP transport strategy using `httpx` (sync and async) with `httpx2` fallback.

    Attributes:
        import_line: Fallback import block attempting ``httpx2`` before ``httpx``.
        sync_client_type: ``"httpx.Client"``.
        async_client_type: ``"httpx.AsyncClient"``.
        transport_exception: ``"httpx.HTTPError"``.
    """

    import_line = HTTPX_FALLBACK_IMPORT
    sync_client_type = "httpx.Client"
    async_client_type = "httpx.AsyncClient"
    transport_exception = "httpx.HTTPError"

    def fetch_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate fetch runtime source lines (`ssc_fetch`, `ssc_fetch_async`) for httpx.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).

        Returns:
            list[str]: Python source lines implementing `ssc_fetch` and/or `ssc_fetch_async`.
        """
        lines: list[str] = []
        if http_io in ("both", "sync"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    def ssc_fetch(
                        client: {self.sync_client_type},
                        method: str,
                        url: str,
                        response_path: str = '',
                        response_join: str = '',
                        **kw: Any,
                    ) -> str:
                        _resp = client.request(method, url, **kw)
                        _resp.raise_for_status()
                        if response_path:
                            _data = _resp.json()
                            for _p in response_path.split('.'):
                                _data = _data[_p]
                            _body = response_join.join(_data) if response_join else _data
                        else:
                            _body = _resp.text
                        return _body
                    """
                ).splitlines()
            )
            lines.append("")
        if http_io in ("both", "async"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    async def ssc_fetch_async(
                        client: {self.async_client_type},
                        method: str,
                        url: str,
                        response_path: str = '',
                        response_join: str = '',
                        **kw: Any,
                    ) -> str:
                        _resp = await client.request(method, url, **kw)
                        _resp.raise_for_status()
                        if response_path:
                            _data = _resp.json()
                            for _p in response_path.split('.'):
                                _data = _data[_p]
                            _body = response_join.join(_data) if response_join else _data
                        else:
                            _body = _resp.text
                        return _body
                    """
                ).splitlines()
            )
            lines.append("")
        return lines

    def rest_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate REST runtime source lines with httpx transport exception handling.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).
                Controls which call helpers (`ssc_rest_call` and/or `ssc_rest_call_async`)
                are included in the returned lines. Defaults to `"both"`.

        Returns:
            list[str]: List of Python code lines implementing REST runtime helpers with
            httpx-specific exception catching.
        """
        exc = self.transport_exception
        lines = [*_REST_SHARED_RUNTIME.splitlines(), "", ""]
        if http_io in ("both", "sync"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    def ssc_rest_call(
                        client: {self.sync_client_type},
                        matchers: List[ErrMatcher],
                        method: str,
                        url: str,
                        value_fn: Optional[Callable[[Any], _T]] = None,
                        **kw: Any,
                    ) -> Union[Ok[_T], Err]:
                        try:
                            resp = client.request(method, url, **kw)
                            status = resp.status_code
                            headers = {{k.lower(): v for k, v in resp.headers.items()}}
                            try:
                                body = resp.json()
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
            lines.extend(["", ""])
        if http_io in ("both", "async"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    async def ssc_rest_call_async(
                        client: {self.async_client_type},
                        matchers: List[ErrMatcher],
                        method: str,
                        url: str,
                        value_fn: Optional[Callable[[Any], _T]] = None,
                        **kw: Any,
                    ) -> Union[Ok[_T], Err]:
                        try:
                            resp = await client.request(method, url, **kw)
                            status = resp.status_code
                            headers = {{k.lower(): v for k, v in resp.headers.items()}}
                            try:
                                body = resp.json()
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


class Httpx2Strategy(HttpxStrategy):
    """HTTP transport strategy using strict `httpx2` (sync and async).

    Attributes:
        import_line: ``"import httpx2"``.
        sync_client_type: ``"httpx2.Client"``.
        async_client_type: ``"httpx2.AsyncClient"``.
        transport_exception: ``"httpx2.HTTPError"``.
    """

    import_line = "import httpx2"
    sync_client_type = "httpx2.Client"
    async_client_type = "httpx2.AsyncClient"
    transport_exception = "httpx2.HTTPError"
