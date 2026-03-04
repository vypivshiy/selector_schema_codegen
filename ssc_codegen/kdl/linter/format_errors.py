"""
Rust-style error formatter for KDL DSL lint errors.

Output example (with file path):

  error: 'css' requires a CSS query argument
    --> schemas/demo.kdl:3:9  [struct Demo > title]
     |
   3 |         css
     |         ^^^
     |
     = hint: example: css ".my-class"

Usage:

    # from file path — file is read automatically
    errors, output = lint_file("schemas/demo.kdl")
    print(output)

    # from string
    errors, output = lint_string(src)
    print(output)

    # format separately
    print(format_errors(errors, filepath="schemas/demo.kdl"))
    print(format_errors(errors, src=src))
    print(format_errors(errors, src=src, filepath="schemas/demo.kdl"))

    # JSON output for LLM pipelines
    errors, output = lint_file("demo.kdl", fmt="json")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from ssc_codegen.kdl.linter.base import LintError, LINTER


# ── core formatter ─────────────────────────────────────────────────────────────

def format_error(
    error: LintError,
    src: str | None = None,
    filepath: str | Path | None = None,
) -> str:
    """
    Format a single LintError in rust-style with source context.

    Provide either:
      - filepath  — file is read automatically
      - src       — use source string directly (no path in output)
      - both      — src used as-is, filepath shown in location arrow
    """
    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding="utf-8")
    elif src is None:
        src = ""

    filepath_str = str(filepath) if filepath else None
    lines = src.splitlines()
    line_idx = error.line - 1  # 0-based

    # header
    parts = [f"{error.severity}: {error.message}"]

    # location arrow
    if filepath_str:
        parts.append(
            f"  --> {filepath_str}:{error.line}:{error.col}"
            f"  [{error.path}]"
        )
    else:
        parts.append(f"  --> {error.path}  line {error.line}:{error.col}")

    gutter = len(str(error.line))
    pad = " " * gutter

    parts.append(f"{pad} |")

    if 0 <= line_idx < len(lines):
        src_line = lines[line_idx]
        parts.append(f"{error.line:{gutter}} | {src_line}")

        col_idx = error.col - 1  # 0-based
        token_len = _token_length(src_line, col_idx)
        underline = " " * col_idx + "^" * max(token_len, 1)
        parts.append(f"{pad} | {underline}")
    else:
        parts.append(f"{pad} |")

    parts.append(f"{pad} |")

    if error.hint:
        parts.append(f"{pad} = hint: {error.hint}")
        parts.append("")

    return "\n".join(parts)


def format_errors(
    errors: list[LintError],
    src: str | None = None,
    filepath: str | Path | None = None,
    fmt: Literal["text", "json"] = "text",
) -> str:
    """
    Format all errors.

    Provide either:
      - filepath  — file is read automatically
      - src       — use source string directly (no path in output)
      - both      — src used as-is, filepath shown in location arrows

    Args:
        fmt: 'text' for human output, 'json' for LLM pipelines

    Returns empty string if no errors.
    """
    if not errors:
        return ""

    if fmt == "json":
        return json.dumps([e.to_dict() for e in errors], indent=2)

    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding="utf-8")
    elif src is None:
        src = ""

    sections = [format_error(e, src=src, filepath=filepath) for e in errors]

    n_errors   = sum(1 for e in errors if e.severity == "error")
    n_warnings = sum(1 for e in errors if e.severity == "warning")

    summary_parts: list[str] = []
    if n_errors:
        summary_parts.append(f"{n_errors} error{'s' if n_errors != 1 else ''}")
    if n_warnings:
        summary_parts.append(f"{n_warnings} warning{'s' if n_warnings != 1 else ''}")

    sections.append("aborting due to " + " and ".join(summary_parts))
    return "\n".join(sections)


# ── file API ───────────────────────────────────────────────────────────────────

def lint_file(
    path: str | Path,
    fmt: Literal["text", "json"] = "text",
) -> tuple[list[LintError], str]:
    """
    Lint a KDL file by path. File is read once and reused for formatting.

    Returns (errors, formatted_output).
    formatted_output is empty string if no errors.

    Usage:
        errors, output = lint_file("schemas/demo.kdl")
        if errors:
            print(output)
            sys.exit(1)

        # for LLM pipeline
        errors, output = lint_file("demo.kdl", fmt="json")
    """
    path = Path(path)
    src = path.read_text(encoding="utf-8")
    errors = LINTER.lint(src)
    output = format_errors(errors, src=src, filepath=path, fmt=fmt)
    return errors, output


def lint_string(
    src: str,
    fmt: Literal["text", "json"] = "text",
) -> tuple[list[LintError], str]:
    """
    Lint a KDL string directly. No file path shown in output.

    Returns (errors, formatted_output).
    """
    errors = LINTER.lint(src)
    output = format_errors(errors, src=src, fmt=fmt)
    return errors, output


# ── internal ───────────────────────────────────────────────────────────────────

def _token_length(line: str, col: int) -> int:
    """Return length of the token starting at col (non-whitespace run)."""
    if col >= len(line):
        return 1
    end = col
    while end < len(line) and not line[end].isspace():
        end += 1
    return max(end - col, 1)