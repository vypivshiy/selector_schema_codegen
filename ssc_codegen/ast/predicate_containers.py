from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class Filter(Node):
    """
    Filters a list, removing elements that do not match all predicates.
    Predicates in body are combined with AND by default.
    accept/ret follow the cursor list type (STRING or DOCUMENT with is_array=True).
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.STRING, is_array=True
        )
    )
    is_array: bool = True


@dataclass
class Assert(Node):
    """
    Validates the current value without modifying it.
    Raises error if any predicate fails (caught by Fallback if present).
    Pass-through: accept == ret == cursor type.
    Can appear multiple times in a pipeline.

    Source location fields (source_file/source_line/source_col) are
    populated by the parser from KdlNode.span and ctx.source_path and
    are language-agnostic — used verbatim in the default assertion
    message so consumers can find the offending .kdl line.
    """

    message: str = ""
    source_file: str = ""
    source_line: int = 0
    source_col: int = 0
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class Match(Node):
    """
    Selects a table row whose key cell (from -match pipeline) satisfies
    all predicates, then returns the value cell (from -value pipeline).
    Only valid inside Field of struct type=table.
    accept: DOCUMENT (row element), ret: STRING (value cell text).
    Predicates in body are combined with AND.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
