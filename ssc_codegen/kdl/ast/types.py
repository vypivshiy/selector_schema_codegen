from __future__ import annotations
from enum import IntEnum, auto


class VariableType(IntEnum):
    AUTO          = auto()
    LIST_AUTO     = auto()

    DOCUMENT      = auto()
    LIST_DOCUMENT = auto()

    STRING        = auto()
    LIST_STRING   = auto()

    INT           = auto()
    LIST_INT      = auto()

    FLOAT         = auto()
    LIST_FLOAT    = auto()

    BOOL          = auto()
    NULL          = auto()
    NESTED        = auto()
    JSON          = auto()

    # helpers
    @property
    def is_list(self) -> bool:
        return self in (
            VariableType.LIST_AUTO,
            VariableType.LIST_DOCUMENT,
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
        )

    @property
    def scalar(self) -> VariableType:
        """Return scalar counterpart for list types."""
        _map = {
            VariableType.LIST_DOCUMENT: VariableType.DOCUMENT,
            VariableType.LIST_STRING:   VariableType.STRING,
            VariableType.LIST_INT:      VariableType.INT,
            VariableType.LIST_FLOAT:    VariableType.FLOAT,
            VariableType.LIST_AUTO:     VariableType.AUTO,
        }
        return _map.get(self, self)

    @property
    def as_list(self) -> VariableType:
        """Return list counterpart for scalar types."""
        _map = {
            VariableType.DOCUMENT: VariableType.LIST_DOCUMENT,
            VariableType.STRING:   VariableType.LIST_STRING,
            VariableType.INT:      VariableType.LIST_INT,
            VariableType.FLOAT:    VariableType.LIST_FLOAT,
            VariableType.AUTO:     VariableType.LIST_AUTO,
        }
        return _map.get(self, self)


class StructType(IntEnum):
    ITEM  = auto()
    LIST  = auto()
    DICT  = auto()
    TABLE = auto()
    FLAT  = auto()
