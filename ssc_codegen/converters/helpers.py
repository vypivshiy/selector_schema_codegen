from __future__ import annotations

from ssc_codegen.naming import (
    to_camel_case,
    to_pascal_case,
    to_snake_case,
    to_upper_snake_case,
)

__all__ = [
    "to_snake_case",
    "to_upper_snake_case",
    "to_pascal_case",
    "to_camel_case",
    "jsonify_path_to_segments",
]


def jsonify_path_to_segments(query: str) -> list[str]:
    """wrap string keys to quotas, digits ignore

    covered cases

    0 -> ["0"]
    foo -> ["foo"]
    foo.0 -> ["foo", 0]
    foo.1.bar.0.0.text -> ["foo", "1", "bar", "0", "0", "text"]

    """
    if not query:
        return []
    parts: list[str] = []
    for part in query.split("."):
        if part.isdigit():
            parts.append(part)
        else:
            parts.append(repr(part))

    return parts


# py_pattern_re_flags removed - flags are now always embedded inline in pattern as (?i) and (?s)
