"""HTTP client strategy ABC for Go codegen."""

from __future__ import annotations

from abc import ABC, abstractmethod


class GoHttpLibStrategy(ABC):
    """HTTP client library strategy for Go REST codegen.

    Go has one HTTP client in stdlib (net/http). The strategy pattern
    is kept for structural consistency with Python/JS backends and
    future extensibility (resty, etc.).
    """

    client_type: str = ""
    import_path: str = ""

    @property
    def rest_imports(self) -> list[str]:
        """Go imports needed by rest_runtime_lines()."""
        return []

    @abstractmethod
    def rest_runtime_lines(self) -> list[str]:
        """Library-specific REST runtime source (sscRestCall)."""
        ...
