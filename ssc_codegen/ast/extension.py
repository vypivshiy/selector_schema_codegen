from __future__ import annotations

from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass(frozen=True)
class ExtensionType:
    """Type pattern used by an extension operation signature."""

    base: VariableType | None = None
    generic: str | None = None
    is_array: bool = False
    is_optional: bool = False

    def resolve(self, binding: TypeInfo | None = None) -> TypeInfo:
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
        if self.generic:
            return True
        return (
            value.base in (self.base, VariableType.AUTO)
            and value.is_array == self.is_array
            and value.is_optional == self.is_optional
        )


@dataclass(frozen=True)
class ExtensionImport:
    value: str
    alias: str = ""


@dataclass(frozen=True)
class ExtensionHelper:
    name: str
    source: str
    imports: tuple[ExtensionImport, ...] = ()


@dataclass(frozen=True)
class ExtensionTarget:
    language: str
    emit: str
    imports: tuple[ExtensionImport, ...] = ()
    helpers: tuple[ExtensionHelper, ...] = ()


@dataclass
class ExtensionDef:
    namespace: str
    name: str
    accept: ExtensionType
    ret: ExtensionType
    targets: dict[str, ExtensionTarget] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}"

    def resolve_return(self, input_type: TypeInfo) -> TypeInfo:
        binding = input_type if self.accept.generic else None
        return self.ret.resolve(binding)


@dataclass
class ExtensionCall(Node):
    qualified_name: str = ""
    definition: ExtensionDef | None = field(default=None, repr=False)
