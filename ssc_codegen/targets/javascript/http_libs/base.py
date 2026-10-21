"""Abstract base class and contract for JavaScript HTTP client strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod


class JsHttpLibStrategy(ABC):
    """HTTP client strategy for JavaScript REST and fetch code generation.

    Attributes:
        fn_name: Name of the JavaScript transport dispatcher helper function
            (e.g. ``"sscRestCall"`` or ``"sscRestCallAxios"``).
        fetch_fn_name: Name of the JavaScript HTML/text fetch helper function
            (e.g. ``"sscFetch"`` or ``"sscFetchAxios"``).
    """

    fn_name: str = ""
    fetch_fn_name: str = ""

    @abstractmethod
    def rest_call_lines(self) -> list[str]:
        """Generate library-specific `sscRestCall` or `sscRestCallAxios` helper source lines.

        Returns:
            List of JavaScript source lines implementing the transport call.
        """
        ...

    @abstractmethod
    def fetch_call_lines(self) -> list[str]:
        """Generate library-specific `sscFetch` or `sscFetchAxios` helper source lines.

        Returns:
            List of JavaScript source lines implementing the fetch call.
        """
        ...
