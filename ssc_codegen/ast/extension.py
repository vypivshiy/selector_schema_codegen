"""AST nodes for user-defined custom extension operations and language targets.

This module defines models for custom extensions declared in `.kdl` via `extension Namespace { ... }`:
- `ExtensionDef`: Complete definition of an extension operation with signature and target bindings.
- `ExtensionTarget`: Target-language implementation (`py`, `js`, `go`) with imports, helpers, and template emit.
- `ExtensionCall`: Invocation AST node (`!Namespace.op-name`) placed in field pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .base import Node
from .types import TypeInfo, VariableType


@dataclass(frozen=True)
class ExtensionType:
    """Type signature pattern for custom extension operations.

    Attributes:
        base: Primitive variable type if fixed.
        generic: Identifier of the generic type variable (e.g. `"T"`).
        is_array: Flag indicating whether this type represents an array/list.
        is_optional: Flag indicating whether this type is optional.
    """

    base: VariableType | None = None
    generic: str | None = None
    is_array: bool = False
    is_optional: bool = False

    def resolve(self, binding: TypeInfo | None = None) -> TypeInfo:
        """Resolve this extension type into concrete TypeInfo.

        Args:
            binding: Bound input type when this signature is generic.

        Returns:
            Resolved `TypeInfo` instance.
        """
        if self.generic:
            if binding is None:
                return TypeInfo(base=VariableType.AUTO)
            return binding
        return TypeInfo(
            base=self.base or VariableType.AUTO,
            is_array=self.is_array,
            is_optional=self.is_optional,
        )

    def accepts(self, value: TypeInfo) -> bool:
        """Check if an incoming type satisfies this signature constraint.

        Args:
            value: Incoming pipeline type metadata.

        Returns:
            True if value is compatible with this signature.
        """
        if self.generic:
            return True
        return (
            value.base in (self.base, VariableType.AUTO)
            and value.is_array == self.is_array
            and value.is_optional == self.is_optional
        )


@dataclass(frozen=True)
class ExtensionImport:
    """Import statement requirement for an extension backend target.

    Attributes:
        value: Import module/path statement.
        alias: Optional import alias identifier.
    """

    value: str
    alias: str = ""


@dataclass(frozen=True)
class ExtensionHelper:
    """Custom helper function required by an extension implementation.

    Attributes:
        name: Name of the helper function.
        source: Source code definition of the helper.
        imports: Tuple of required `ExtensionImport` instances.
    """

    name: str
    source: str
    imports: tuple[ExtensionImport, ...] = ()


@dataclass(frozen=True)
class ExtensionTarget:
    """Target-language implementation mapping for a custom extension operation.

    Attributes:
        language: Target language identifier (`"py"`, `"js"`, `"go"`).
        emit: Inline template expression for code generation (with `{{in}}` and `{{out}}` placeholders).
        imports: Tuple of required import statements.
        helpers: Tuple of required helper function definitions.
    """

    language: Literal["py", "js", "go"] | str
    emit: str
    imports: tuple[ExtensionImport, ...] = ()
    helpers: tuple[ExtensionHelper, ...] = ()


@dataclass
class ExtensionDef:
    """Declaration of a user-defined extension operation.

    Attributes:
        namespace: Namespace group name for the extension.
        name: Operation name within the namespace.
        accept: Input type signature constraint.
        ret: Return type signature.
        targets: Dictionary mapping target language identifiers to implementation configs.
    """

    namespace: str
    name: str
    accept: ExtensionType
    ret: ExtensionType
    targets: dict[str, ExtensionTarget] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """Fully-qualified extension identifier in `Namespace.op` format."""
        return f"{self.namespace}.{self.name}"

    def resolve_return(self, input_type: TypeInfo) -> TypeInfo:
        """Resolve the return type info based on the provided input type.

        Args:
            input_type: Concrete input type info passed to this operation.

        Returns:
            Resolved return `TypeInfo` instance.
        """
        binding = input_type if self.accept.generic else None
        return self.ret.resolve(binding)


@dataclass
class ExtensionCall(Node):
    r"""Invocation node for a user-defined extension operation (`!Namespace.op`).

    Attributes:
        qualified_name: Fully qualified operation identifier (e.g. `"Utils.slugify"`).
        definition: Resolved `ExtensionDef` specification instance.

    Examples:
        - KDL: `!StringUtils.slugify`
        - Python: `v2 = re.sub(r'[\s_]+', '-', v1.lower())`
        - JavaScript: `const v2 = v1.toLowerCase().replace(/[\s_]+/g, '-');`
        - Go: `v2 := slugify(v1)`
    """

    qualified_name: str = ""
    definition: ExtensionDef | None = field(default=None, repr=False)
