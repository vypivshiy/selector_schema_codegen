"""KdlNode adapter — adapts KdlNode to the protocol used by handler functions."""

from __future__ import annotations

from ssc_codegen.kdl import KdlNode


class NodeAdapter:
    """Adapts KdlNode to the old TsKdlNode protocol used by handler functions."""

    __slots__ = ("name", "args", "properties", "children", "type_annotation")

    def __init__(self, kn: KdlNode) -> None:
        self.name = kn.name
        self.args = [a.value for a in kn.args]
        self.properties = {k: v.value for k, v in kn.properties.items()}
        self.children = kn.children
        self.type_annotation = kn.type_annotation

    def __repr__(self) -> str:
        return f"<NodeAdapter {self.name!r}>"


def adapt(node: KdlNode) -> NodeAdapter:
    return NodeAdapter(node)
