"""AST root node, insertion hooks, and technical marker definitions for compiled modules.

This module defines the top-level intermediate representation container `Module` and its
structural child markers:
- `Module`: Root AST node containing all structs, functions, type definitions, and extensions.
- `CodeStartHook`: Insertion point for user code emitted before generated structs (`code-start`).
- `CodeEndHook`: Insertion point for user code emitted after generated structs (`code-end`).
- `Utilities`: Technical placeholder marking the location for standard runtime helper functions.
- `Docstring`: Deprecated node retained for backward compatibility (prefer `Module.doc`).
"""

from __future__ import annotations
import warnings
from dataclasses import dataclass
from dataclasses import field

from .base import Node


@dataclass
class Module(Node):
    """Root intermediate representation node for a compiled schema file.

    Maintains all schema definitions including JSON mappings, generated type
    definitions, user structs, and extension registries.

    Attributes:
        doc: Module-level docstring documentation.
        source_file: Basename of the originating source `.kdl` schema file.
        extensions: Registry mapping namespace names to custom `ExtensionDef` instances.
    """

    doc: str = ""
    source_file: str = ""
    extensions: dict[str, "ExtensionDef"] = field(default_factory=dict)

    def __post_init__(self):
        self.body.extend(
            [
                Utilities(parent=self),
                CodeStartHook(parent=self),
            ]
        )

    @property
    def docstring(self) -> Docstring:
        """Deprecated property for accessing module docstring.

        Warning:
            Deprecated: Use `Module.doc` instead.
        """
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
        """Reference to the module's utilities placeholder node."""
        return self.body[0]  # type: ignore

    @property
    def code_start(self) -> CodeStartHook:
        """Reference to the module's start hook node."""
        return self.body[1]  # type: ignore


@dataclass
class CodeStartHook(Node):
    """User code insertion point emitted before generated structs (`code-start`).

    Attributes:
        body: Ordered list of custom user-injected code nodes.
    """

    pass


@dataclass
class CodeEndHook(Node):
    """User code insertion point emitted after all generated structs (`code-end`).

    Attributes:
        body: Ordered list of custom user-injected code nodes.
    """

    pass


@dataclass
class Docstring(Node):
    """DEPRECATED: Module-level docstring node.

    Retained only for backward-compatibility; use `Module.doc` instead.

    Attributes:
        value: Text documentation string.
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
    """Technical AST node serving as the insertion point for standard helpers."""

    pass


from .extension import ExtensionDef  # noqa: E402
