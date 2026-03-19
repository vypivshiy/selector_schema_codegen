"""CST navigation utilities"""

from __future__ import annotations

import re

from tree_sitter import Node

from ssc_codegen.kdl.linter.types import RawArg

# KDL 2.0 raw string: #"content"#, ##"content"##, etc.
# Tree-sitter KDL grammar may not recognize these natively,
# so they appear as identifier > string nodes.
_RAW_STRING_RE = re.compile(r'^(#+)"(.*?)"\1$', re.DOTALL)


class NodeNavigator:
    """Утилиты для навигации по CST дереву"""

    def __init__(self, src: bytes):
        self.src = src

    def node_name(self, node: Node) -> str:
        """Имя узла (первый идентификатор)"""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return ""

    def get_args(self, node: Node) -> list[str]:
        """Получить аргументы как строки (define refs resolved to their name)"""
        return [r.value for r in self.get_raw_args(node)]

    def get_raw_args(self, node: Node) -> list[RawArg]:
        """
        Получить аргументы с типами.
        Skips properties (key=value pairs).
        """
        result = []
        for child in node.children:
            if child.type != "node_field":
                continue
            if any(c.type == "prop" for c in child.children):
                continue  # skip properties
            raw = self._extract_raw_arg(child)
            if raw is not None:
                result.append(raw)
        return result

    def get_arg(self, node: Node, index: int) -> str | None:
        """Получить аргумент по индексу"""
        args = self.get_args(node)
        return args[index] if index < len(args) else None

    def get_prop(self, node: Node, key: str) -> str | None:
        """Получить property значение"""
        for child in node.children:
            if child.type == "node_field":
                for sub in child.children:
                    if sub.type == "prop":
                        k = sub.children[0].text.decode()
                        if k == key:
                            return self._extract_value(sub.children[2])
        return None

    def get_children_nodes(self, node: Node) -> list[Node]:
        """Получить child nodes"""
        for child in node.children:
            if child.type == "node_children":
                return [c for c in child.children if c.type == "node"]
        return []

    def has_empty_block(self, node: Node) -> bool:
        """Проверить пустой ли блок (node_children with no child nodes)"""
        for child in node.children:
            if child.type == "node_children":
                # Has node_children, check if it's empty
                return not any(c.type == "node" for c in child.children)
        return False

    def has_single_line_op(self, node: Node, op_name: str) -> bool:
        """Проверить есть ли single-line операция (не wrapped in node)"""
        for child in node.children:
            if child.type == "node_children":
                # Look for identifier matching op_name as direct child
                identifiers = [
                    c for c in child.children if c.type == "identifier"
                ]
                return (
                    len(identifiers) == 1
                    and identifiers[0].text.decode() == op_name
                )
        return False

    def get_bare_op_container(self, node: Node) -> Node | None:
        """
        Return the node_children element if it contains a bare (unwrapped) trailing op.

        In KDL 2.0, the last node in a children block without a `;` terminator
        is represented by tree-sitter as bare identifier + node_field children
        directly inside node_children, NOT wrapped in a `node` element.

        Returns the node_children node itself (usable as a virtual node for
        node_name/get_args), or None if no bare op exists.
        """
        for child in node.children:
            if child.type == "node_children":
                has_bare_ident = any(
                    c.type == "identifier" for c in child.children
                )
                if has_bare_ident:
                    return child
        return None

    # ── private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_string_content(string_node: Node) -> str:
        """
        Reconstruct the full string value from a 'string' CST node,
        concatenating string_fragment and escape children.
        """
        _ESCAPE_MAP = {
            '\\"': '"', "\\\\": "\\", "\\n": "\n", "\\r": "\r",
            "\\t": "\t", "\\b": "\b", "\\f": "\f", "\\/": "/",
        }
        parts: list[str] = []
        for child in string_node.children:
            if child.type == "string_fragment":
                parts.append(child.text.decode())
            elif child.type == "escape":
                esc = child.text.decode()
                parts.append(_ESCAPE_MAP.get(esc, esc))
        return "".join(parts)

    def _extract_raw_arg(self, node_field: Node) -> RawArg | None:
        """
        Extract RawArg from a node_field.

        CST layout for a positional arg:
          node_field
            value
              identifier   ← unquoted   → is_identifier=True
              string       ← quoted     → is_identifier=False
              raw_string   ← #"..."#    → is_identifier=False
              number/bool  ← literal    → is_identifier=False
              type + ...   ← annotated  → skip annotation, read inner value
        """
        for val_node in node_field.children:
            if val_node.type != "value":
                continue
            return self._classify_value_node(val_node)
        return None

    def _classify_value_node(self, val_node: Node) -> RawArg:
        """Classify a 'value' CST node into a RawArg."""
        for inner in val_node.children:
            # skip type annotation  (type)value
            if inner.type == "type":
                continue

            if inner.type == "identifier":
                # The grammar wraps quoted strings as identifier > string.
                # Quoted strings have string_fragment children; raw strings
                # (#"..."#) have a string child with 0 children — skip those.
                for sub in inner.children:
                    if sub.type == "string" and sub.child_count > 0:
                        return RawArg(
                            value=self._extract_string_content(sub),
                            is_identifier=False,
                            node=inner,
                        )

                text = inner.text.decode()
                # KDL 2.0 raw strings (#"..."#) may be parsed as
                # identifier > string by tree-sitter grammars without
                # native raw_string support.
                m = _RAW_STRING_RE.match(text)
                if m:
                    return RawArg(
                        value=m.group(2),
                        is_identifier=False,
                        node=inner,
                    )
                # True bare identifier (unquoted)
                return RawArg(
                    value=text,
                    is_identifier=True,
                    node=inner,
                )
            if inner.type == "string":
                # quoted string — extract full content with escapes
                return RawArg(
                    value=self._extract_string_content(inner),
                    is_identifier=False,
                    node=inner,
                )

            if inner.type == "raw_string":
                # raw string #"..."# — extract content
                frag = ""
                for child in inner.children:
                    if child.type == "raw_string_content":
                        frag = child.text.decode()
                        break
                return RawArg(value=frag, is_identifier=False, node=inner)

            # number, bool (#true/#false), #null
            return RawArg(
                value=inner.text.decode(),
                is_identifier=False,
                node=inner,
            )

        # empty value node (shouldn't happen, but be safe)
        return RawArg(
            value=val_node.text.decode(), is_identifier=False, node=val_node
        )

    def _extract_value(self, node: Node) -> str:
        """Recursively extract text value (used for props and non-raw-arg contexts)."""
        if node.type == "string":
            return self._extract_string_content(node)
        if node.type == "raw_string":
            for child in node.children:
                if child.type == "raw_string_content":
                    return child.text.decode()
            return ""
        if node.type in ("value", "identifier", "prop"):
            for child in node.children:
                result = self._extract_value(child)
                if result:
                    return result
        return node.text.decode()
