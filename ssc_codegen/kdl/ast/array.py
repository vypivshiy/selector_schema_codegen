from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType

# Index, First, Last, Slice accept LIST_AUTO / return AUTO or LIST_AUTO.
# Concrete types are resolved by the builder from the cursor type via
# VariableType.scalar / VariableType.as_list helpers.


@dataclass
class Index(Node):
    """
    Returns element at position i.
    Negative index counts from end.
    LIST_AUTO → AUTO (resolved by builder).
    """
    i:      int          = 0
    accept: VariableType = field(default=VariableType.LIST_AUTO)
    ret:    VariableType = field(default=VariableType.AUTO)


@dataclass
class Slice(Node):
    """
    Returns sublist [start:end].
    LIST_AUTO → LIST_AUTO (resolved by builder).
    """
    start:  int          = 0
    end:    int          = 0
    accept: VariableType = field(default=VariableType.LIST_AUTO)
    ret:    VariableType = field(default=VariableType.LIST_AUTO)


@dataclass
class Len(Node):
    """Returns list length as INT."""
    accept: VariableType = field(default=VariableType.LIST_AUTO)
    ret:    VariableType = field(default=VariableType.INT)


@dataclass
class Unique(Node):
    """
    Removes duplicate strings from list.
    keep_order=True — preserves original order (default: False).
    LIST_STRING → LIST_STRING.
    """
    keep_order: bool         = False
    accept:     VariableType = field(default=VariableType.LIST_STRING)
    ret:        VariableType = field(default=VariableType.LIST_STRING)
