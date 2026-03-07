"""
KDL DSL linter — base infrastructure.
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Literal
from functools import wraps

from tree_sitter import Node

from ssc_codegen.kdl.linter._kdl_lang import KDL_PARSER


class DefineKind(Enum):
    SCALAR = auto()  # define FOO="value"
    BLOCK = auto()  # define FOO { ops... }


@dataclass
class DefineInfo:
    name: str
    kind: DefineKind
    value: str | None  # SCALAR value; None for BLOCK
    node: Node


@dataclass
class TransformInfo:
    """Metadata collected from a module-level 'transform' block."""
    name: str
    accept: str  # raw type string, e.g. "STRING"
    ret: str     # raw type string, e.g. "LIST_STRING"
    langs: list[str]  # language identifiers present, e.g. ["py", "js"]
    node: Node


@dataclass
class RawArg:
    """
    Positional argument with CST origin.

    is_identifier=True  — unquoted identifier in source → potential define ref
                          e.g.  css-all MY-SEL  or  re-sub RE-PAT RE-REPL
    is_identifier=False — quoted string, raw string, number, bool, null
                          e.g.  css-all ".item"  or  re-sub #"\\d+"# ""
    """

    value: str
    is_identifier: bool
    node: Node


# ── error ──────────────────────────────────────────────────────────────────────


@dataclass
class LintError:
    message: str
    hint: str
    path: str
    line: int
    col: int
    severity: Literal["error", "warning"] = "error"

    def __str__(self) -> str:
        sev = self.severity.upper()
        return (
            f"{sev}: {self.message}\n"
            f"  --> {self.path}  line {self.line}:{self.col}\n"
            f"   |\n"
            f"   | hint: {self.hint}\n"
        )

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
            "path": self.path,
            "line": self.line,
            "col": self.col,
        }


# ── context ────────────────────────────────────────────────────────────────────


@dataclass
class LintContext:
    src: bytes
    errors: list[LintError] = field(default_factory=list)
    _path: list[str] = field(default_factory=list)
    defines: dict[str, DefineInfo] = field(default_factory=dict)
    transforms: dict[str, TransformInfo] = field(default_factory=dict)
    # cache for block-define inferred (accept, ret) pairs — populated lazily
    inferred_define_types: dict[str, tuple] = field(default_factory=dict)

    # ── path ───────────────────────────────────────────────────────────────────

    @property
    def current_path(self) -> str:
        return " > ".join(self._path) if self._path else "<module>"

    def push(self, segment: str) -> None:
        self._path.append(segment)

    def pop(self) -> None:
        if self._path:
            self._path.pop()

    # ── errors ─────────────────────────────────────────────────────────────────

    def error(self, node: Node, message: str, hint: str = "") -> None:
        self.errors.append(
            LintError(
                message=message,
                hint=hint,
                path=self.current_path,
                line=node.start_point.row + 1,
                col=node.start_point.column + 1,
                severity="error",
            )
        )

    def warning(self, node: Node, message: str, hint: str = "") -> None:
        self.errors.append(
            LintError(
                message=message,
                hint=hint,
                path=self.current_path,
                line=node.start_point.row + 1,
                col=node.start_point.column + 1,
                severity="warning",
            )
        )

    # ── CST helpers ────────────────────────────────────────────────────────────

    def node_name(self, node: Node) -> str:
        """First identifier child = KDL node name."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return ""

    def get_args(self, node: Node) -> list[str]:
        """Positional args as plain strings (define refs resolved to their name)."""
        return [r.value for r in self.get_raw_args(node)]

    def get_raw_args(self, node: Node) -> list[RawArg]:
        """
        Positional args with is_identifier flag.
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
        args = self.get_args(node)
        return args[index] if index < len(args) else None

    def get_prop(self, node: Node, key: str) -> str | None:
        for child in node.children:
            if child.type == "node_field":
                for sub in child.children:
                    if sub.type == "prop":
                        k = sub.children[0].text.decode()
                        if k == key:
                            return self._extract_value(sub.children[2])
        return None

    def get_children_nodes(self, node: Node) -> list[Node]:
        for child in node.children:
            if child.type == "node_children":
                return [c for c in child.children if c.type == "node"]
        return []

    def is_define_ref(self, arg: str) -> bool:
        return arg in self.defines

    def resolve_scalar_arg(self, arg: str) -> str | None:
        info = self.defines.get(arg)
        if info is None:
            return arg
        if info.kind == DefineKind.SCALAR:
            return info.value
        return None

    # ── internal ───────────────────────────────────────────────────────────────

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
                return RawArg(
                    value=inner.text.decode(),
                    is_identifier=True,
                    node=inner,
                )
            if inner.type == "string":
                # quoted string — extract content from string_fragment
                frag = ""
                for child in inner.children:
                    if child.type == "string_fragment":
                        frag = child.text.decode()
                        break
                return RawArg(value=frag, is_identifier=False, node=inner)

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
            for child in node.children:
                if child.type == "string_fragment":
                    return child.text.decode()
            return ""
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


# ── linter ─────────────────────────────────────────────────────────────────────

RuleFn = Callable[[Node, LintContext], None]

# keywords that appear at module level — never inside field pipelines
_MODULE_KEYWORDS: frozenset[str] = frozenset(
    {
        "struct",
        "json",
        "define",
        "transform",
    }
)


class AstLinter:
    """
    Registry-based KDL DSL linter.

    Special wildcard key "*" — called for nodes with no specific rule.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[RuleFn]] = {}

    def rule(self, *node_names: str) -> Callable[..., RuleFn]:
        """Register rule(s). Use '*' for wildcard (no specific rule)."""

        def decorator(fn: RuleFn) -> RuleFn:
            @wraps(fn)
            def wrapper(node: Node, ctx: LintContext) -> None:
                fn(node, ctx)

            for name in node_names:
                self._rules.setdefault(name, []).append(wrapper)
            return wrapper

        return decorator

    def remove_rule(self, fn_name: str) -> None:
        for name in self._rules:
            self._rules[name] = [
                f for f in self._rules[name] if f.__name__ != fn_name
            ]

    def replace_rule(
        self, fn_name: str, *node_names: str
    ) -> Callable[..., RuleFn]:
        self.remove_rule(fn_name)
        return self.rule(*node_names)

    def lint(self, src: str) -> list[LintError]:
        tree = KDL_PARSER.parse(src.encode())
        ctx = LintContext(src=src.encode())
        self._collect_defines(tree.root_node, ctx)
        self._walk(tree.root_node, ctx)
        return ctx.errors

    def _collect_defines(self, root: Node, ctx: LintContext) -> None:
        """
        First pass — collect module-level defines and transforms into ctx.

        Scalar: define NAME=value  → prop child, no node_children
        Block:  define NAME { }   → first positional arg + node_children
        transform NAME accept=TYPE return=TYPE { lang { ... } ... }
        """
        for node in root.children:
            node_nm = ctx.node_name(node)
            if node_nm == "transform":
                raw_args = ctx.get_raw_args(node)
                if raw_args:
                    t_name = raw_args[0].value
                    accept_str = ctx.get_prop(node, "accept") or ""
                    ret_str = ctx.get_prop(node, "return") or ""
                    lang_nodes = ctx.get_children_nodes(node)
                    langs = [ctx.node_name(ln) for ln in lang_nodes if ctx.node_name(ln)]
                    ctx.transforms[t_name] = TransformInfo(
                        name=t_name,
                        accept=accept_str,
                        ret=ret_str,
                        langs=langs,
                        node=node,
                    )
                continue
            if node_nm != "define":
                continue

            children = ctx.get_children_nodes(node)

            if children:
                # block define: name is first positional arg
                # use get_raw_args to correctly extract the identifier
                raw_args = ctx.get_raw_args(node)
                if raw_args:
                    name = raw_args[0].value
                    ctx.defines[name] = DefineInfo(
                        name=name,
                        kind=DefineKind.BLOCK,
                        value=None,
                        node=node,
                    )
            else:
                # scalar define: iterate props
                for child in node.children:
                    if child.type != "node_field":
                        continue
                    for sub in child.children:
                        if sub.type != "prop":
                            continue
                        name = sub.children[0].text.decode()
                        value = ctx._extract_value(sub.children[2])
                        ctx.defines[name] = DefineInfo(
                            name=name,
                            kind=DefineKind.SCALAR,
                            value=value,
                            node=node,
                        )

    def _walk(
        self,
        node: Node,
        ctx: LintContext,
        _in_pipeline: bool = False,
        _in_struct_field: bool = False,
    ) -> None:
        """
        Walk the CST. _in_pipeline=True means we are inside a field pipeline
        (children of a regular field or reserved field) — ops are valid here.
        Module-level nodes and field names are not pipeline ops.

        _in_struct_field=True means the current node is a direct child of a
        struct body (i.e. a field name like 'urls' or '-split-doc').
        Its children are pipeline operations and must be walked with
        _in_pipeline=True.
        """
        if node.type != "node":
            for child in node.children:
                self._walk(child, ctx, _in_pipeline, _in_struct_field)
            return

        name = ctx.node_name(node)
        if not name:
            return

        ctx.push(name)

        # dispatch specific rules
        specific = self._rules.get(name)
        if specific:
            for fn in specific:
                fn(node, ctx)
        elif _in_pipeline:
            # no specific rule + inside pipeline → wildcard
            for fn in self._rules.get("*", []):
                fn(node, ctx)

        # Determine pipeline flag for children:
        #   - module-level keywords (struct, define, …): children are NOT ops
        #   - struct field nodes (_in_struct_field=True): children ARE ops
        #   - already inside a pipeline: stay in pipeline (unless entering a
        #     module keyword, which cannot appear inside pipelines anyway)
        if name in _MODULE_KEYWORDS:
            # struct / define / json / transform — children are fields/directives
            child_in_pipeline = False
            child_in_struct_field = name == "struct"
        elif _in_struct_field:
            # this node IS the field name; its children are pipeline ops
            child_in_pipeline = True
            child_in_struct_field = False
        else:
            # already inside a pipeline: keep propagating
            child_in_pipeline = _in_pipeline
            child_in_struct_field = False

        for child in ctx.get_children_nodes(node):
            self._walk(child, ctx, child_in_pipeline, child_in_struct_field)

        ctx.pop()


LINTER = AstLinter()
