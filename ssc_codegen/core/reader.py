"""Reader class and public API."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ssc_codegen.ast import Module
from ssc_codegen.exceptions import BuildTimeError, ParseError
from ssc_codegen.kdl import (
    KDL2CSTParser,
    KDLParseError,
    KdlArg,
    KdlNode,
    Position,
    ReadDiagnostic,
    Reader,
    Severity,
    Span,
    WalkContext,
    parse_into,
)

from ssc_codegen.core.contexts import LintContext, ParseContext
from ssc_codegen.core.expressions import typedef_from_struct
from ssc_codegen.core.module_handler import (
    handle_define,
    handle_json,
    handle_struct,
    handle_transform,
    resolve_imports,
)
from ssc_codegen.core.linting import lint_json_cross_refs, lint_rest_cross_refs


class SscReader(Reader[KdlNode, Module]):
    """Unified KDL -> Module AST reader with integrated linting."""

    def __init__(self, *, source_path: Path | None = None) -> None:
        self._source_path = source_path
        self._ctx = ParseContext(source_path=source_path)
        self._lint = LintContext()

    def on_node(
        self,
        name: str,
        args: tuple[KdlArg, ...],
        properties: Mapping[str, KdlArg],
        children: tuple[KdlNode, ...],
        ctx: WalkContext[KdlNode],
    ) -> KdlNode:
        return ctx.node

    def error_node(self, message: str, ctx: WalkContext[KdlNode]) -> KdlNode:
        return ctx.node

    def finalize(
        self,
        nodes: list[KdlNode],
        diagnostics: list[ReadDiagnostic],
    ) -> Module:
        ctx = self._ctx
        lint = self._lint
        top_nodes = nodes

        # pass 1 — resolve imports
        top_nodes = resolve_imports(
            top_nodes, self._source_path, ctx, lint, diagnostics
        )

        # pass 2 — collect defines and transforms
        for node in top_nodes:
            if node.name == "define":
                handle_define(node, ctx, lint)
            elif node.name == "transform":
                handle_transform(node, ctx, lint)

        # pass 3 — build module
        module = Module()
        structs: list = []
        typedefs: list = []

        for node in top_nodes:
            lint.push(node.name)
            if node.name == "@doc":
                module.docstring.value = str(node.args[0].value)
            elif node.name == "json":
                handle_json(node, module, ctx, lint)
            elif node.name == "struct":
                struct = handle_struct(node, module, ctx, lint)
                typedefs.append(typedef_from_struct(struct, module))
                structs.append(struct)
            elif node.name in ("define", "transform", "import"):
                pass  # already handled
            else:
                diagnostics.append(
                    ReadDiagnostic(
                        message=f"Unknown node: {node.name}",
                        severity=Severity.ERROR,
                        span=node.span,
                        path=lint.path,
                        code="E200",
                    )
                )
            lint.pop()

        # wire transforms
        for td in ctx.transforms.values():
            td.parent = module

        # post-pass: cross-reference validation
        lint_json_cross_refs(ctx, lint)
        lint_rest_cross_refs(ctx, lint)

        # wire module body
        module.body.extend(
            list(ctx.json_defs.values())
            + list(ctx.transforms.values())
            + typedefs
            + structs
        )

        # merge lint diagnostics into walker diagnostics
        diagnostics.extend(lint.diagnostics)

        return module


def parse_module(
    src: str, *, source_path: Path | None = None
) -> tuple[Module, list[ReadDiagnostic]]:
    """Parse KDL source -> Module AST + diagnostics."""
    parser = KDL2CSTParser()
    try:
        doc = parser.parse(src)
    except KDLParseError as exc:
        pos = Position(offset=exc.offset, line=exc.line, column=exc.column)
        span = Span(start=pos, end=pos)
        return Module(), [
            ReadDiagnostic(
                message=exc.message,
                severity=Severity.ERROR,
                span=span,
                path=str(source_path) if source_path else "",
                hint="Fix the syntax error and try again.",
                code="E000",
                label="syntax error",
            )
        ]
    reader = SscReader(source_path=source_path)
    try:
        return parse_into(doc, reader)
    except (ParseError, BuildTimeError) as exc:
        pos = Position(offset=0, line=0, column=0)
        span = Span(start=pos, end=pos)
        return Module(), [
            ReadDiagnostic(
                message=str(exc),
                severity=Severity.ERROR,
                span=span,
                path=str(source_path) if source_path else "",
                code="E000",
            )
        ]
