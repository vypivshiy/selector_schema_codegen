from __future__ import annotations

from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy


class RequestsStrategy(HttpLibStrategy):
    """requests HTTP client strategy (sync-only, async via executor).

    ``requests`` has no async API — ``async_fetch`` wraps the sync call
    through ``asyncio.get_event_loop().run_in_executor()``.
    """

    import_line = "import requests"
    sync_client_type = "requests.Session"
    async_client_type = "requests.Session"
    transport_exception = "requests.RequestException"

    def rest_runtime_lines(self) -> list[str]:
        exc = self.transport_exception
        return [
            "_T = TypeVar('_T')",
            "_E = TypeVar('_E')",
            "",
            "@dataclass(frozen=True)",
            "class Ok(Generic[_T]):",
            "    status: int = 0",
            "    headers: Mapping[str, str] = field(default_factory=dict)",
            "    value: _T = None  # type: ignore[assignment]",
            "    is_ok: Literal[True] = True",
            "",
            "@dataclass(frozen=True)",
            "class Err(Generic[_E]):",
            "    status: int = 0",
            "    headers: Mapping[str, str] = field(default_factory=dict)",
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
            "    headers: Mapping[str, str] = field(default_factory=dict)",
            "",
            "@dataclass(frozen=True)",
            "class ErrMatcher:",
            "    status: int",
            "    check: Callable[[dict], bool] | None = None",
            "    factory: Callable[..., Err] = None  # type: ignore[assignment]",
            "",
            "    def match(self, _s: int, _h, _b) -> Err | None:",
            "        if _s != self.status:",
            "            return None",
            "        if self.check is not None:",
            "            if not isinstance(_b, dict) or not self.check(_b):",
            "                return None",
            "        return self.factory(headers=_h, value=_b)",
            "",
            "",
            "def ssc_dispatch_err(_matchers, _status: int, _headers, _body):",
            "    for _m in _matchers:",
            "        _err = _m.match(_status, _headers, _body)",
            "        if _err is not None:",
            "            return _err",
            "    if 200 <= _status < 300:",
            "        return None",
            "    return UnknownErr(status=_status, headers=_headers, value=_body)",
            "",
            "",
            "def ssc_rest_call(client, _matchers, method, url, _value_fn=None, **kw):",
            "    try:",
            "        _resp = client.request(method, url, **kw)",
            "        _status = _resp.status_code",
            "        _headers = {k.lower(): v for k, v in _resp.headers.items()}",
            "        try:",
            "            _body = _resp.json()",
            "        except Exception:",
            "            _body = None",
            f"    except {exc} as _exc:",
            "        return TransportErr(cause=repr(_exc))",
            "    _err = ssc_dispatch_err(_matchers, _status, _headers, _body)",
            "    if _err is not None:",
            "        return _err",
            "    _value = _body if _value_fn is None else _value_fn(_body)",
            "    return Ok(status=_status, headers=_headers, value=_value)",
            "",
            "",
            "async def ssc_rest_call_async(client, _matchers, method, url, _value_fn=None, **kw):",
            "    import asyncio",
            "    loop = asyncio.get_event_loop()",
            "    return await loop.run_in_executor(",
            "        None, lambda: ssc_rest_call(client, _matchers, method, url, _value_fn, **kw)",
            "    )",
            "",
        ]
