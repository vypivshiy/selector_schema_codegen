"""Pure-Python KDL 2.0 parser backend with a tree-sitter-like Node API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ssc_codegen.kdl.parser import (
    CSTArgEntry,
    CSTDocument,
    CSTIdentifier,
    CSTNode,
    CSTPropEntry,
    CSTValue,
    KDL2CSTParser,
)


@dataclass(frozen=True)
class Point:
    row: int
    column: int


@dataclass
class Node:
    type: str
    start_byte: int
    end_byte: int
    start_point: Point
    end_point: Point
    _source: str
    _children: list["Node"] = field(default_factory=list)
    _field_names: list[str | None] = field(default_factory=list)
    parent: "Node | None" = None
    is_named: bool = True
    is_missing: bool = False

    @property
    def children(self) -> list["Node"]:
        return self._children

    @property
    def child_count(self) -> int:
        return len(self._children)

    @property
    def has_error(self) -> bool:
        if self.type == "ERROR":
            return True
        return any(ch.has_error for ch in self._children)

    @property
    def text(self) -> bytes:
        return self._source[self.start_byte : self.end_byte].encode("utf-8")

    def field_name_for_child(self, index: int) -> str | None:
        if 0 <= index < len(self._field_names):
            return self._field_names[index]
        return None

    def child_by_field_name(self, name: str) -> "Node | None":
        for child, field_name in zip(
            self._children, self._field_names, strict=False
        ):
            if field_name == name:
                return child
        return None

    def children_by_field_name(self, name: str) -> list["Node"]:
        out: list[Node] = []
        for child, field_name in zip(
            self._children, self._field_names, strict=False
        ):
            if field_name == name:
                out.append(child)
        return out


@dataclass
class Tree:
    root_node: Node


class _KDLParserAdapter:
    def __init__(self) -> None:
        self._parser = KDL2CSTParser()

    def parse(self, src: bytes) -> Tree:
        text = src.decode("utf-8")
        cst_doc = self._parser.parse(text)
        root = _build_document_node(cst_doc, text)
        return Tree(root_node=root)


def _to_point(line: int, col: int) -> Point:
    return Point(row=max(0, line - 1), column=max(0, col - 1))


def _node(
    node_type: str,
    start: int,
    end: int,
    sp: Point,
    ep: Point,
    source: str,
    children: list[Node] | None = None,
    field_names: list[str | None] | None = None,
    is_named: bool = True,
) -> Node:
    n = Node(
        type=node_type,
        start_byte=start,
        end_byte=end,
        start_point=sp,
        end_point=ep,
        _source=source,
        _children=children or [],
        _field_names=field_names or [],
        is_named=is_named,
    )
    for child in n._children:
        child.parent = n
    return n


def _build_document_node(doc: CSTDocument, src: str) -> Node:
    children = [_build_kdl_node(n, src) for n in doc.nodes]
    return _node(
        "document",
        doc.span.start.offset,
        doc.span.end.offset,
        _to_point(doc.span.start.line, doc.span.start.column),
        _to_point(doc.span.end.line, doc.span.end.column),
        src,
        children=children,
        field_names=["node"] * len(children),
    )


def _build_identifier_node(ident: CSTIdentifier, src: str) -> Node:
    return _node(
        "identifier",
        ident.span.start.offset,
        ident.span.end.offset,
        _to_point(ident.span.start.line, ident.span.start.column),
        _to_point(ident.span.end.line, ident.span.end.column),
        src,
    )


def _typed_value_raw(value: CSTValue) -> tuple[str | None, str]:
    if value.type_annotation is None:
        return None, value.raw
    ann = value.type_annotation.raw
    if value.raw.startswith(ann):
        return ann, value.raw[len(ann) :]
    return ann, value.raw


def _build_value_node(item: CSTValue | CSTIdentifier, src: str) -> Node:
    if isinstance(item, CSTIdentifier):
        inner = _build_identifier_node(item, src)
        return _node(
            "value",
            item.span.start.offset,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
            children=[inner],
            field_names=["value"],
        )

    type_raw, literal_raw = _typed_value_raw(item)
    children: list[Node] = []
    fields: list[str | None] = []

    if type_raw is not None and item.type_annotation is not None:
        ty = _node(
            "type",
            item.type_annotation.span.start.offset,
            item.type_annotation.span.end.offset,
            _to_point(
                item.type_annotation.span.start.line,
                item.type_annotation.span.start.column,
            ),
            _to_point(
                item.type_annotation.span.end.line,
                item.type_annotation.span.end.column,
            ),
            src,
        )
        children.append(ty)
        fields.append("type")

    if item.type_annotation is not None:
        lit_start = item.type_annotation.span.end.offset
    else:
        lit_start = item.span.start.offset

    # Keep compatibility with existing navigator expectations:
    # quoted strings are represented as identifier -> string(string_fragment)
    if literal_raw.startswith('"') and literal_raw.endswith('"'):
        string_frag = _node(
            "string_fragment",
            lit_start + 1,
            item.span.end.offset - 1,
            _to_point(item.span.start.line, item.span.start.column + 1),
            _to_point(item.span.end.line, max(1, item.span.end.column - 1)),
            src,
        )
        string_node = _node(
            "string",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
            children=[string_frag],
            field_names=["fragment"],
        )
        inner = _node(
            "identifier",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
            children=[string_node],
        )
    elif (
        literal_raw.startswith("#")
        and '"' in literal_raw
        and literal_raw.endswith("#")
    ):
        inner = _node(
            "identifier",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
        )
    elif literal_raw in {"#true", "#false", "#null", "#inf", "#-inf", "#nan"}:
        inner = _node(
            "keyword",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
        )
    elif _looks_number_literal(literal_raw):
        inner = _node(
            "number",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
        )
    else:
        inner = _node(
            "identifier",
            lit_start,
            item.span.end.offset,
            _to_point(item.span.start.line, item.span.start.column),
            _to_point(item.span.end.line, item.span.end.column),
            src,
        )

    children.append(inner)
    fields.append("value")

    return _node(
        "value",
        item.span.start.offset,
        item.span.end.offset,
        _to_point(item.span.start.line, item.span.start.column),
        _to_point(item.span.end.line, item.span.end.column),
        src,
        children=children,
        field_names=fields,
    )


def _build_prop_field(entry: CSTPropEntry, src: str) -> Node:
    key = _build_identifier_node(entry.key, src)
    val = _build_value_node(entry.value, src)
    eq = _node(
        "=",
        entry.key.span.end.offset,
        entry.key.span.end.offset + 1,
        key.end_point,
        key.end_point,
        src,
        is_named=False,
    )
    prop = _node(
        "prop",
        entry.span.start.offset,
        entry.span.end.offset,
        _to_point(entry.span.start.line, entry.span.start.column),
        _to_point(entry.span.end.line, entry.span.end.column),
        src,
        children=[key, eq, val],
        field_names=["key", None, "value"],
    )
    return _node(
        "node_field",
        entry.span.start.offset,
        entry.span.end.offset,
        _to_point(entry.span.start.line, entry.span.start.column),
        _to_point(entry.span.end.line, entry.span.end.column),
        src,
        children=[prop],
        field_names=["property"],
    )


def _build_arg_field(entry: CSTArgEntry, src: str) -> Node:
    val = _build_value_node(entry.value, src)
    return _node(
        "node_field",
        entry.span.start.offset,
        entry.span.end.offset,
        _to_point(entry.span.start.line, entry.span.start.column),
        _to_point(entry.span.end.line, entry.span.end.column),
        src,
        children=[val],
        field_names=["argument"],
    )


def _build_kdl_node(node: CSTNode, src: str) -> Node:
    children: list[Node] = []
    fields: list[str | None] = []

    if node.type_annotation is not None:
        ty = _node(
            "type",
            node.type_annotation.span.start.offset,
            node.type_annotation.span.end.offset,
            _to_point(
                node.type_annotation.span.start.line,
                node.type_annotation.span.start.column,
            ),
            _to_point(
                node.type_annotation.span.end.line,
                node.type_annotation.span.end.column,
            ),
            src,
        )
        children.append(ty)
        fields.append("type")

    children.append(_build_identifier_node(node.name, src))
    fields.append("name")

    for entry in node.entries:
        if isinstance(entry, CSTPropEntry):
            nf = _build_prop_field(entry, src)
        else:
            nf = _build_arg_field(entry, src)
        children.append(nf)
        fields.append(None)

    if node.has_children_block:
        child_nodes = [_build_kdl_node(ch, src) for ch in node.children]
        if node.children_block_span is not None:
            ch_start_off = node.children_block_span.start.offset
            ch_end_off = node.children_block_span.end.offset
            ch_start = _to_point(
                node.children_block_span.start.line,
                node.children_block_span.start.column,
            )
            ch_end = _to_point(
                node.children_block_span.end.line,
                node.children_block_span.end.column,
            )
        elif child_nodes:
            ch_start_off = node.children[0].span.start.offset
            ch_end_off = node.children[-1].span.end.offset
            ch_start = _to_point(
                node.children[0].span.start.line,
                node.children[0].span.start.column,
            )
            ch_end = _to_point(
                node.children[-1].span.end.line,
                node.children[-1].span.end.column,
            )
        else:
            ch_start_off = node.span.end.offset
            ch_end_off = node.span.end.offset
            ch_start = _to_point(node.span.end.line, node.span.end.column)
            ch_end = _to_point(node.span.end.line, node.span.end.column)
        ch_block = _node(
            "node_children",
            ch_start_off,
            ch_end_off,
            ch_start,
            ch_end,
            src,
            children=child_nodes,
            field_names=["node"] * len(child_nodes),
        )
        children.append(ch_block)
        fields.append("children")

    return _node(
        "node",
        node.span.start.offset,
        node.span.end.offset,
        _to_point(node.span.start.line, node.span.start.column),
        _to_point(node.span.end.line, node.span.end.column),
        src,
        children=children,
        field_names=fields,
    )


def _looks_number_literal(raw: str) -> bool:
    if not raw:
        return False
    if raw[0] in "+-":
        raw = raw[1:]
    if raw.startswith(("0x", "0o", "0b")):
        return True
    return any(ch.isdigit() for ch in raw)


KDL_PARSER = _KDLParserAdapter()

__all__ = ["KDL_PARSER", "Node", "Point", "Tree"]
