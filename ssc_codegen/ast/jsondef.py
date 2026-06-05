from __future__ import annotations
from dataclasses import dataclass

from .base import Node


@dataclass
class JsonDefField(Node):
    """
    Single field in a JSON mapping definition.

    Type metadata is in ``type_info`` (base, is_array, is_optional, ref, omitempty, skip).
    """

    name: str = ""
    type_name: str = ""
    alias: str = ""
    doc: str = ""


@dataclass
class JsonDef(Node):
    """
    JSON mapping definition.
    DSL: json Name { ... } / (array)json Name { ... } / json Name path="a.b" { ... }
    body: list[JsonDefField]
    """

    name: str = ""
    is_array: bool = False
    path: str = ""
