"""Abstract base class and contract for Python HTTP client transport strategies."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod

_MERGE_KWARGS_RUNTIME = inspect.cleandoc(
    """
    def ssc_merge_kwargs(
        base: Dict[str, Any], extra: Dict[str, Any]
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in base.items():
            if k in ('headers', 'params', 'cookies') and isinstance(v, dict):
                d = {dk: dv for dk, dv in v.items() if dv is not None}
                if d:
                    out[k] = d
            elif v is not None:
                out[k] = v
        for k, v in extra.items():
            if isinstance(out.get(k), dict) and isinstance(v, dict):
                out[k] = {**out[k], **v}
            else:
                out[k] = v
        return out
    """
)

_REST_SHARED_RUNTIME = inspect.cleandoc(
    """
    _T = TypeVar('_T')
    _E = TypeVar('_E')

    @dataclass(frozen=True)
    class Ok(Generic[_T]):
        status: int = 0
        headers: Dict[str, str] = field(default_factory=dict)
        value: _T = None  # type: ignore[assignment]
        is_ok: Literal[True] = True

    @dataclass(frozen=True)
    class Err(Generic[_E]):
        status: int = 0
        headers: Dict[str, str] = field(default_factory=dict)
        value: _E = None  # type: ignore[assignment]
        is_ok: Literal[False] = False

    @dataclass(frozen=True)
    class UnknownErr(Err[Any]):
        pass

    @dataclass(frozen=True)
    class TransportErr(Err[None]):
        status: Literal[0] = 0
        cause: str = ''
        value: None = None
        headers: Dict[str, str] = field(default_factory=dict)

    @dataclass(frozen=True)
    class ErrMatcher:
        status: int
        check: Optional[Callable[[dict], bool]] = None
        factory: Optional[Callable[..., Err]] = None

        def match(
            self,
            status: int,
            headers: Dict[str, str],
            body: Any,
        ) -> Optional[Err]:
            if status != self.status:
                return None
            if body is None or not isinstance(body, (dict, list)):
                return None
            if self.check is not None:
                if not isinstance(body, dict) or not self.check(body):
                    return None
            try:
                return self.factory(headers=headers, value=body)
            except Exception:
                return None


    def ssc_dispatch_err(
        matchers: List[ErrMatcher],
        status: int,
        headers: Dict[str, str],
        body: Any,
    ) -> Optional[Err]:
        for matcher in matchers:
            err = matcher.match(status, headers, body)
            if err is not None:
                return err
        if 200 <= status < 300:
            return None
        return UnknownErr(status=status, headers=headers, value=body)
    """
)


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

    def merge_kwargs_lines(self) -> list[str]:
        """Generate `ssc_merge_kwargs` runtime helper lines.

        Returns:
            list[str]: Python source lines defining `ssc_merge_kwargs`.
        """
        return [*_MERGE_KWARGS_RUNTIME.splitlines(), ""]

    @abstractmethod
    def rest_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate REST runtime source lines (`Ok`, `Err`, `ssc_rest_call`, etc.).

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).
                Controls which call helpers (`ssc_rest_call` and/or `ssc_rest_call_async`)
                are included in the returned lines. Defaults to `"both"`.

        Returns:
            list[str]: List of Python code lines implementing the REST runtime helpers with
            library-specific transport exception catching.
        """
        ...

    def fetch_runtime_lines(self, http_io: str = "both") -> list[str]:
        """Generate `MethodFetch` runtime helper source lines (`ssc_fetch`, `ssc_fetch_async`).

        Args:
            http_io (str): HTTP method generation mode (`"both"`, `"sync"`, `"async"`).

        Returns:
            list[str]: Python source lines implementing the fetch runtime helpers.
        """
        return []
