class ParseError(Exception):
    """Raised on DSL syntax or semantic error during AST construction."""


class BuildTimeError(ParseError):
    """Type mismatch or unresolved reference detected at AST build time."""
