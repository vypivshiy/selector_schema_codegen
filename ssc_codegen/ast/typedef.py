from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType, StructType


@dataclass
class TypeDefField(Node):
    """
    Single field type annotation.

    nested_ref — struct name when ret == NESTED.
    json_ref   — JsonDef name when ret == JSON.
    """

    name: str = ""
    ret: VariableType = field(default=VariableType.AUTO)
    nested_ref: str | None = None
    json_ref: str | None = None
    is_array: bool = False

    @property
    def typedef(self) -> "TypeDef":
        return self.parent  # type: ignore


@dataclass
class TypeDef(Node):
    """
    Type annotation generated from Struct after AST construction.
    Inserted before the corresponding Struct in Module.body.
    body: list[TypeDefField]
    """

    name: str = ""
    struct_type: StructType = StructType.ITEM

    @property
    def fields(self) -> List[TypeDefField]:
        return self.body
