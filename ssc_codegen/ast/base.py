from __future__ import annotations
import warnings
from dataclasses import dataclass, field

from kdlquery.parser import Span

from .types import TypeInfo, VariableType


@dataclass
class Node:
    """Base abstract syntax tree node for intermediate representations.

    All AST nodes inherit from this class to participate in traversal,
    type propagation, and code generation passes.

    Attributes:
        ret_type_info: Resolved type metadata of the value returned by this node.
        accept_type_info: Resolved type metadata of the input value accepted by this node.
        is_array: Flag indicating whether the node operates in a list/array context.
        parent: Reference to the parent AST node (excluded from representation and comparison).
        body: Ordered list of child AST nodes contained within this node.
        span: Optional source code location tracking (line, column) from the KDL source.
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
        """Scalar return type shortcut.

        Warning:
            Deprecated: Use `ret_type_info.base` instead.

        Returns:
            The base `VariableType` of `ret_type_info`.
        """
        warnings.warn(
            "Node.ret is deprecated; use Node.ret_type_info.base instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.ret_type_info.base

    @property
    def accept(self) -> VariableType:
        """Scalar accepted input type shortcut.

        Warning:
            Deprecated: Use `accept_type_info.base` instead.

        Returns:
            The base `VariableType` of `accept_type_info`.
        """
        warnings.warn(
            "Node.accept is deprecated; use Node.accept_type_info.base instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.accept_type_info.base

    @property
    def type_info(self) -> TypeInfo:
        """TypeInfo alias shortcut.

        Warning:
            Deprecated: Use `ret_type_info` instead.

        Returns:
            The `ret_type_info` instance of this node.
        """
        warnings.warn(
            "Node.type_info is deprecated; use Node.ret_type_info instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.ret_type_info
