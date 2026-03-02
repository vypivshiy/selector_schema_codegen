from typing import Protocol, Any
import ckdl


class KdlNode(Protocol):
    name: str
    args: list[Any]
    properties: dict[str, Any]
    children: list["KdlNode"]
    type_annotation: str | None


class Document(Protocol):
    nodes: list[KdlNode]


def parse(s: str) -> Document:
    return ckdl.parse(s)  # type: ignore
