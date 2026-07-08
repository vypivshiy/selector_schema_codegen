"""User-supplied target configuration (CLI input)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetSpec:
    """Raw user input before validation."""

    lang: str  # "python" | "js"
    lib: str | None = None  # DOM library (Python only)
    http_client: str | None = None
    separate_runtime: bool = False
