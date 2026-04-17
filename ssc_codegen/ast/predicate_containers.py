from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType


@dataclass
class Filter(Node):
    """
    Filters a list, removing elements that do not match all predicates.
    Predicates in body are combined with AND by default.
    accept/ret follow the cursor list type (LIST_STRING or LIST_DOCUMENT).
    """

    accept: VariableType = field(default=VariableType.LIST_STRING)
    ret: VariableType = field(default=VariableType.LIST_STRING)


@dataclass
class Assert(Node):
    """
    Validates the current value without modifying it.
    Raises error if any predicate fails (caught by Fallback if present).
    Pass-through: accept == ret == cursor type.
    Can appear multiple times in a pipeline.
    """

    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class Match(Node):
    """
    Selects a table row whose key cell (from -match pipeline) satisfies
    all predicates, then returns the value cell (from -value pipeline).
    Only valid inside Field of struct type=table.
    accept: DOCUMENT (row element), ret: STRING (value cell text).
    Predicates in body are combined with AND.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)
