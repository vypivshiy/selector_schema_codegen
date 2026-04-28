"""Diagnostics formatting — human-readable (Rust-style) and JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from ssc_codegen.kdl import ReadDiagnostic, Severity

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


def format_diagnostic(
    d: ReadDiagnostic,
    src: str | None = None,
    filepath: str | Path | None = None,
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding="utf-8-sig")
    elif src is None:
        src = ""

    if use_color is None:
        use_color = _should_use_color()

    colors = _Palette.enabled() if use_color else _Palette.disabled()
    filepath_str = str(filepath) if filepath else None
    lines = src.splitlines()

    line = d.span.start.line
    col = d.span.start.column
    end_line = d.span.end.line
    end_col = d.span.end.column

    severity_head = _style(
        f"{d.severity.value}[{d.code}]",
        color=colors.severity(d.severity),
        bold=True,
        use_color=use_color,
    )
    parts = [f"{severity_head}: {d.message}"]

    if filepath_str:
        location = f"{filepath_str}:{line}:{col}"
    else:
        location = f"line {line}:{col}"
    parts.append(
        f"  {_style('-->', color=colors.dim, use_color=use_color)} {location}"
    )

    display_start, display_end = _visible_line_window(
        line, len(lines), context_lines
    )
    gutter_width = len(str(display_end))
    pad = " " * gutter_width
    gutter_bar = _style("|", color=colors.dim, use_color=use_color)

    parts.append(f"{pad} {gutter_bar}")

    line_idx = line - 1
    if lines and 0 <= line_idx < len(lines):
        for line_no in range(display_start, display_end + 1):
            src_line = lines[line_no - 1]
            line_num = _style(
                f"{line_no:>{gutter_width}}",
                color=colors.dim,
                use_color=use_color,
            )
            parts.append(f"{line_num} {gutter_bar} {src_line}")
            if line_no == line:
                underline = _build_underline(
                    col, end_col, end_line, line, src_line
                )
                marker = _style(
                    underline,
                    color=colors.severity(d.severity),
                    bold=True,
                    use_color=use_color,
                )
                label = d.label
                if label:
                    label_text = _style(
                        label,
                        color=colors.severity(d.severity),
                        use_color=use_color,
                    )
                    parts.append(f"{pad} {gutter_bar} {marker} {label_text}")
                else:
                    parts.append(f"{pad} {gutter_bar} {marker}")
    else:
        parts.append(f"{pad} {gutter_bar}")

    parts.append(f"{pad} {gutter_bar}")

    if d.path:
        parts.append(
            f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('scope:', color=colors.cyan, bold=True, use_color=use_color)} {d.path}"
        )
    if d.hint:
        parts.append(
            f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('help:', color=colors.cyan, bold=True, use_color=use_color)} {d.hint}"
        )
    for note in d.notes:
        parts.append(
            f"{pad} {_style('=', color=colors.dim, use_color=use_color)} {_style('note:', color=colors.magenta, bold=True, use_color=use_color)} {note}"
        )

    return "\n".join(parts)


def format_diagnostics(
    diagnostics: list[ReadDiagnostic],
    src: str | None = None,
    filepath: str | Path | None = None,
    fmt: Literal["text", "json"] = "text",
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    if not diagnostics:
        return ""

    if fmt == "json":
        return json.dumps([_diag_to_dict(d) for d in diagnostics], indent=2)

    if src is None and filepath is not None:
        src = Path(filepath).read_text(encoding="utf-8-sig")
    elif src is None:
        src = ""

    if use_color is None:
        use_color = _should_use_color()

    sections = [
        format_diagnostic(
            d,
            src=src,
            filepath=filepath,
            use_color=use_color,
            context_lines=context_lines,
        )
        for d in diagnostics
    ]

    n_errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
    n_warnings = sum(1 for d in diagnostics if d.severity == Severity.WARNING)
    summary = _format_summary(n_errors, n_warnings, use_color=use_color)

    return "\n\n".join([*sections, summary])


def diagnostic_to_dict(d: ReadDiagnostic) -> dict:
    """Serialize a single diagnostic to a JSON-friendly dict."""
    return _diag_to_dict(d)


def diagnostics_to_dict(diagnostics: list[ReadDiagnostic]) -> dict:
    """Serialize diagnostics + summary counts to a JSON-friendly dict."""
    n_errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
    n_warnings = sum(1 for d in diagnostics if d.severity == Severity.WARNING)
    return {
        "errors": [_diag_to_dict(d) for d in diagnostics],
        "error_count": n_errors,
        "warning_count": n_warnings,
    }


# ── internal ──────────────────────────────────────────────────────────────────


def _diag_to_dict(d: ReadDiagnostic) -> dict:
    s = d.span.start
    e = d.span.end
    return {
        "code": d.code,
        "severity": d.severity.value,
        "message": d.message,
        "hint": d.hint,
        "path": d.path,
        "label": d.label,
        "notes": list(d.notes),
        "span": {
            "start": {"offset": s.offset, "line": s.line, "column": s.column},
            "end": {"offset": e.offset, "line": e.line, "column": e.column},
        },
    }


class _Palette:
    def __init__(
        self, *, red: str, yellow: str, cyan: str, magenta: str, dim: str
    ):
        self.red = red
        self.yellow = yellow
        self.cyan = cyan
        self.magenta = magenta
        self.dim = dim

    @classmethod
    def enabled(cls) -> _Palette:
        return cls(
            red=_RED, yellow=_YELLOW, cyan=_CYAN, magenta=_MAGENTA, dim=_DIM
        )

    @classmethod
    def disabled(cls) -> _Palette:
        return cls(red="", yellow="", cyan="", magenta="", dim="")

    def severity(self, sev: Severity) -> str:
        return self.red if sev == Severity.ERROR else self.yellow


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
        prefix = _style(
            "Lint failed", color=colors.red, bold=True, use_color=use_color
        )
    elif n_warnings:
        prefix = _style(
            "Lint completed with warnings",
            color=colors.yellow,
            bold=True,
            use_color=use_color,
        )
    else:
        prefix = _style(
            "Lint completed", color=colors.cyan, bold=True, use_color=use_color
        )
    return f"{prefix}: {', '.join(counts)}"


def _visible_line_window(
    line_no: int, total_lines: int, context_lines: int
) -> tuple[int, int]:
    if total_lines <= 0:
        return (line_no, line_no)
    start = max(1, line_no - context_lines)
    end = min(total_lines, line_no + context_lines)
    return (start, end)


def _build_underline(
    col: int, end_col: int, end_line: int, line: int, src_line: str
) -> str:
    col_idx = max(col - 1, 0)
    if end_line == line and end_col > col:
        end_idx = min(end_col - 1, len(src_line))
    else:
        end_idx = col_idx + _token_length(src_line, col_idx)
    caret_len = max(end_idx - col_idx, 1)
    return " " * col_idx + "^" * caret_len


def _token_length(line: str, col: int) -> int:
    if col >= len(line):
        return 1
    end = col
    while end < len(line) and not line[end].isspace():
        end += 1
    return max(end - col, 1)


def _should_use_color() -> bool:
    if sys.platform == "win32":
        return _COLORAMA_AVAILABLE
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _style(
    text: str, *, color: str = "", bold: bool = False, use_color: bool
) -> str:
    if not use_color:
        return text
    prefix = f"{color}{_BOLD if bold else ''}"
    if not prefix:
        return text
    return f"{prefix}{text}{_RESET}"
