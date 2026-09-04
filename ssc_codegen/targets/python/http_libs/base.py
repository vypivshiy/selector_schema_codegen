"""Abstract base class and contract for Python HTTP client transport strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod


class HttpLibStrategy(ABC):
    """HTTP client library strategy for REST and fetch code generation.

    Encapsulates all network library-specific requirements:
    import statements, synchronous/asynchronous client type annotations,
    transport exception classes, runtime error dispatching helpers
    (`ssc_rest_call`, `ssc_rest_call_async`), and method body generation for
    `MethodFetch`.

    Attributes:
        import_line: Verbatim import statement line (e.g. ``"import httpx"``).
        sync_client_type: Type annotation for synchronous client parameter (e.g. ``"httpx.Client"``).
        async_client_type: Type annotation for async client parameter (e.g. ``"httpx.AsyncClient"``).
        transport_exception: Fully qualified exception class name caught during network requests
            (e.g. ``"httpx.HTTPError"``, ``"aiohttp.ClientError"``, ``"requests.RequestException"``).
        supports_sync_fetch: If `True`, emits a synchronous `fetch` classmethod. If `False`
            (as in `aiohttp`), only `async_fetch` is generated.
        async_fetch_delegates_to_sync: If `True` (as in `requests`), `async_fetch` delegates
            to the synchronous `fetch` via `asyncio.to_thread` / `run_in_executor`.
    """

    # === DATA (override in concrete subclasses) ===
    import_line: str = ""
    sync_client_type: str = ""
    async_client_type: str = ""
    transport_exception: str = ""

    # === FETCH BEHAVIOR (override in concrete subclasses) ===

    supports_sync_fetch: bool = True
    async_fetch_delegates_to_sync: bool = False

    # === BEHAVIOR ===

    @abstractmethod
    def rest_runtime_lines(self) -> list[str]:
        """Generate REST runtime source lines (`Ok`, `Err`, `ssc_rest_call`, etc.).

        Returns:
            List of Python code lines implementing the REST runtime helpers with
            library-specific transport exception catching.
        """
        ...

    def fetch_body_lines(
        self,
        *,
        is_async: bool,
        request_call: str,
        kwargs_lines: list[str],
        response_path: str,
        response_join: str,
        i2: str,
        i3: str,
    ) -> list[str]:
        """Generate statements inside a `MethodFetch` parser classmethod.

        Args:
            is_async: `True` if generating the asynchronous `async_fetch` method.
            request_call: Header of the client request invocation line.
            kwargs_lines: Indented keyword argument lines for the request.
            response_path: Optional dot-separated path to extract body from JSON response.
            response_join: Optional separator string when joining list of response fragments.
            i2: Indentation prefix for method body statements.
            i3: Indentation prefix for nested block statements.

        Returns:
            List of generated Python code lines executing the HTTP request and
            instantiating the parser class with the response body.
        """
        lines = [request_call, *kwargs_lines, f"{i2})"]
        lines.append(f"{i2}_resp.raise_for_status()")
        if response_path:
            accessor = "".join(f"[{p!r}]" for p in response_path.split("."))
            lines.append(f"{i2}_data = _resp.json()")
            if response_join:
                lines.append(
                    f"{i2}_body = {response_join!r}.join(_data{accessor})"
                )
            else:
                lines.append(f"{i2}_body = _data{accessor}")
        else:
            lines.append(f"{i2}_body = _resp.text")
        lines.append(f"{i2}return cls(_body)")
        return lines
