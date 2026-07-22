"""Diagnostics formatting — human-readable (Rust-style) and JSON."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from kdlquery import ReadDiagnostic, Severity

try:
    import colorama

    colorama.init(autoreset=False)
    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False

# ── ANSI escape codes ─────────────────────────────────────────────────────────

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"


# ── Public API ────────────────────────────────────────────────────────────────


def format_diagnostic(
    d: ReadDiagnostic,
    src: str | None = None,
    filepath: str | Path | None = None,
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    """Format a single diagnostic as a human-readable Rust-style string."""
    src = _resolve_src(src, filepath)
    renderer = _Renderer(use_color=_resolve_color(use_color))
    return renderer.render(
        d, src=src, filepath=filepath, context_lines=context_lines
    )


def format_diagnostics(
    diagnostics: list[ReadDiagnostic],
    src: str | None = None,
    filepath: str | Path | None = None,
    fmt: Literal["text", "json"] = "text",
    *,
    use_color: bool | None = None,
    context_lines: int = 1,
) -> str:
    """Format a list of diagnostics as text or JSON."""
    if not diagnostics:
        return ""

    if fmt == "json":
        return json.dumps(
            [diagnostic_to_dict(d) for d in diagnostics], indent=2
        )

    src = _resolve_src(src, filepath)
    renderer = _Renderer(use_color=_resolve_color(use_color))

    sections = [
        renderer.render(
            d, src=src, filepath=filepath, context_lines=context_lines
        )
        for d in diagnostics
    ]
    summary = renderer.render_summary(diagnostics)
    return "\n\n".join([*sections, summary])


def diagnostic_to_dict(d: ReadDiagnostic) -> dict[str, Any]:
    """Serialize a single diagnostic to a JSON-friendly dict."""
    s, e = d.span.start, d.span.end
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


# ── Renderer ──────────────────────────────────────────────────────────────────


@dataclass
class _Renderer:
    """Renders diagnostics using ANSI color sequences when enabled."""

    use_color: bool

    # Derived color values — populated in __post_init__
    _red: str = field(init=False)
    _yellow: str = field(init=False)
    _cyan: str = field(init=False)
    _magenta: str = field(init=False)
    _dim: str = field(init=False)

    def __post_init__(self) -> None:
        if self.use_color:
            self._red, self._yellow = _RED, _YELLOW
            self._cyan, self._magenta, self._dim = _CYAN, _MAGENTA, _DIM
        else:
            self._red = self._yellow = self._cyan = self._magenta = (
                self._dim
            ) = ""

    # ── public render methods ─────────────────────────────────────────────────

    def render(
        self,
        d: ReadDiagnostic,
        *,
        src: str,
        filepath: str | Path | None,
        context_lines: int,
    ) -> str:
        lines = src.splitlines()
        line, col = d.span.start.line, d.span.start.column
        end_line, end_col = d.span.end.line, d.span.end.column

        display_start, display_end = _line_window(
            line, len(lines), context_lines
        )
        gutter_width = len(str(display_end))
        pad = " " * gutter_width

        parts: list[str] = [
            self._header(d),
            self._location_arrow(d, filepath, pad),
            self._gutter_blank(pad),
        ]

        if lines and 0 <= line - 1 < len(lines):
            parts += self._source_block(
                lines,
                line,
                col,
                end_line,
                end_col,
                d,
                display_start,
                display_end,
                pad,
            )
        else:
            parts.append(self._gutter_blank(pad))

        parts.append(self._gutter_blank(pad))
        parts += self._footer_annotations(d, pad)

        return "\n".join(parts)

    def render_summary(self, diagnostics: list[ReadDiagnostic]) -> str:
        n_errors = _count(diagnostics, Severity.ERROR)
        n_warnings = _count(diagnostics, Severity.WARNING)

        counts: list[str] = []
        if n_errors:
            counts.append(f"{n_errors} error{'s' if n_errors != 1 else ''}")
        if n_warnings:
            counts.append(
                f"{n_warnings} warning{'s' if n_warnings != 1 else ''}"
            )
        if not counts:
            counts.append("0 diagnostics")

        if n_errors:
            prefix = self._styled("Lint failed", color=self._red, bold=True)
        elif n_warnings:
            prefix = self._styled(
                "Lint completed with warnings", color=self._yellow, bold=True
            )
        else:
            prefix = self._styled("Lint completed", color=self._cyan, bold=True)

        return f"{prefix}: {', '.join(counts)}"

    # ── private rendering helpers ─────────────────────────────────────────────

    def _header(self, d: ReadDiagnostic) -> str:
        sev_color = self._severity_color(d.severity)
        severity_head = self._styled(
            f"{d.severity.value}[{d.code}]", color=sev_color, bold=True
        )
        return f"{severity_head}: {d.message}"

    def _location_arrow(
        self, d: ReadDiagnostic, filepath: str | Path | None, pad: str
    ) -> str:
        line, col = d.span.start.line, d.span.start.column
        location = (
            f"{filepath}:{line}:{col}" if filepath else f"line {line}:{col}"
        )
        arrow = self._styled("-->", color=self._dim)
        return f"  {arrow} {location}"

    def _gutter_blank(self, pad: str) -> str:
        return f"{pad} {self._styled('|', color=self._dim)}"

    def _source_block(
        self,
        lines: list[str],
        line: int,
        col: int,
        end_line: int,
        end_col: int,
        d: ReadDiagnostic,
        display_start: int,
        display_end: int,
        pad: str,
    ) -> list[str]:
        gutter_width = len(pad)
        gutter_bar = self._styled("|", color=self._dim)
        parts: list[str] = []

        for line_no in range(display_start, display_end + 1):
            src_line = lines[line_no - 1]
            line_num = self._styled(
                f"{line_no:>{gutter_width}}", color=self._dim
            )
            parts.append(f"{line_num} {gutter_bar} {src_line}")

            if line_no == line:
                parts.append(
                    self._underline_row(
                        col, end_col, end_line, line, src_line, d, pad
                    )
                )

        return parts

    def _underline_row(
        self,
        col: int,
        end_col: int,
        end_line: int,
        line: int,
        src_line: str,
        d: ReadDiagnostic,
        pad: str,
    ) -> str:
        gutter_bar = self._styled("|", color=self._dim)
        sev_color = self._severity_color(d.severity)
        underline = _build_underline(col, end_col, end_line, line, src_line)
        marker = self._styled(underline, color=sev_color, bold=True)

        if d.label:
            label = self._styled(d.label, color=sev_color)
            return f"{pad} {gutter_bar} {marker} {label}"
        return f"{pad} {gutter_bar} {marker}"

    def _footer_annotations(self, d: ReadDiagnostic, pad: str) -> list[str]:
        parts: list[str] = []
        eq = self._styled("=", color=self._dim)

        if d.path:
            scope = self._styled("scope:", color=self._cyan, bold=True)
            parts.append(f"{pad} {eq} {scope} {d.path}")

        if d.hint:
            help_ = self._styled("help:", color=self._cyan, bold=True)
            parts.append(f"{pad} {eq} {help_} {d.hint}")

        for note in d.notes:
            note_label = self._styled("note:", color=self._magenta, bold=True)
            parts.append(f"{pad} {eq} {note_label} {note}")

        return parts

    # ── styling ───────────────────────────────────────────────────────────────

    def _styled(self, text: str, *, color: str = "", bold: bool = False) -> str:
        if not self.use_color:
            return text
        prefix = f"{color}{_BOLD if bold else ''}"
        return f"{prefix}{text}{_RESET}" if prefix else text

    def _severity_color(self, severity: Severity) -> str:
        return self._red if severity == Severity.ERROR else self._yellow


# ── Utilities ─────────────────────────────────────────────────────────────────


def _resolve_src(src: str | None, filepath: str | Path | None) -> str:
    if src is not None:
        return src
    if filepath is not None:
        return Path(filepath).read_text(encoding="utf-8-sig")
    return ""


def _resolve_color(use_color: bool | None) -> bool:
    if use_color is not None:
        return use_color
    if sys.platform == "win32":
        return _COLORAMA_AVAILABLE
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _count(diagnostics: list[ReadDiagnostic], severity: Severity) -> int:
    return sum(1 for d in diagnostics if d.severity == severity)


def _line_window(
    line_no: int, total_lines: int, context_lines: int
) -> tuple[int, int]:
    if total_lines <= 0:
        return (line_no, line_no)
    return max(1, line_no - context_lines), min(
        total_lines, line_no + context_lines
    )


def _build_underline(
    col: int, end_col: int, end_line: int, line: int, src_line: str
) -> str:
    col_idx = max(col - 1, 0)
    if end_line == line and end_col > col:
        end_idx = min(end_col - 1, len(src_line))
    else:
        end_idx = col_idx + _token_length(src_line, col_idx)
    return " " * col_idx + "^" * max(end_idx - col_idx, 1)


def _token_length(line: str, col: int) -> int:
    if col >= len(line):
        return 1
    end = col
    while end < len(line) and not line[end].isspace():
        end += 1
    return max(end - col, 1)
