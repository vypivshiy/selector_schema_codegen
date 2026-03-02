from __future__ import annotations
from dataclasses import dataclass

from .base import Node


@dataclass
class JsonDefField(Node):
    """
    Single field in a JSON mapping definition.

    type_name   — primitive ("str", "int", "float", "bool") or ref name.
    is_optional — True when field declared with ? suffix (value | null).
    is_array    — True when field declared with {} suffix.
    ref_name    — set when type_name references another JsonDef.
    """

    name: str = ""
    type_name: str = ""
    is_optional: bool = False
    is_array: bool = False
    ref_name: str | None = None


@dataclass
class JsonDef(Node):
    """
    JSON mapping definition.
    DSL: json Name { ... } / json Name array=#true { ... }
    body: list[JsonDefField]
    """

    name: str = ""
    is_array: bool = False
