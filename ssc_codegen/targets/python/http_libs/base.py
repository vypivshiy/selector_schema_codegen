from __future__ import annotations

from abc import ABC, abstractmethod


class HttpLibStrategy(ABC):
    """HTTP client library strategy for REST codegen.

    Owns everything HTTP-library-specific: import line, client type
    annotations, transport exception class, and the REST runtime source
    (ssc_rest_call / ssc_rest_call_async with library-specific exception
    handling).
    """

    # === DATA (override in concrete subclasses) ===
    import_line: str = ""
    sync_client_type: str = ""
    async_client_type: str = ""
    transport_exception: str = ""

    # === BEHAVIOR ===

    @abstractmethod
    def rest_runtime_lines(self) -> list[str]:
        """REST runtime source lines (Ok/Err/ssc_rest_call/etc.).

        The only library-specific part is the ``except`` clause in
        ``ssc_rest_call`` / ``ssc_rest_call_async`` which catches
        ``self.transport_exception``.
        """
        ...
