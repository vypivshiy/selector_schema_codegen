from dataclasses import dataclass, replace
from typing import Callable, Type, TYPE_CHECKING

from ssc_codegen.kdl.ast import Node
from ssc_codegen.kdl.ast import Filter, Assert, Match
from ssc_codegen.kdl.ast import LogicNot, LogicAnd, LogicOr
from ssc_codegen.kdl.ast import JsonDef, TypeDef, Struct, Init
from ssc_codegen.kdl.ast import PreValidate, Field, InitField, SplitDoc, Key, Value, TableConfig, TableMatchKey, TableRow

if TYPE_CHECKING:
    from ssc_codegen.kdl.ast import Module


@dataclass
class ConverterContext:
    index: int = 0
    depth: int = 0
    var_name: str = "v"
    indent_char: str = " " * 4

    @property
    def prv(self) -> str:
        return (
            self.var_name if self.index == 0 else f"{self.var_name}{self.index}"
        )

    @property
    def nxt(self) -> str:
        return f"{self.var_name}{self.index + 1}"

    @property
    def indent(self) -> str:
        return self.indent_char * self.depth

    def advance(self) -> "ConverterContext":
        return replace(self, index=self.index + 1)

    def deeper(self) -> "ConverterContext":
        return replace(self, depth=self.depth + 1)


CallbackNode = Callable[[Node, ConverterContext], list[str] | str]

# Nodes whose body contains other container/field nodes.
# Traversal goes deeper (depth+1), index resets to 0.
_CONTAINER_NODES = (JsonDef, TypeDef, Struct, Init)

_PIPELINE_NODES = (
    Field,
    InitField,
    PreValidate,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableMatchKey,
    TableRow,
)

# Nodes whose body contains predicate ops.
# Traversal keeps same ctx — no depth or index change.
_PREDICATE_NODES = (Filter, Assert, Match, LogicNot, LogicAnd, LogicOr)


