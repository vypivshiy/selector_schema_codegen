"""ssc_codegen.core — unified KDL -> Module AST reader with integrated linting."""
from ssc_codegen.core.reader import parse_module
from ssc_codegen.core.format import format_diagnostics, format_diagnostic
from kdlquery import ReadDiagnostic
__all__ = [
    "parse_module",
    "ReadDiagnostic",
    "format_diagnostics",
    "format_diagnostic"
]
