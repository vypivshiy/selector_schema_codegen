"""Compatibility checks and small translations for Rust ``regex``."""

from __future__ import annotations

import re

from ssc_codegen.exceptions import BuildTimeError


_UNSUPPORTED = re.compile(r"\(\?[=!<]|\\[1-9]")


def validate_rust_pattern(pattern: str) -> str:
    """Validate and return a Python-compatible regex for Rust ``regex``.

    Args:
        pattern: DSL regular expression pattern.

    Returns:
        The unchanged pattern.

    Raises:
        BuildTimeError: If the pattern uses lookaround or a backreference.
    """
    if _UNSUPPORTED.search(pattern):
        raise BuildTimeError(
            "Rust regex does not support lookaround or backreferences: "
            f"{pattern!r}"
        )
    return pattern


def rust_replacement(replacement: str) -> str:
    """Translate DSL/Python numeric replacement groups to Rust syntax."""
    parts: list[str] = []
    cursor = 0
    for match in re.finditer(r"\\([1-9][0-9]*)", replacement):
        parts.append(replacement[cursor : match.start()].replace("$", "$$"))
        parts.append(f"${match.group(1)}")
        cursor = match.end()
    parts.append(replacement[cursor:].replace("$", "$$"))
    return "".join(parts)
