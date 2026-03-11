from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node


@dataclass
class Module(Node):
    """
    Root node.
    Build order of body:
      CodeStartHook → Docstring, Imports, Utilities
      → JsonDef entries → TypeDef entries → Struct entries
      → CodeEndHook
    """

    def __post_init__(self):
        self.body.extend(
            [
                Docstring(parent=self),
                Imports(parent=self),
                Utilities(parent=self),
                CodeStartHook(parent=self),
            ]
        )

    @property
    def docstring(self) -> Docstring:
        return self.body[0]  # type: ignore

    @property
    def imports(self) -> Imports:
        return self.body[1]  # type: ignore

    @property
    def utilities(self) -> Imports:
        return self.body[2]  # type: ignore

    @property
    def code_start(self) -> Imports:
        return self.body[3]  # type: ignore


@dataclass
class CodeStartHook(Node):
    """
    User code insertion point before all generated code.
    Codegen emits body content verbatim at the top of the output file.
    """

    pass


@dataclass
class CodeEndHook(Node):
    """
    User code insertion point after all generated structs.
    Codegen emits body content verbatim at the bottom of the output file.
    """

    pass


@dataclass
class Docstring(Node):
    """Module-level docstring. DSL: doc "text" """

    value: str = ""


@dataclass
class Imports(Node):
    """
    Technical node — codegen inserts required import statements into body.
    Not produced from DSL directly; populated during codegen phase.
    
    transform_imports: Dict of imports by target language (e.g., {"py": {...}, "js": {...}})
                       Collected during parsing when TransformCall nodes are created.
    """

    libs: list[str] = field(default_factory=list)
    transform_imports: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class Utilities(Node):
    """
    Technical node — codegen inserts shared helper functions into body.
    Not produced from DSL directly; populated during codegen phase.
    """

    pass
