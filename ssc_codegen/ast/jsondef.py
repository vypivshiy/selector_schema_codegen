from __future__ import annotations
from dataclasses import dataclass

from .base import Node


@dataclass
class JsonDefField(Node):
    """
    Single field in a JSON mapping definition.

    type_name   — primitive ("str", "int", "float", "bool") or ref name.
    is_optional — True when field declared with ? suffix or @optional arg.
    is_array    — True when field declared with (array) prefix.
    ref_name    — set when type_name references another JsonDef.
    alias       — original JSON key when it differs from name.
    skip        — field is parsed but excluded from output TypedDict.
    may_miss    — field key may be absent from JSON (use .get() instead of []).
    doc         — documentation string for the field.
    """

    name: str = ""
    type_name: str = ""
    is_optional: bool = False
    is_array: bool = False
    ref_name: str | None = None
    alias: str = ""
    skip: bool = False
    may_miss: bool = False
    doc: str = ""


@dataclass
class JsonDef(Node):
    """
    JSON mapping definition.
    DSL: json Name { ... } / json Name array=#true { ... } / json Name path="a.b" { ... }
    body: list[JsonDefField]
    """

    name: str = ""
    is_array: bool = False
    path: str = ""
