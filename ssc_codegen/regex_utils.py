"""
Utilities for processing regex patterns from KDL defines.

These functions handle extraction of flags (IGNORECASE, DOTALL, VERBOSE)
from compiled re.Pattern objects and inline flag syntax like (?i)(?s),
and convert VERBOSE patterns to compact form by removing whitespace/comments.
"""

from __future__ import annotations

import re as _re
from typing import Any

# https://stackoverflow.com/a/14919203
_CM1_RX = r"(?m)(?<!\\)((\\{2})*)#.*$"
_CM2_RX = r"(\\)?((\\{2})*)(#)"
_WS_RX = r"(\\)?((\\{2})*)(\s)\s*"


def unverbosify_regex(pattern: str | _re.Pattern) -> str:
    """Strip re.VERBOSE whitespace/comments from a compiled pattern.

    Args:
        pattern: Either a string pattern (returned as-is) or a compiled
                 re.Pattern object with optional VERBOSE flag.

    Returns:
        The pattern string with VERBOSE formatting removed (if present).
    """
    if isinstance(pattern, str):
        return pattern

    def _strip(m):  # type: ignore[return-value]
        if m.group(1) is None:
            return m.group(2)
        elif m.group(1) == "\\":
            return m.group(2) + m.group(4)
        raise ValueError("unexpected match in unverbosify")

    if pattern.flags & _re.VERBOSE:
        return _re.sub(
            _WS_RX,
            _strip,
            _re.sub(_CM2_RX, _strip, _re.sub(_CM1_RX, "\\1", pattern.pattern)),
        )
    return pattern.pattern


_INLINE_FLAGS_RE = _re.compile(r"^\(\?([a-z]+)\)")


def extract_inline_flags(pattern: str) -> tuple[str, bool, bool]:
    """Strip leading ``(?flags)`` inline group from *pattern* and return
    ``(stripped_pattern, ignore_case, dotall)``.

    Only ``i`` (IGNORECASE) and ``s`` (DOTALL) are extracted; other flags
    are left in place so the regex stays semantically identical.

    NOTE: This also detects and strips VERBOSE flag 'x', returning it as part
    of the metadata so caller can handle verbose mode appropriately.

    Args:
        pattern: A regex pattern string, possibly starting with (?imsux...) flags.

    Returns:
        A tuple of (pattern_without_i_s_x_flags, ignore_case, dotall).
        If 'x' flag was present, it is removed from the pattern.
    """
    m = _INLINE_FLAGS_RE.match(pattern)
    if not m:
        return pattern, False, False
    flags_str = m.group(1)
    ignore_case = "i" in flags_str
    dotall = "s" in flags_str
    # Remove i, s, and x (verbose) flags
    remaining = flags_str.replace("i", "").replace("s", "").replace("x", "")
    # rebuild the inline group without i/s/x; drop it entirely if empty
    if remaining:
        prefix = f"(?{remaining})"
    else:
        prefix = ""
    return prefix + pattern[m.end() :], ignore_case, dotall


def add_inline_regex_flags(
    pattern: str, ignore_case: bool = False, dotall: bool = False
) -> str:
    """Add inline flags (?i) and/or (?s) to the beginning of a pattern.

    Args:
        pattern: The regex pattern string.
        ignore_case: Whether to add (?i) flag.
        dotall: Whether to add (?s) flag.

    Returns:
        Pattern with inline flags prepended, e.g., "(?is)pattern".

    Example:
        >>> add_inline_regex_flags("foo.*bar", ignore_case=True, dotall=True)
        '(?is)foo.*bar'
    """
    flags = ""
    if ignore_case:
        flags += "i"
    if dotall:
        flags += "s"
    if flags:
        return f"(?{flags}){pattern}"
    return pattern


def normalize_regex_pattern(value: Any) -> str:
    """Convert a regex pattern to a single-line inline form with embedded flags.

    This function:
    1. Strips VERBOSE formatting (whitespace and comments) if present
    2. Extracts all flags (IGNORECASE, DOTALL, VERBOSE)
    3. Returns pattern with inline flags like (?is)pattern

    This is the primary function to use when preparing regex patterns for codegen.

    Args:
        value: A regex pattern value (converted to string).

    Returns:
        A single-line pattern string with inline flags, ready for codegen.
    """
    raw = str(value).lstrip()
    m = _INLINE_FLAGS_RE.match(raw)
    has_verbose = bool(m and "x" in m.group(1))
    pattern, ignore_case, dotall = extract_inline_flags(raw)
    if has_verbose:
        fake_pattern = _re.compile(pattern, _re.VERBOSE)
        pattern = unverbosify_regex(fake_pattern)

    return add_inline_regex_flags(pattern, ignore_case, dotall)
