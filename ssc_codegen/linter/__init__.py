from ssc_codegen.linter.base import LINTER, LintError, LintResult, ErrorCode
from ssc_codegen.linter.format_errors import (
    format_errors, 
    format_error, 
    lint_file, 
    lint_string,
)

# singleton load rules
from ssc_codegen.linter import rules # type: ignore
from ssc_codegen.linter import rules_struct  # type: ignore
from ssc_codegen.linter import type_rules  # type: ignore

__all__ = [
    # Core classes
    "LINTER",
    "LintError",
    "LintResult",
    "ErrorCode",
    # Formatting
    "format_errors",
    "format_error",
    # Linting API
    "lint_file",
    "lint_string",
]
