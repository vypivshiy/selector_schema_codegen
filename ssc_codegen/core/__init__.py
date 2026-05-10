"""ssc_codegen.core — unified KDL -> Module AST reader with integrated linting."""
from ssc_codegen.core.reader import parse_module, SscReader, ReadDiagnostic
from ssc_codegen.core.format import format_diagnostics, format_diagnostic
__all__ = [
    "parse_module",
    "SscReader",
    "ReadDiagnostic",
    "format_diagnostics",
    "format_diagnostic"
]