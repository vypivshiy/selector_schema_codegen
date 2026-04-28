from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from .parser import Span
from .reader import (
    KdlNode,
    ReadDiagnostic,
    Reader,
    WalkContext,
)


class Node(TypedDict):
    name: str
    args: tuple[Any, ...]
    props: dict[str, Any]
    child: list[Node]


class DictReader(Reader[Node, list[Node]]):
    def on_node(
        self,
        name: str,
        args: tuple[tuple[Any, Span], ...],
        properties: Mapping[str, tuple[Any, Span]],
        children: tuple[KdlNode, ...],
        ctx: WalkContext[Node],
    ) -> Node:
        child_nodes = ctx.walk_children()
        return Node(
            name=name,
            args=tuple(v for v, _ in args),
            props={k: v for k, (v, _) in properties.items()},
            child=child_nodes,
        )

    def error_node(
        self,
        message: str,
        ctx: WalkContext[Node],
    ) -> Node:
        return Node(
            name=ctx.node.name,
            args=(),
            props={},
            child=[],
        )

    def finalize(
        self,
        nodes: list[Node],
        diagnostics: list[ReadDiagnostic],
    ) -> list[Node]:
        return nodes
