from ssc_codegen.kdl.linter.base import LintError
from ssc_codegen.kdl.linter.rules import LINTER
from ssc_codegen.kdl.linter.format_errors import format_errors, format_error

__all__ = [
    "format_errors",
    "format_error",
    "run_linter"
]


def run_linter(code: str) -> list[LintError]:
    return LINTER.lint(code)
