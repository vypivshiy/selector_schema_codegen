from __future__ import annotations
import re

from ssc_codegen.kdl.ast import (
    PredRe,
    PredReAll,
    PredReAny,
    PredTextRe,
    PredAttrRe,
    Re,
    ReAll,
    ReSub,
)


def to_snake_case(s: str) -> str:
    """
    'myFieldName'  -> 'my_field_name'
    'MyFieldName'  -> 'my_field_name'
    'my-field-name' -> 'my_field_name'
    'my field name' -> 'my_field_name'
    """
    s = re.sub(r"[-\s]+", "_", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def to_upper_snake_case(s: str) -> str:
    """
    'myFieldName'  -> 'MY_FIELD_NAME'
    """
    return to_snake_case(s).upper()


def to_pascal_case(s: str) -> str:
    """
    'my_field_name' -> 'MyFieldName'
    'my-field-name' -> 'MyFieldName'
    'myFieldName'   -> 'MyFieldName'
    'JsnArr'        -> 'JsnArr'      # уже PascalCase — не ломаем
    'jsnArr'        -> 'JsnArr'
    """
    # split by separators only, не трогаем регистр внутри слова
    parts = re.split(r"[-_\s]+", s)
    return "".join(p[0].upper() + p[1:] for p in parts if p)


def to_camel_case(s: str) -> str:
    """
    'MyFieldName'   -> 'myFieldName'
    'my_field_name' -> 'myFieldName'
    'JsnArr'        -> 'jsnArr'
    """
    parts = re.split(r"[-_\s]+", s)
    if not parts:
        return s
    return (
        parts[0][0].lower()
        + parts[0][1:]
        + "".join(p[0].upper() + p[1:] for p in parts[1:] if p)
    )


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


def py_pattern_re_flags(node: Re | ReAll | ReSub | PredRe | PredReAll | PredReAny | PredTextRe | PredAttrRe) -> str:
    """Build a trailing re-flags argument string, e.g. ', re.IGNORECASE' or
    ', re.IGNORECASE | re.DOTALL', or '' when no flags are set."""
    parts: list[str] = []
    if node.ignore_case:
        parts.append("re.IGNORECASE")
    if node.dotall:
        parts.append("re.DOTALL")
    return (", " + " | ".join(parts)) if parts else ""
