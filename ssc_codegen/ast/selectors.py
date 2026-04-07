from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType


@dataclass
class CssSelect(Node):
    query: str = ""
    queries: list[str] = field(default_factory=list)
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class CssSelectAll(Node):
    query: str = ""
    queries: list[str] = field(default_factory=list)
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class XpathSelect(Node):
    query: str = ""
    queries: list[str] = field(default_factory=list)
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class XpathSelectAll(Node):
    query: str = ""
    queries: list[str] = field(default_factory=list)
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class CssRemove(Node):
    """Removes matched elements from document in-place, passes document forward."""

    query: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class XpathRemove(Node):
    """Removes matched elements from document in-place, passes document forward."""

    query: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)
