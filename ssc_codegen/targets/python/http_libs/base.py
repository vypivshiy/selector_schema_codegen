from __future__ import annotations

from abc import ABC, abstractmethod


class HttpLibStrategy(ABC):
    """HTTP client library strategy for REST codegen.

    Owns everything HTTP-library-specific: import line, client type
    annotations, transport exception class, the REST runtime source
    (ssc_rest_call / ssc_rest_call_async with library-specific exception
    handling), and the ``MethodFetch`` body (request + response handling).
    """

    # === DATA (override in concrete subclasses) ===
    import_line: str = ""
    sync_client_type: str = ""
    async_client_type: str = ""
    transport_exception: str = ""

    # === FETCH BEHAVIOR (override in concrete subclasses) ===

    #: Emit a synchronous ``fetch`` classmethod. aiohttp is async-only, so
    #: its strategy sets this to ``False`` and only ``async_fetch`` is
    #: generated.
    supports_sync_fetch: bool = True

    #: ``async_fetch`` delegates to the already-generated sync ``fetch``
    #: via ``loop.run_in_executor``. True for sync-only clients (requests).
    #: When True, :meth:`fetch_body_lines` is NOT called with
    #: ``is_async=True``; ``emit_method_fetch`` emits the executor wrapper
    #: directly.
    async_fetch_delegates_to_sync: bool = False

    # === BEHAVIOR ===

    @abstractmethod
    def rest_runtime_lines(self) -> list[str]:
        """REST runtime source lines (Ok/Err/ssc_rest_call/etc.).

        The only library-specific part is the ``except`` clause in
        ``ssc_rest_call`` / ``ssc_rest_call_async`` which catches
        ``self.transport_exception``.
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
        """Body of a ``MethodFetch`` classmethod (request + response).

        Default implementation follows httpx/requests semantics:
        ``resp = client.request(...); resp.raise_for_status(); body =
        resp.text`` (or ``resp.json()`` when ``response_path`` is set).

        ``is_async=True`` only changes the caller-supplied ``request_call``
        (already prefixed with ``await``); the response handling is identical
        for httpx. aiohttp overrides this method for ``async with`` semantics.
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
