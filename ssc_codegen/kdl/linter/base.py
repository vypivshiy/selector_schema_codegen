"""
KDL DSL linter — base infrastructure.

Usage:
    from ssc_codegen.kdl.linter.base import LINTER

    errors = LINTER.lint(kdl_source)
    for e in errors:
        print(e)

Adding a rule:
    @LINTER.rule("css", "css-all")
    def _(node: KdlNode, ctx: LintContext) -> None:
        if not ctx.get_arg(node, 0):
            ctx.error(node, "requires a query argument", "example: css \".cls\"")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal
from functools import wraps

from tree_sitter import Node

from ssc_codegen.kdl.linter._kdl_lang import KDL_PARSER


# ── error ──────────────────────────────────────────────────────────────────────

@dataclass
class LintError:
    message:  str
    hint:     str
    path:     str                              # "struct Demo > field title"
    line:     int                              # 1-based
    col:      int                              # 1-based
    severity: Literal["error", "warning"] = "error"

    def __str__(self) -> str:
        sev = self.severity.upper()
        return (
            f"{sev}: {self.message}\n"
            f"  --> {self.path}  line {self.line}:{self.col}\n"
            f"   |\n"
            f"   | hint: {self.hint}\n"
        )


# ── context ────────────────────────────────────────────────────────────────────

@dataclass
class LintContext:
    src:    bytes
    errors: list[LintError] = field(default_factory=list)
    _path:  list[str]       = field(default_factory=list)

    # ── path tracking ──────────────────────────────────────────────────────────

    @property
    def current_path(self) -> str:
        return " > ".join(self._path) if self._path else "<module>"

    def push(self, segment: str) -> None:
        self._path.append(segment)

    def pop(self) -> None:
        if self._path:
            self._path.pop()

    # ── error reporting ────────────────────────────────────────────────────────

    def error(self, node: Node, message: str, hint: str = "") -> None:
        self.errors.append(LintError(
            message=message,
            hint=hint,
            path=self.current_path,
            line=node.start_point.row + 1,
            col=node.start_point.column + 1,
            severity="error",
        ))

    def warning(self, node: Node, message: str, hint: str = "") -> None:
        self.errors.append(LintError(
            message=message,
            hint=hint,
            path=self.current_path,
            line=node.start_point.row + 1,
            col=node.start_point.column + 1,
            severity="warning",
        ))

    # ── CST helpers ────────────────────────────────────────────────────────────

    def node_name(self, node: Node) -> str:
        """Extract KDL node name (first identifier child)."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return ""

    def get_args(self, node: Node) -> list[str]:
        """Get all positional arguments of a KDL node (non-property node_fields)."""
        args = []
        for child in node.children:
            if child.type == "node_field":
                # property has a 'prop' child; plain arg does not
                if not any(c.type == "prop" for c in child.children):
                    args.append(self._extract_value(child))
        return args

    def get_arg(self, node: Node, index: int) -> str | None:
        """Get positional argument by index, None if missing."""
        args = self.get_args(node)
        return args[index] if index < len(args) else None

    def get_prop(self, node: Node, key: str) -> str | None:
        """Get property value by name."""
        for child in node.children:
            if child.type == "node_field":
                for sub in child.children:
                    if sub.type == "prop":
                        k = sub.children[0].text.decode()
                        if k == key:
                            return self._extract_value(sub.children[2])
        return None

    def get_children_nodes(self, node: Node) -> list[Node]:
        """Get child KDL nodes from node_children block."""
        for child in node.children:
            if child.type == "node_children":
                return [c for c in child.children if c.type == "node"]
        return []

    def _extract_value(self, node: Node) -> str:
        """Recursively extract text value from value/identifier/string nodes."""
        if node.type == "string":
            for child in node.children:
                if child.type == "string_fragment":
                    return child.text.decode()
            return ""
        if node.type in ("value", "identifier", "prop"):
            for child in node.children:
                result = self._extract_value(child)
                if result:
                    return result
        return node.text.decode()


# ── linter ─────────────────────────────────────────────────────────────────────

RuleFn = Callable[[Node, LintContext], None]


class AstLinter:
    """
    Registry-based KDL DSL linter.

    Rules are registered per KDL node name via @LINTER.rule(...).
    The linter walks the full CST and dispatches to matching rules.

    Two-pass walk:
      pass 1 — module-level nodes (struct, json, define, transform)
      pass 2 — inside each struct: reserved fields, regular fields, pipeline ops

    Each rule receives the raw tree-sitter Node and LintContext.
    LintContext.push/pop manages the path stack for error messages.
    """

    def __init__(self) -> None:
        # dict[node_name, list[RuleFn]] — multiple handlers per node
        self._rules: dict[str, list[RuleFn]] = {}

    def rule(self, *node_names: str) -> Callable[..., RuleFn]:
        """Register a rule for one or more KDL node names. Multiple rules per node are allowed."""
        def decorator(fn: RuleFn) -> RuleFn:
            @wraps(fn)
            def wrapper(node: Node, ctx: LintContext) -> None:
                fn(node, ctx)

            for name in node_names:
                self._rules.setdefault(name, []).append(wrapper)
            return wrapper
        return decorator

    def remove_rule(self, fn_name: str) -> None:
        """Remove a rule by function name across all node registrations."""
        for name in self._rules:
            self._rules[name] = [
                f for f in self._rules[name]
                if f.__name__ != fn_name
            ]

    def lint(self, src: str) -> list[LintError]:
        tree = KDL_PARSER.parse(src.encode())
        ctx = LintContext(src=src.encode())
        self._walk(tree.root_node, ctx)
        return ctx.errors

    def replace_rule(self, fn_name: str, *node_names: str) -> Callable[..., RuleFn]:
        """Remove existing rule by name and register new one in its place."""
        self.remove_rule(fn_name)
        return self.rule(*node_names)

    def _walk(self, node: Node, ctx: LintContext) -> None:
        if node.type == "node":
            name = ctx.node_name(node)
            if name:
                ctx.push(name)
                # dispatch all registered handlers for this node name
                for fn in self._rules.get(name, []):
                    fn(node, ctx)
                for child in ctx.get_children_nodes(node):
                    self._walk(child, ctx)
                ctx.pop()
            return
        for child in node.children:
            self._walk(child, ctx)


LINTER = AstLinter()