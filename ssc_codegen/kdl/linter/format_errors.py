"""Rust-style diagnostic formatter for KDL DSL lint errors."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from ssc_codegen.kdl.linter.base import LINTER, LintError, LintResult

_KDL_TEXT_ENCODING = "utf-8-sig"

# Windows ANSI backport
try:
    import colorama

    colorama.init(autoreset=False)
    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"


def format_error(
    error: LintError,
    src: str | None = None,
    filepath: str | Path | None = None,
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    """Format a single lint error with source context."""
    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding=_KDL_TEXT_ENCODING)
    elif src is None:
        src = ""

    if use_color is None:
        use_color = _should_use_color()

    colors = _Palette.enabled() if use_color else _Palette.disabled()
    filepath_str = str(filepath) if filepath else None
    lines = src.splitlines()
    line_idx = error.line - 1

    severity_head = _style(
        f"{error.severity}[{error.code.value}]",
        color=colors.severity(error.severity),
        bold=True,
        use_color=use_color,
    )
    parts = [f"{severity_head}: {error.message}"]

    if filepath_str:
        location = f"{filepath_str}:{error.line}:{error.col}"
    else:
        location = f"line {error.line}:{error.col}"
    parts.append(f"  {_style('-->', color=colors.dim, use_color=use_color)} {location}")

    display_start, display_end = _visible_line_window(error.line, len(lines), context_lines)
    gutter_width = len(str(display_end))
    pad = " " * gutter_width
    gutter_bar = _style('|', color=colors.dim, use_color=use_color)

    parts.append(f"{pad} {gutter_bar}")

    if lines and 0 <= line_idx < len(lines):
        for line_no in range(display_start, display_end + 1):
            src_line = lines[line_no - 1]
            line_num = _style(f"{line_no:>{gutter_width}}", color=colors.dim, use_color=use_color)
            parts.append(f"{line_num} {gutter_bar} {src_line}")
            if line_no == error.line:
                underline = _build_underline(error, src_line)
                marker = _style(underline, color=colors.severity(error.severity), bold=True, use_color=use_color)
                label = error.display_label
                if label:
                    label_text = _style(label, color=colors.severity(error.severity), use_color=use_color)
                    parts.append(f"{pad} {gutter_bar} {marker} {label_text}")
                else:
                    parts.append(f"{pad} {gutter_bar} {marker}")
    else:
        parts.append(f"{pad} {gutter_bar}")

    parts.append(f"{pad} {gutter_bar}")

    if error.path:
        parts.append(f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('scope:', color=colors.cyan, bold=True, use_color=use_color)} {error.path}")
    if error.hint:
        parts.append(f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('help:', color=colors.cyan, bold=True, use_color=use_color)} {error.hint}")
    for note in error.notes:
        parts.append(f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('note:', color=colors.magenta, bold=True, use_color=use_color)} {note}")

    return "\n".join(parts)


def format_errors(
    errors: list[LintError],
    src: str | None = None,
    filepath: str | Path | None = None,
    fmt: Literal["text", "json"] = "text",
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    """Format all lint diagnostics."""
    if not errors:
        return ""

    if fmt == "json":
        return json.dumps([e.to_dict() for e in errors], indent=2)

    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding=_KDL_TEXT_ENCODING)
    elif src is None:
        src = ""

    if use_color is None:
        use_color = _should_use_color()

    sections = [
        format_error(
            e,
            src=src,
            filepath=filepath,
            use_color=use_color,
            context_lines=context_lines,
        )
        for e in errors
    ]

    n_errors = sum(1 for e in errors if e.severity == "error")
    n_warnings = sum(1 for e in errors if e.severity == "warning")
    summary = _format_summary(n_errors, n_warnings, use_color=use_color)

    return "\n\n".join([*sections, summary])


def lint_file(filepath: str | Path) -> LintResult:
    """Lint a KDL schema file."""
    filepath = Path(filepath)
    src = filepath.read_text(encoding=_KDL_TEXT_ENCODING)
    return LINTER.lint(src, filepath=filepath)


def lint_string(src: str) -> LintResult:
    """Lint a KDL schema string (for tests)."""
    return LINTER.lint(src, filepath=None)


class _Palette:
    def __init__(self, *, red: str, yellow: str, cyan: str, magenta: str, dim: str):
        self.red = red
        self.yellow = yellow
        self.cyan = cyan
        self.magenta = magenta
        self.dim = dim

    @classmethod
    def enabled(cls) -> '_Palette':
        return cls(red=_RED, yellow=_YELLOW, cyan=_CYAN, magenta=_MAGENTA, dim=_DIM)

    @classmethod
    def disabled(cls) -> '_Palette':
        return cls(red='', yellow='', cyan='', magenta='', dim='')

    def severity(self, severity: str) -> str:
        return self.red if severity == 'error' else self.yellow


def _format_summary(n_errors: int, n_warnings: int, *, use_color: bool) -> str:
    colors = _Palette.enabled() if use_color else _Palette.disabled()
    counts: list[str] = []
    if n_errors:
        counts.append(f"{n_errors} error{'s' if n_errors != 1 else ''}")
    if n_warnings:
        counts.append(f"{n_warnings} warning{'s' if n_warnings != 1 else ''}")
    if not counts:
        counts.append("0 diagnostics")

    if n_errors:
        prefix = _style("Lint failed", color=colors.red, bold=True, use_color=use_color)
    elif n_warnings:
        prefix = _style("Lint completed with warnings", color=colors.yellow, bold=True, use_color=use_color)
    else:
        prefix = _style("Lint completed", color=colors.cyan, bold=True, use_color=use_color)
    return f"{prefix}: {', '.join(counts)}"


def _visible_line_window(line_no: int, total_lines: int, context_lines: int) -> tuple[int, int]:
    if total_lines <= 0:
        return (line_no, line_no)
    start = max(1, line_no - context_lines)
    end = min(total_lines, line_no + context_lines)
    return (start, end)


def _build_underline(error: LintError, src_line: str) -> str:
    col_idx = max(error.col - 1, 0)
    end_idx = _resolve_end_col(error, src_line, col_idx)
    caret_len = max(end_idx - col_idx, 1)
    return " " * col_idx + "^" * caret_len


def _resolve_end_col(error: LintError, src_line: str, col_idx: int) -> int:
    if (
        error.end_line == error.line
        and error.end_col is not None
        and error.end_col > error.col
    ):
        return min(max(error.end_col - 1, col_idx + 1), len(src_line))
    token_len = _token_length(src_line, col_idx)
    return min(col_idx + max(token_len, 1), max(len(src_line), col_idx + 1))


def _token_length(line: str, col: int) -> int:
    """Return length of the token starting at col (non-whitespace run)."""
    if col >= len(line):
        return 1
    end = col
    while end < len(line) and not line[end].isspace():
        end += 1
    return max(end - col, 1)


def _should_use_color() -> bool:
    if sys.platform == 'win32':
        return _COLORAMA_AVAILABLE
    return hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()


def _style(text: str, *, color: str = '', bold: bool = False, use_color: bool) -> str:
    if not use_color:
        return text
    prefix = f"{color}{_BOLD if bold else ''}"
    if not prefix:
        return text
    return f"{prefix}{text}{_RESET}"
