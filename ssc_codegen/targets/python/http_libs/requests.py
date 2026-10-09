"""requests HTTP client transport strategy for Python code generation."""

from __future__ import annotations

from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy


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

    def rest_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate REST runtime source lines with requests transport exception handling.

        Args:
            http_io: HTTP method generation mode (`"both"`, `"sync"`, `"async"`).
                Controls which call helpers (`ssc_rest_call` and/or `ssc_rest_call_async`)
                are included in the returned lines. Defaults to `"both"`.

        Returns:
            List of Python code lines implementing REST runtime helpers with
            requests-specific exception catching.
        """
        exc = self.transport_exception
        lines = [
            "_T = TypeVar('_T')",
            "_E = TypeVar('_E')",
            "",
            "@dataclass(frozen=True)",
            "class Ok(Generic[_T]):",
            "    status: int = 0",
            "    headers: Dict[str, str] = field(default_factory=dict)",
            "    value: _T = None  # type: ignore[assignment]",
            "    is_ok: Literal[True] = True",
            "",
            "@dataclass(frozen=True)",
            "class Err(Generic[_E]):",
            "    status: int = 0",
            "    headers: Dict[str, str] = field(default_factory=dict)",
            "    value: _E = None  # type: ignore[assignment]",
            "    is_ok: Literal[False] = False",
            "",
            "@dataclass(frozen=True)",
            "class UnknownErr(Err[Any]):",
            "    pass",
            "",
            "@dataclass(frozen=True)",
            "class TransportErr(Err[None]):",
            "    status: Literal[0] = 0",
            "    cause: str = ''",
            "    value: None = None",
            "    headers: Dict[str, str] = field(default_factory=dict)",
            "",
            "@dataclass(frozen=True)",
            "class ErrMatcher:",
            "    status: int",
            "    check: Optional[Callable[[dict], bool]] = None",
            "    factory: Optional[Callable[..., Err]] = None",
            "",
            "    def match(",
            "        self,",
            "        status: int,",
            "        headers: Dict[str, str],",
            "        body: Any,",
            "    ) -> Optional[Err]:",
            "        if status != self.status:",
            "            return None",
            "        if self.check is not None:",
            "            if not isinstance(body, dict) or not self.check(body):",
            "                return None",
            "        if self.factory is not None:",
            "            return self.factory(headers=headers, value=body)",
            "        return None",
            "",
            "",
            "def ssc_dispatch_err(",
            "    matchers: List[ErrMatcher],",
            "    status: int,",
            "    headers: Dict[str, str],",
            "    body: Any,",
            ") -> Optional[Err]:",
            "    for matcher in matchers:",
            "        err = matcher.match(status, headers, body)",
            "        if err is not None:",
            "            return err",
            "    if 200 <= status < 300:",
            "        return None",
            "    return UnknownErr(status=status, headers=headers, value=body)",
            "",
            "",
        ]
        # ssc_rest_call is needed for sync/both modes and as execution delegate for async mode
        if http_io in ("both", "sync", "async"):
            lines.extend(
                [
                    "def ssc_rest_call(",
                    "    client: requests.Session,",
                    "    matchers: List[ErrMatcher],",
                    "    method: str,",
                    "    url: str,",
                    "    value_fn: Optional[Callable[[Any], _T]] = None,",
                    "    **kw: Any,",
                    ") -> Union[Ok[_T], Err]:",
                    "    try:",
                    "        resp = client.request(method, url, **kw)",
                    "        status = resp.status_code",
                    "        headers = {k.lower(): v for k, v in resp.headers.items()}",
                    "        try:",
                    "            body = resp.json()",
                    "        except Exception:",
                    "            body = None",
                    f"    except {exc} as exc:",
                    "        return TransportErr(cause=repr(exc))",
                    "    err = ssc_dispatch_err(matchers, status, headers, body)",
                    "    if err is not None:",
                    "        return err",
                    "    value = body if value_fn is None else value_fn(body)",
                    "    return Ok(status=status, headers=headers, value=value)",
                    "",
                    "",
                ]
            )
        if http_io in ("both", "async"):
            lines.extend(
                [
                    "async def ssc_rest_call_async(",
                    "    client: requests.Session,",
                    "    matchers: List[ErrMatcher],",
                    "    method: str,",
                    "    url: str,",
                    "    value_fn: Optional[Callable[[Any], _T]] = None,",
                    "    **kw: Any,",
                    ") -> Union[Ok[_T], Err]:",
                    "    import asyncio",
                    "    loop = asyncio.get_event_loop()",
                    "    return await loop.run_in_executor(",
                    "        None,",
                    "        lambda: ssc_rest_call(",
                    "            client, matchers, method, url, value_fn, **kw",
                    "        ),",
                    "    )",
                    "",
                ]
            )
        return lines
