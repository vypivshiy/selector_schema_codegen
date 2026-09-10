"""Compatibility checks and small translations for Rust ``regex``."""

from __future__ import annotations

import re

from ssc_codegen.exceptions import BuildTimeError


_UNSUPPORTED = re.compile(
    r"\(\?[=!<]|\\[1-9]|\(\?P=[a-zA-Z_]\w*\)|\\k<[a-zA-Z_]\w*>|\\k'[a-zA-Z_]\w*'"
)


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
    """Translate DSL/Python numeric replacement groups to Rust syntax.

    Translates numeric backreferences in either DSL/Python format (``\\1``) or
    POSIX/Rust format (``$1``) into Rust regex capture group syntax (``$1``),
    while escaping literal dollar signs as ``$$``.

    Args:
        replacement: Raw replacement string from the schema.

    Returns:
        Rust-compatible replacement string with group references translated.
    """
    parts: list[str] = []
    cursor = 0
    pattern = re.compile(r"\\([1-9][0-9]*)|(?:\$([1-9][0-9]*))|(\$\$)|(\$)")
    for match in pattern.finditer(replacement):
        bs_group, dollar_group, double_dollar, single_dollar = match.groups()
        parts.append(replacement[cursor : match.start()])
        if bs_group:
            parts.append(f"${bs_group}")
        elif dollar_group:
            parts.append(f"${dollar_group}")
        elif double_dollar:
            parts.append("$$")
        elif single_dollar:
            parts.append("$$")
        cursor = match.end()
    parts.append(replacement[cursor:])
    return "".join(parts)
