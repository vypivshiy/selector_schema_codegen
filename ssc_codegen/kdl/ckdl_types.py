from typing import Protocol, Any
import ckdl

class Node(Protocol):
    name: str
    args: list[Any]
    properties: dict[str, Any]
    children: list["Node"]
    type_annotation: str | None


class Document(Protocol):
    nodes: list[Node]


def parse(s: str) -> Document:
    return ckdl.parse(s)  # type: ignore
