"""Compatibility shim — re-exports from kdlquery."""

from kdlquery.parser import (
    CSTArgEntry,
    CSTDocument,
    CSTEntry,
    CSTIdentifier,
    CSTNode,
    CSTPropEntry,
    CSTTypeAnnotation,
    CSTValue,
    KDL2CSTParser,
    KDLParseError,
    KDLLexer,
    Position,
    Span,
    Token,
    TokenType,
)
from kdlquery.dict_reader import DictReader
from kdlquery.reader import (
    DiagnosticCollector,
    KdlValue,
    KdlNode,
    ReadDiagnostic,
    Reader,
    Severity,
    WalkContext,
    Walker,
    parse_into,
)

KdlArg = KdlValue

__all__ = [
    "CSTArgEntry",
    "CSTDocument",
    "CSTEntry",
    "CSTIdentifier",
    "CSTNode",
    "CSTPropEntry",
    "CSTTypeAnnotation",
    "CSTValue",
    "KDL2CSTParser",
    "KDLParseError",
    "KDLLexer",
    "Position",
    "Span",
    "Token",
    "TokenType",
    "DiagnosticCollector",
    "KdlArg",
    "KdlNode",
    "ReadDiagnostic",
    "Reader",
    "Severity",
    "WalkContext",
    "Walker",
    "parse_into",
    "DictReader",
]
