from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class CssSelect(Node):
    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )

    @property
    def query(self):  # deprecated
        return self.queries[0]


@dataclass
class CssSelectAll(Node):
    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )
    is_array: bool = True

    @property
    def query(self):  # deprecated
        return self.queries[0]


@dataclass
class XpathSelect(Node):
    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )

    @property
    def query(self):  # deprecated
        return self.queries[0]


@dataclass
class XpathSelectAll(Node):
    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )
    is_array: bool = True

    @property
    def query(self):  # deprecated
        return self.queries[0]


@dataclass
class CssRemove(Node):
    """Removes matched elements from document in-place, passes document forward."""

    query: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )


@dataclass
class XpathRemove(Node):
    """Removes matched elements from document in-place, passes document forward."""

    query: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
