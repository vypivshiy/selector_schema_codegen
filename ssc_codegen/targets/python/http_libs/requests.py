"""requests HTTP client transport strategy for Python code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.python.http_libs.base import (
    HttpLibStrategy,
    _REST_SHARED_RUNTIME,
)


class RequestsStrategy(HttpLibStrategy):
    """HTTP transport strategy using `requests` (sync, async via worker threads).

    Attributes:
        import_line: ``"import requests"``.
        sync_client_type: ``"requests.Session"``.
        async_client_type: ``"requests.Session"``.
        transport_exception: ``"requests.RequestException"``.
        async_fetch_delegates_to_sync: `True` (delegates async to `run_in_executor`).
    """

    import_line = "import requests"
    sync_client_type = "requests.Session"
    async_client_type = "requests.Session"
    transport_exception = "requests.RequestException"

    # requests has no native async API: async_fetch wraps the sync fetch via
    # asyncio.to_thread (worker thread, non-blocking). See emit_method_fetch.
    async_fetch_delegates_to_sync = True

    def fetch_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate fetch runtime source lines (`ssc_fetch`) for requests.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).

        Returns:
            list[str]: Python source lines implementing `ssc_fetch`.
        """
        lines: list[str] = []
        if http_io in ("both", "sync", "async"):
            lines.extend(
                inspect.cleandoc(
                    """
                    def ssc_fetch(
                        client: requests.Session,
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
        return lines

    def rest_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate REST runtime source lines with requests transport exception handling.

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).
                Controls which call helpers (`ssc_rest_call` and/or `ssc_rest_call_async`)
                are included in the returned lines. Defaults to `"both"`.

        Returns:
            list[str]: List of Python code lines implementing REST runtime helpers with
            requests-specific exception catching.
        """
        exc = self.transport_exception
        lines = [*_REST_SHARED_RUNTIME.splitlines(), "", ""]
        # ssc_rest_call is needed for sync/both modes and as execution delegate for async mode
        if http_io in ("both", "sync", "async"):
            lines.extend(
                inspect.cleandoc(
                    f"""
                    def ssc_rest_call(
                        client: requests.Session,
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
                    """
                    async def ssc_rest_call_async(
                        client: requests.Session,
                        matchers: List[ErrMatcher],
                        method: str,
                        url: str,
                        value_fn: Optional[Callable[[Any], _T]] = None,
                        **kw: Any,
                    ) -> Union[Ok[_T], Err]:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(
                            None,
                            lambda: ssc_rest_call(
                                client, matchers, method, url, value_fn, **kw
                            ),
                        )
                    """
                ).splitlines()
            )
            lines.append("")
        return lines
