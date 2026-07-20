from __future__ import annotations
from dataclasses import dataclass, field

from kdlquery.parser import Span

from .types import TypeInfo, VariableType


@dataclass
class Node:
    """
    Base AST node.

    Canonical type metadata:
        ret_type_info    — resolved type of the value this node RETURNS.
        accept_type_info — resolved type this node ACCEPTS as input.
    is_array           — list context flag for pipeline expression nodes
                         (kept in sync with ret_type_info.is_array by the builder).
    parent             — back-reference, excluded from repr to avoid cycles.
    body               — child nodes (pipeline body, struct body, etc.).
    span               — optional source location carried from KdlNode.span.
                         Populated lazily by parsers that need position info
                         in codegen (Assert, Re). None for nodes that never
                         use source location.

    The scalar ``accept`` / ``ret`` views and the legacy ``type_info`` name are
    exposed as read-only backport properties derived from the TypeInfo fields.
    """

    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    is_array: bool = False
    parent: Node | None = field(default=None, repr=False)
    body: list[Node] = field(default_factory=list)
    span: Span | None = field(default=None, repr=False, compare=False)

    # ── backport properties (deprecated: prefer the TypeInfo fields) ───────────
    @property
    def ret(self) -> VariableType:
        return self.ret_type_info.base

    @property
    def accept(self) -> VariableType:
        return self.accept_type_info.base

    @property
    def type_info(self) -> TypeInfo:
        return self.ret_type_info
