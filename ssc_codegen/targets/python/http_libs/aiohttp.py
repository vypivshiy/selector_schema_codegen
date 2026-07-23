from __future__ import annotations

from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy


class AioHttpStrategy(HttpLibStrategy):
    """aiohttp HTTP client strategy (async-only, sync wrapped via asyncio.run)."""

    import_line = "import aiohttp"
    sync_client_type = "aiohttp.ClientSession"
    async_client_type = "aiohttp.ClientSession"
    transport_exception = "aiohttp.ClientError"

    # aiohttp is async-only: no synchronous ``fetch`` is generated.
    supports_sync_fetch = False

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
        """aiohttp semantics: ``async with client.request(...) as _resp:``.

        ``ClientSession.request`` is an async context manager;
        ``text()`` / ``json()`` are coroutines (need ``await``);
        ``raise_for_status()`` is a regular sync method in aiohttp.
        ``is_async`` is ignored — aiohttp only ever emits the async path
        (caller guarantees ``supports_sync_fetch=False``).
        """
        lines = [
            f"{i2}async with client.request(",
            *kwargs_lines,
            f"{i2}) as _resp:",
        ]
        lines.append(f"{i3}_resp.raise_for_status()")
        if response_path:
            accessor = "".join(f"[{p!r}]" for p in response_path.split("."))
            lines.append(f"{i3}_data = await _resp.json()")
            if response_join:
                lines.append(
                    f"{i3}_body = {response_join!r}.join(_data{accessor})"
                )
            else:
                lines.append(f"{i3}_body = _data{accessor}")
        else:
            lines.append(f"{i3}_body = await _resp.text()")
        lines.append(f"{i3}return cls(_body)")
        return lines

    def rest_runtime_lines(self) -> list[str]:
        exc = self.transport_exception
        return [
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
            "        return self.factory(headers=headers, value=body)",
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
            "def ssc_rest_call(",
            "    client: aiohttp.ClientSession,",
            "    matchers: List[ErrMatcher],",
            "    method: str,",
            "    url: str,",
            "    value_fn: Optional[Callable[[Any], _T]] = None,",
            "    **kw: Any,",
            ") -> Union[Ok[_T], Err]:",
            "    async def go() -> Union[Ok[_T], Err]:",
            "        try:",
            "            async with client.request(method, url, **kw) as resp:",
            "                status = resp.status",
            "                headers = {k.lower(): v for k, v in resp.headers.items()}",
            "                try:",
            "                    body = await resp.json()",
            "                except Exception:",
            "                    body = None",
            f"        except {exc} as exc:",
            "            return TransportErr(cause=repr(exc))",
            "        err = ssc_dispatch_err(matchers, status, headers, body)",
            "        if err is not None:",
            "            return err",
            "        value = body if value_fn is None else value_fn(body)",
            "        return Ok(status=status, headers=headers, value=value)",
            "    try:",
            "        asyncio.get_running_loop()",
            "    except RuntimeError:",
            "        return asyncio.run(go())",
            "    import concurrent.futures",
            "    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:",
            "        return pool.submit(asyncio.run, go()).result()",
            "",
            "",
            "async def ssc_rest_call_async(",
            "    client: aiohttp.ClientSession,",
            "    matchers: List[ErrMatcher],",
            "    method: str,",
            "    url: str,",
            "    value_fn: Optional[Callable[[Any], _T]] = None,",
            "    **kw: Any,",
            ") -> Union[Ok[_T], Err]:",
            "    try:",
            "        async with client.request(method, url, **kw) as resp:",
            "            status = resp.status",
            "            headers = {k.lower(): v for k, v in resp.headers.items()}",
            "            try:",
            "                body = await resp.json()",
            "            except Exception:",
            "                body = None",
            f"    except {exc} as exc:",
            "        return TransportErr(cause=repr(exc))",
            "    err = ssc_dispatch_err(matchers, status, headers, body)",
            "    if err is not None:",
            "        return err",
            "    value = body if value_fn is None else value_fn(body)",
            "    return Ok(status=status, headers=headers, value=value)",
            "",
        ]
