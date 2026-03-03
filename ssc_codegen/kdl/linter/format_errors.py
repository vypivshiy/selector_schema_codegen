"""
Rust-style error formatter for KDL DSL lint errors.

Output example:

  error: 'css' requires a CSS query argument
    --> struct Demo > title  line 3:9
     |
   3 |         css
     |         ^^^ missing query argument
     |
     = hint: example: css ".my-class"

"""
from __future__ import annotations

from ssc_codegen.kdl.linter.base import LintError


def format_error(error: LintError, src: str) -> str:
    """
    Format a single LintError in rust-style with source context.

    Args:
        error: the lint error to format
        src:   original DSL source text (used to extract the offending line)
    """
    lines = src.splitlines()
    line_idx = error.line - 1  # 0-based

    # header: error/warning + message
    parts = [f"{error.severity}: {error.message}"]

    # location arrow
    parts.append(f"  --> {error.path}  line {error.line}:{error.col}")

    # gutter width — based on line number digits
    gutter = len(str(error.line))
    pad = " " * gutter

    parts.append(f"{pad} |")

    # source line
    if 0 <= line_idx < len(lines):
        src_line = lines[line_idx]
        parts.append(f"{error.line:{gutter}} | {src_line}")

        # underline: point to the token at col
        # try to underline the whole token (non-whitespace run from col)
        col_idx = error.col - 1  # 0-based
        token_len = _token_length(src_line, col_idx)
        underline = " " * col_idx + "^" * max(token_len, 1)
        parts.append(f"{pad} | {underline}")
    else:
        parts.append(f"{pad} |")

    parts.append(f"{pad} |")

    # hint
    if error.hint:
        parts.append(f"{pad} = hint: {error.hint}")
        parts.append("")

    return "\n".join(parts)


def format_errors(errors: list[LintError], src: str) -> str:
    """Format all errors. Returns empty string if no errors."""
    if not errors:
        return ""

    sections = [format_error(e, src) for e in errors]

    # summary line
    n_errors   = sum(1 for e in errors if e.severity == "error")
    n_warnings = sum(1 for e in errors if e.severity == "warning")

    parts = []
    if n_errors:
        parts.append(f"{n_errors} error{'s' if n_errors != 1 else ''}")
    if n_warnings:
        parts.append(f"{n_warnings} warning{'s' if n_warnings != 1 else ''}")

    sections.append("aborting due to " + " and ".join(parts))
    return "\n".join(sections)


def _token_length(line: str, col: int) -> int:
    """Return length of the token starting at col (non-whitespace run)."""
    if col >= len(line):
        return 1
    end = col
    while end < len(line) and not line[end].isspace():
        end += 1
    return max(end - col, 1)