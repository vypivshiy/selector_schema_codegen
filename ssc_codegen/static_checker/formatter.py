# ssc_codegen/static_checker/formatter.py

import os
import sys
from pathlib import Path
from typing import List

from .v2 import AnalysisError

_USE_COLORAMA = False
if sys.platform == "win32":
    try:
        import colorama

        colorama.init()
        _USE_COLORAMA = True
    except ImportError:
        pass

_RESET = "\033[0m"
_ERROR = "\033[91m"
_NOTE = "\033[90m"
_HELP = "\033[96m"


def _should_use_color() -> bool:
    if sys.platform == "win32":
        return _USE_COLORAMA
    return sys.stdout.isatty()


def _find_method_position(
    code_line: str, method: str
) -> tuple[int, int] | None:
    """Find the position of `.method(` in the code line."""
    pattern = f".{method}("
    pos = code_line.find(pattern)
    if pos != -1:
        start = pos + 1  # after '.'
        end = start + len(method)
        return start, end
    return None


def format_error(err: AnalysisError) -> str:
    """Format exception for output. Fmt error style inspired from rust language"""
    use_color = _should_use_color()
    reset = _RESET if use_color else ""
    error_color = _ERROR if use_color else ""
    note_color = _NOTE if use_color else ""
    help_color = _HELP if use_color else ""

    lines = []
    lines.append(f"{error_color}error:{reset} {err.message}")

    if err.filename and err.lineno:
        try:
            source_lines = (
                Path(err.filename).read_text(encoding="utf-8").splitlines()
            )
            code_line = source_lines[err.lineno - 1].rstrip()

            # Build err marker
            marker = ""
            marker_start = 0

            if err.problem_method:
                if pos := _find_method_position(code_line, err.problem_method):
                    marker_start, end = pos
                    marker = "^" * (end - marker_start)

            if not marker:
                eq_pos = code_line.find("=")
                if eq_pos != -1:
                    marker_start = eq_pos + 1
                    while (
                        marker_start < len(code_line)
                        and code_line[marker_start].isspace()
                    ):
                        marker_start += 1
                    marker = "^" * (len(code_line) - marker_start)
                else:
                    marker_start = 0
                    marker = "^" * len(code_line)

            rel_path = os.path.relpath(err.filename)
            line_num_str = str(err.lineno)

            line_width = 4
            line_num_str = str(err.lineno)

            empty_gutter = " " * line_width + " |"
            code_prefix = f"{line_num_str:>{line_width}} |"
            marker_prefix = empty_gutter

            lines.append(f" {note_color}-->{reset} {rel_path}:{err.lineno}")
            lines.append(f"{note_color}{empty_gutter}{reset}")
            lines.append(f"{note_color}{code_prefix}{reset} {code_line}")
            lines.append(
                f"{note_color}{marker_prefix}{reset} "
                f"{' ' * marker_start}{marker}"
            )

        except (OSError, IndexError):
            rel_path = os.path.relpath(err.filename)
            lines.append(f" {note_color}-->{reset} {rel_path}:{err.lineno}")

    if err.tip:
        lines.append(
            f" {help_color}={reset} {help_color}help:{reset} {err.tip}"
        )

    return "\n".join(lines)


def format_all_errors(errors: List[AnalysisError]) -> str:
    if not errors:
        return ""
    return "\n\n".join(format_error(err) for err in errors)
