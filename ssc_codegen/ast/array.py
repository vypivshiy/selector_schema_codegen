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
    Accepts list, returns scalar.
    """

    i: int = 0
    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class Slice(Node):
    """
    Returns sublist [start:end].
    Accepts list, returns list.
    """

    start: int = 0
    end: int = 0
    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)
    is_array: bool = True


@dataclass
class Len(Node):
    """Returns list length as INT."""

    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.INT)


@dataclass
class Unique(Node):
    """
    Removes duplicate strings from list.
    keep_order=True — preserves original order (default: False).
    STRING → STRING with is_array=True.
    """

    keep_order: bool = False
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
    is_array: bool = True
