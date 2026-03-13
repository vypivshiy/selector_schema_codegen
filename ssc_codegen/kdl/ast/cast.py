from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType


@dataclass
class ToInt(Node):
    """
    Casts string(s) to integer(s).
    STRING → INT, LIST_STRING → LIST_INT.
    accept/ret set by builder from cursor type.
    """

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.INT)


@dataclass
class ToFloat(Node):
    """
    Casts string(s) to float(s).
    STRING → FLOAT, LIST_STRING → LIST_FLOAT.
    accept/ret set by builder from cursor type.
    """

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.FLOAT)


@dataclass
class ToBool(Node):
    """
    Casts any scalar to bool.
    AUTO → BOOL.
    """

    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.BOOL)


@dataclass
class Jsonify(Node):
    """
    Deserializes a JSON string using a named json mapping definition.
    Optional path extracts a nested value by dotted key e.g. "0.text".
    STRING → JSON.

    is_array: True when the result is a JSON array (e.g., Quote without index).
              False when accessing a single item (e.g., Quote[0] or Quote[0].field).
    """

    schema_name: str = ""
    path: str | None = None
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.JSON)
    is_array: bool = False


@dataclass
class Nested(Node):
    """
    Passes current document to another struct parser and returns its result.
    Target struct can be of any type.
    DOCUMENT → NESTED.
    """

    struct_name: str = ""
    is_array: bool = False
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.NESTED)
