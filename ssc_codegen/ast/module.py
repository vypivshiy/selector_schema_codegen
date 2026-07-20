from __future__ import annotations
import warnings
from dataclasses import dataclass

from .base import Node


@dataclass
class Module(Node):
    """
    Root node.
    Build order of body:
      Utilities, CodeStartHook
      → JsonDef entries → TypeDef entries → Struct entries
      → CodeEndHook

    The module-level docstring lives in the ``doc`` field and is always
    emitted first by the converter (before any body traversal).

    Import statements are no longer AST body nodes — the converter emits
    them directly from the ``visit_module`` handler based on module shape
    (REST present, REST-only, separate runtime) and build options.

    ``source_file`` is the basename of the originating .kdl file; populated
    by the parser from ParseContext.source_path. Used by codegen to format
    source-location messages for Assert/Re/etc.
    """

    doc: str = ""
    source_file: str = ""

    def __post_init__(self):
        self.body.extend(
            [
                Utilities(parent=self),
                CodeStartHook(parent=self),
            ]
        )

    @property
    def docstring(self) -> Docstring:
        warnings.warn(
            "Module.docstring is deprecated; use the Module.doc field instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Docstring(parent=self, value=self.doc)

    @docstring.setter
    def docstring(self, value: "Docstring | str") -> None:
        warnings.warn(
            "Module.docstring is deprecated; use the Module.doc field instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.doc = value.value if isinstance(value, Docstring) else str(value)

    @property
    def utilities(self) -> Utilities:
        return self.body[0]  # type: ignore

    @property
    def code_start(self) -> CodeStartHook:
        return self.body[1]  # type: ignore


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
    """DEPRECATED: use the ``doc`` field on ``Module`` instead.

    Module-level docstring. DSL: ``doc "text"``.
    Retained only for backward-compatibility imports; the class emits a
    DeprecationWarning on instantiation and is no longer added to
    ``Module.body`` by ``Module.__post_init__``.
    """

    value: str = ""

    def __post_init__(self) -> None:
        warnings.warn(
            "Docstring node is deprecated; use Module.doc instead.",
            DeprecationWarning,
            stacklevel=2,
        )


@dataclass
class Utilities(Node):
    """
    Technical node — codegen inserts shared helper functions into body.
    Not produced from DSL directly; populated during codegen phase.
    """

    pass
