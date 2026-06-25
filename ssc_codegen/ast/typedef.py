from __future__ import annotations
from dataclasses import dataclass

from .base import Node
from .types import StructType


@dataclass
class TypeDefField(Node):
    """Single field type annotation. Type info is in ``ret_type_info``."""

    name: str = ""

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
    def fields(self) -> list[TypeDefField]:
        return self.body
