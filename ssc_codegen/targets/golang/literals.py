"""Shared Go literal rendering helpers.

Single source of truth for Go string/value/collection literals — used by
both ``visitor.py`` and ``rest.py``.
"""

from __future__ import annotations


def go_str(s: str) -> str:
    """Go double-quoted string literal with proper escaping."""
    escaped = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def go_str_array(values) -> str:
    """Render ``[]string{...}`` from an iterable of strings."""
    items = ", ".join(go_str(v) for v in values)
    return f"[]string{{{items}}}"


def go_str_map(d: dict) -> str:
    """Render ``map[string]string{...}`` from a Python dict."""
    if not d:
        return "map[string]string{}"
    items = ", ".join(f"{go_str(k)}: {go_str(v)}" for k, v in d.items())
    return f"map[string]string{{{items}}}"
