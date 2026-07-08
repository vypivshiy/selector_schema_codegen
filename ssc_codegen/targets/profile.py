"""Target profiles: capability descriptors + converter factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TargetProfile:
    """Resolved target: capabilities, constraints, converter factory."""

    language: str
    file_extension: str
    create_converter: Callable[[], Any]
    http_clients: tuple[str, ...] = ()
    supports_separate_runtime: bool = False
    runtime_include_fallback: bool = False
