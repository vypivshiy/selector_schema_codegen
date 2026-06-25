from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class ToInt(Node):
    """
    Casts string(s) to integer(s).
    STRING → INT, LIST_STRING → LIST_INT.
    accept/ret set by builder from cursor type.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.INT)
    )


@dataclass
class ToFloat(Node):
    """
    Casts string(s) to float(s).
    STRING → FLOAT, LIST_STRING → LIST_FLOAT.
    accept/ret set by builder from cursor type.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.FLOAT)
    )


@dataclass
class ToBool(Node):
    """
    Casts any scalar to bool.
    AUTO → BOOL.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.BOOL)
    )


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
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.JSON)
    )
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
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.NESTED)
    )
