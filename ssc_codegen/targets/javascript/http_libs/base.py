from __future__ import annotations

from abc import ABC, abstractmethod


class JsHttpLibStrategy(ABC):
    """HTTP client strategy for JS codegen.

    JS emits both fetch and axios runtime helpers regardless of selection
    (small functions, tests verify both are present).  The strategy only
    determines which helper name generated methods delegate to.
    """

    fn_name: str = ""

    @abstractmethod
    def rest_call_lines(self) -> list[str]:
        """Library-specific ``sscRestCall`` / ``sscRestCallAxios`` source."""
        ...
