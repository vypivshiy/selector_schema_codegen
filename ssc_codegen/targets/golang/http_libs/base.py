"""HTTP client strategy abstract base class for Go code generation."""

from __future__ import annotations

from abc import ABC, abstractmethod


class GoHttpLibStrategy(ABC):
    """HTTP client library strategy for Go REST code generation.

    Attributes:
        client_type: Go type signature for the HTTP client (e.g. ``"*http.Client"``).
        import_path: Import path of the network package (e.g. ``"net/http"``).
    """

    client_type: str = ""
    import_path: str = ""

    @property
    def rest_imports(self) -> list[str]:
        """Go import paths needed by `rest_runtime_lines`."""
        return []

    @abstractmethod
    def rest_runtime_lines(self) -> list[str]:
        """Generate library-specific REST runtime source lines (`sscRestCall`).

        Returns:
            List of Go source code lines implementing HTTP transport execution.
        """
        ...
