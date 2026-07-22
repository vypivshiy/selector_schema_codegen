"""Python regex → Go RE2 pattern translation helpers.

ssc-gen DSL regex grammar intentionally targets a limited subset of PCRE
compatible with Go RE2. The grammar excludes: backreferences, lookahead,
lookbehind, atomic groups, possessive quantifiers, ``\\K``, conditional
patterns, and recursion. Patterns stay within this subset → portable
across Python/JS/Go backends without translation loss.

See docs/llm.txt for DSL regex grammar constraints.
"""

from __future__ import annotations


def py_re_to_go_raw(pattern: str) -> str:
    """Render a Python regex pattern as a Go raw-string literal.

    RE2 supports inline flags (?i), (?m), (?s) natively — patterns pass
    through unchanged.  Uses Go backtick raw strings to avoid escaping.

    Falls back to double-quoted string if the pattern contains a backtick.
    """
    if "`" not in pattern:
        return f"`{pattern}`"
    escaped = pattern.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
