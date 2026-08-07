from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum, auto


class VariableType(IntEnum):
    AUTO = auto()
    DOCUMENT = auto()
    STRING = auto()
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    NULL = auto()
    NESTED = auto()
    JSON = auto()


VT = VariableType


@dataclass(frozen=True)
class TypeInfo:
    """Unified type information container.

    Stores base type + modifiers (array, optional) + ref name + JSON hints.
    Target-language rendering (suffixes, wrappers) is done by converters, not here.
    """

    base: VariableType  # STRING, INT, FLOAT, BOOL, NULL, NESTED, JSON, DOCUMENT, AUTO
    is_array: bool = False
    is_optional: bool = False
    ref: str | None = None  # raw struct/JsonDef name — converter adds suffix
    omitempty: bool = False  # @omitempty — key may be absent from JSON
    skip: bool = False  # @skip — field parsed but excluded from output

    @property
    def is_list(self) -> bool:
        return self.is_array

    @property
    def is_ref(self) -> bool:
        return self.base in (VT.NESTED, VT.JSON) and self.ref is not None


class StructType(IntEnum):
    ITEM = auto()
    LIST = auto()
    DICT = auto()
    TABLE = auto()
    FLAT = auto()
    REST = auto()
    RAW = auto()
