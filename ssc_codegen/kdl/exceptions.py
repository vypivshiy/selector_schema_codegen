class ParseError(Exception):
    """Raised on DSL syntax or semantic error during AST construction."""


class UnknownNodeError(ParseError):
    def __init__(self, name: str, context: str) -> None:
        super().__init__(f"Unknown {context} node: {name!r}")


class BuildTimeError(ParseError):
    """Type mismatch or unresolved reference detected at AST build time."""
