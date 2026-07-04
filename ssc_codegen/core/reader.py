"""Public API — parse KDL source into Module AST."""

from __future__ import annotations

from pathlib import Path

from ssc_codegen.ast import Module, StructRest
from ssc_codegen.exceptions import BuildTimeError, ParseError
from kdlquery import KDLParseError, parse as kdl_parse
from kdlquery import ReadDiagnostic, Severity
from kdlquery.types import Position, Span

from ssc_codegen.core.contexts import LintContext, ParseContext
from ssc_codegen.core.linter import lint_cross_refs, lint_module
from ssc_codegen.core.expressions import typedef_from_struct
from ssc_codegen.core.rest_artifacts import rest_artifacts_from_struct
from ssc_codegen.core.module_handler import (
    handle_define,
    handle_json,
    handle_struct,
    resolve_imports,
)


def parse_module(
    src: str, *, source_path: Path | None = None
) -> tuple[Module, list[ReadDiagnostic]]:
    """Parse KDL source -> Module AST + diagnostics."""
    try:
        doc = kdl_parse(src)
    except KDLParseError as exc:
        pos = Position(offset=0, line=exc.line, column=exc.col)
        span = Span(start=pos, end=pos)
        return Module(), [
            ReadDiagnostic(
                message=exc.msg,
                severity=Severity.ERROR,
                span=span,
                path=str(source_path) if source_path else "",
                hint="Fix the syntax error and try again.",
                code="E000",
                label="syntax error",
            )
        ]

    ctx = ParseContext(source_path=source_path)
    lint = LintContext()
    top_nodes = list(doc.nodes)
    diagnostics: list[ReadDiagnostic] = []

    # pass 1 — resolve imports (returns flat list with imported nodes)
    top_nodes = resolve_imports(top_nodes, source_path, ctx, lint, diagnostics)

    # pass 2 — structural linting on KdlDocument (current file only)
    diagnostics.extend(lint_module(doc, str(source_path or "")))

    # pass 3 — cross-ref validation on merged flat list
    diagnostics.extend(lint_cross_refs(top_nodes, str(source_path or "")))

    try:
        # pass 4 — collect defines
        for node in top_nodes:
            if node.name == "define":
                handle_define(node, ctx, lint)

        # pass 5 — build module
        module = Module()
        structs: list = []
        typedefs: list = []

        for node in top_nodes:
            lint.push(node.name)
            if node.name == "@doc":
                module.doc = str(node.args[0].value)
            elif node.name == "json":
                handle_json(node, module, ctx, lint)
            elif node.name == "struct":
                struct = handle_struct(node, module, ctx, lint)
                typedefs.append(typedef_from_struct(struct, module))
                structs.append(struct)
            elif node.name in ("define", "import"):
                pass  # already handled
            else:
                pass  # already reported by structural linter
            lint.pop()

        # wire module body — interleave each struct's typedef + REST artifacts
        # before the struct itself (mirrors TypeDef-before-Struct ordering)
        module.body.extend(ctx.json_defs.values())
        for typedef, struct in zip(typedefs, structs):
            module.body.append(typedef)
            if isinstance(struct, StructRest):
                module.body.extend(rest_artifacts_from_struct(struct, module))
            module.body.append(struct)

        # merge lint diagnostics into walker diagnostics
        diagnostics.extend(lint.diagnostics)

        return module, diagnostics
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
