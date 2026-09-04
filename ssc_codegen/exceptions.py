"""Core exception hierarchy for ssc_codegen.

This module defines base and specialized exceptions raised during KDL schema parsing,
AST construction, type checking, and target compilation.
"""

from __future__ import annotations


class ParseError(Exception):
    """Base exception for syntax, semantic, or structural errors in schema parsing.

    Raised when a KDL document violates DSL grammar, cannot be parsed, or fails
    fundamental structural checks during AST creation.

    Examples:
        ```python
        from ssc_codegen.exceptions import ParseError

        try:
            # parsing invalid syntax
            raise ParseError("Missing required struct identifier")
        except ParseError as exc:
            print(f"Schema error: {exc}")
        ```
    """


class BuildTimeError(ParseError):
    """Exception raised for semantic errors and type mismatches during AST build.

    Raised during AST compilation passes when symbol references cannot be resolved,
    pipeline type inferences fail, or incompatible configurations are encountered.

    Examples:
        ```python
        from ssc_codegen.exceptions import BuildTimeError

        try:
            raise BuildTimeError("Unknown type reference 'UnknownStruct'")
        except BuildTimeError as exc:
            print(f"Build time validation error: {exc}")
        ```
    """
