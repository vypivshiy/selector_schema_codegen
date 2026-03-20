"""
Utilities for processing regex patterns from KDL defines.

These functions handle extraction of flags (IGNORECASE, DOTALL, VERBOSE)
from compiled re.Pattern objects and inline flag syntax like (?i)(?s),
and convert VERBOSE patterns to compact form by removing whitespace/comments.
"""

from __future__ import annotations

import re as _re


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

    if pattern.flags & _re.X:
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


def extract_regex_flags(value: str | _re.Pattern) -> tuple[str, bool, bool]:
    """Resolve a raw define value (str or compiled Pattern) to
    ``(pattern, ignore_case, dotall)``.

    Handles both sources of flags:
    - Compiled ``re.Pattern``: ``re.IGNORECASE``, ``re.DOTALL``, ``re.VERBOSE``
    - Plain string with leading inline flags: ``(?i)``, ``(?s)``, ``(?is)`` …

    The returned pattern is stripped of ``i``/``s`` inline flags so that
    codegen can emit explicit ``re.IGNORECASE`` / ``re.DOTALL`` arguments.

    VERBOSE patterns are converted to compact form (whitespace/comments removed).

    Args:
        value: Either a string pattern or a compiled re.Pattern object.

    Returns:
        A tuple of (pattern_string, ignore_case, dotall).

    Example:
        >>> import re
        >>> pattern = re.compile(r"(?xs) foo \\s+ bar  # comment", re.VERBOSE | re.DOTALL)
        >>> extract_regex_flags(pattern)
        ('foo\\s+bar', False, True)
    """
    if isinstance(value, str):
        return extract_inline_flags(value)
    pattern = unverbosify_regex(value)
    ignore_case = bool(value.flags & _re.IGNORECASE)
    dotall = bool(value.flags & _re.DOTALL)
    # compiled patterns may also embed inline flags in their .pattern string
    # (e.g. re.compile("(?i)foo") sets IGNORECASE but also keeps "(?i)" in
    # .pattern on some Python versions) — strip to avoid double-reporting
    pattern, ic2, ds2 = extract_inline_flags(pattern)
    return pattern, ignore_case or ic2, dotall or ds2


def normalize_regex_pattern(value: str | _re.Pattern) -> str:
    """Convert a regex pattern to a single-line inline form with embedded flags.

    This function:
    1. Strips VERBOSE formatting (whitespace and comments) if present
    2. Extracts all flags (IGNORECASE, DOTALL, VERBOSE)
    3. Returns pattern with inline flags like (?is)pattern

    This is the primary function to use when preparing regex patterns for codegen.

    Args:
        value: Either a string pattern or a compiled re.Pattern object.

    Returns:
        A single-line pattern string with inline flags, ready for codegen.

    Example:
        >>> import re
        >>> pattern = re.compile(r'''(?xs)
        ...     foo \\s+ bar  # match foo and bar
        ... ''', re.VERBOSE | re.DOTALL)
        >>> normalize_regex_pattern(pattern)
        '(?s)foo\\s+bar'
    """
    # If it's a compiled Pattern, unverbosify_regex handles VERBOSE
    if isinstance(value, _re.Pattern):
        pattern, ignore_case, dotall = extract_regex_flags(value)
        return add_inline_regex_flags(pattern, ignore_case, dotall)

    # If it's a string, check for inline (?x) flag and handle it
    pattern = value
    ignore_case = False
    dotall = False

    # Check for inline flags
    m = _INLINE_FLAGS_RE.match(pattern)
    if m:
        flags_str = m.group(1)
        ignore_case = "i" in flags_str
        dotall = "s" in flags_str
        has_verbose = "x" in flags_str

        # Remove all i, s, x flags from the inline group
        remaining = flags_str.replace("i", "").replace("s", "").replace("x", "")
        if remaining:
            pattern = f"(?{remaining})" + pattern[m.end() :]
        else:
            pattern = pattern[m.end() :]

        # If VERBOSE flag was present, manually strip whitespace and comments
        if has_verbose:
            # Use the unverbosify logic on a fake compiled pattern
            fake_pattern = _re.compile(pattern, _re.VERBOSE)
            pattern = unverbosify_regex(fake_pattern)

    return add_inline_regex_flags(pattern, ignore_case, dotall)
