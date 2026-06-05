from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .types import TypeInfo, VariableType

if TYPE_CHECKING:
    pass


@dataclass
class Node:
    """
    Base AST node.

    accept / ret  — pipeline type contract, resolved at AST build time.
    is_array      — list context flag for pipeline expression nodes.
    type_info     — resolved type metadata (base, optional, array, ref).
    parent        — back-reference, excluded from repr to avoid cycles.
    body          — child nodes (pipeline body, struct body, etc.).
    """

    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)
    is_array: bool = False
    type_info: TypeInfo | None = None
    parent: Node | None = field(default=None, repr=False)
    body: list[Node] = field(default_factory=list)