class BaseConverter:
    def __init__(self, *, var_name: str = "v", indent: str = " " * 4) -> None:
        self._pre_callbacks: dict[Type[Node], CallbackNode] = {}
        self._post_callbacks: dict[Type[Node], CallbackNode] = {}
        self.var_name = var_name
        self.indent = indent

    # ── decorators ────────────────────────────────────────────────────────────

    def pre(
        self,
        node_type: Type[Node],
        *,
        post_callback: CallbackNode | str | None = None,
    ) -> Callable[..., CallbackNode]:
        def decorator(fn: CallbackNode) -> CallbackNode:
            self._pre_callbacks[node_type] = fn
            if post_callback:
                if isinstance(post_callback, str):
                    self._post_callbacks[node_type] = (
                        lambda _, _2: post_callback
                    )  # type: ignore
                else:
                    self._post_callbacks[node_type] = post_callback
            return fn

        return decorator

    def post(self, node_type: Type[Node]) -> Callable[..., CallbackNode]:
        def decorator(fn: CallbackNode) -> CallbackNode:
            self._post_callbacks[node_type] = fn
            return fn

        return decorator

    def __call__(
        self,
        node_type: Type[Node],
        *,
        post_callback: CallbackNode | str | None = None,
    ) -> Callable[..., CallbackNode]:
        return self.pre(node_type, post_callback=post_callback)

    def extend(self) -> "BaseConverter":
        """
        Create a new converter that inherits all handlers from this one.
        New registrations on the child override inherited handlers.
        Parent is never affected.

        Example hierarchy:

            PY_BASE = BaseConverter()

            @PY_BASE(CssSelect)
            def _(node, ctx): return f"{ctx.nxt} = ..."  # generic

            # bs4 overrides css, inherits everything else
            PY_BS4 = PY_BASE.extend()

            @PY_BS4(CssSelect)
            def _(node, ctx): return f"{ctx.nxt} = {ctx.prv}.select_one(...)"

            # selectolax — separate extend from base, not from bs4
            PY_SELECTOLAX = PY_BASE.extend()

            @PY_SELECTOLAX(CssSelect)
            def _(node, ctx): return f"{ctx.nxt} = {ctx.prv}.css_first(...)"

            # js dialects
            JS_BASE = BaseConverter()
            JS_JQUERY = JS_BASE.extend()
            JS_CHEERIO = JS_BASE.extend()
        """
        child = BaseConverter(var_name=self.var_name, indent=self.indent)
        child._pre_callbacks = dict(self._pre_callbacks)
        child._post_callbacks = dict(self._post_callbacks)
        return child

    # ── internal traversal ────────────────────────────────────────────────────

    def _collect(
        self, result: list[str] | str | None, lines: list[str]
    ) -> None:
        """Append handler result to lines, skip empty."""
        if not result:
            return
        if isinstance(result, str):
            lines.append(result)
        else:
            lines.extend(r for r in result if r)

    def _emit_node(self, node: Node, ctx: ConverterContext) -> list[str]:
        """
        Emit a single node:
          1. pre callback
          2. body traversal — three modes:
               _PREDICATE_NODES  (Filter/Assert/Match/Logic*):
                   same ctx, no depth/index change
               _CONTAINER_NODES  (JsonDef/TypeDef/Struct/Init/InitField):
                   depth+1, index resets to 0
               Field and other pipeline-body nodes:
                   NOT auto-traversed — handler calls _emit_pipeline() explicitly
          3. post callback
        """
        lines: list[str] = []

        if cb := self._pre_callbacks.get(type(node)):
            self._collect(cb(node, ctx), lines)

        if node.body:
            if isinstance(node, _PREDICATE_NODES):
                # Predicate nodes: same ctx, no depth/index change
                for child in node.body:
                    self._collect(self._emit_node(child, ctx), lines)
            elif isinstance(node, _CONTAINER_NODES):
                # Container nodes: depth+1, index=0, NOT advanced between children
                inner_ctx = replace(ctx, depth=ctx.depth + 1, index=0)
                for child in node.body:
                    self._collect(self._emit_node(child, inner_ctx), lines)
            elif isinstance(node, _PIPELINE_NODES):
                # Pipeline nodes: use _emit_pipeline which advances index

                # contains in InitMode (deep=3, expected 2)
                if isinstance(node, InitField):
                    lines.extend(self._emit_pipeline(node.body, ctx))
                else:    
                    lines.extend(self._emit_pipeline(node.body, ctx.deeper()))

        if cb := self._post_callbacks.get(type(node)):
            self._collect(cb(node, ctx), lines)

        return lines

    def _emit_pipeline(
        self, nodes: list[Node], ctx: ConverterContext
    ) -> list[str]:
        """
        Emit pipeline nodes (Field.body, InitField.body, reserved field bodies).
        index advances after each node, depth is set by the caller.

        Call this from within a Field/InitField handler:

            @CONVERTER(Field)
            def _(node: Field, ctx: ConverterContext) -> list[str]:
                lines = [f"{ctx.indent}def _parse_{node.name}(self, v):"]
                lines += CONVERTER._emit_pipeline(node.body, ctx.deeper())
                return lines
        """
        lines: list[str] = []
        for node in nodes:
            self._collect(self._emit_node(node, ctx), lines)
            ctx = ctx.advance()
        return lines

    # ── public entry point ────────────────────────────────────────────────────

    def convert(self, module_ast: "Module") -> str:
        """
        Traverse Module.body and emit code.

        Module.body order (mirrors build order):
          CodeStartHook, Docstring, Imports, Utilities,
          JsonDef*, TypeDef*, Struct*, CodeEndHook

        Container nodes (JsonDef, TypeDef, Struct, Init, InitField) are
        traversed automatically with depth+1.

        Field.body pipeline traversal must be triggered manually from the
        Field handler via self._emit_pipeline().
        """
        ctx = ConverterContext(var_name=self.var_name, indent_char=self.indent)
        lines: list[str] = []
        for node in module_ast.body:
            self._collect(self._emit_node(node, ctx), lines)
        return "\n".join(lines)
