"""Module-level handlers — struct, json, define, transform, imports."""

from __future__ import annotations

from pathlib import Path

from ssc_codegen.ast import (
    JsonDef,
    Module,
    Struct,
    StructType,
    TransformDef,
    TransformTarget,
)
from ssc_codegen.exceptions import BuildTimeError, ParseError
from ssc_codegen.kdl import (
    KDL2CSTParser,
    KdlArg,
    KdlNode,
    ReadDiagnostic,
    Severity,
)

from ssc_codegen.core.contexts import (
    DefineKind,
    DefineInfo,
    LintContext,
    ParseContext,
    TransformInfo,
)
from ssc_codegen.core.expressions import (
    _resolve_define_references,
    _VAR_TYPE_MAP,
)
from ssc_codegen.core.linting import (
    lint_define_node,
    lint_json_node,
    lint_struct_node,
    lint_transform_node,
)
from ssc_codegen.core.struct_parser import parse_json_fields, parse_struct

_KDL_TEXT_ENCODING = "utf-8-sig"


def handle_struct(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> Struct:
    lint_struct_node(node, module, ctx, lint)
    type_ = node.properties.get(
        "type", KdlArg(value="item", span=node.span, is_identifier=True)
    ).value
    keep_order = node.properties.get(
        "keep-order", KdlArg(value=False, span=node.span, is_identifier=False)
    ).value
    match type_:
        case "item":
            st_type = StructType.ITEM
        case "list":
            st_type = StructType.LIST
        case "table":
            st_type = StructType.TABLE
        case "dict":
            st_type = StructType.DICT
        case "flat":
            st_type = StructType.FLAT
        case "rest":
            st_type = StructType.REST
        case _:
            raise BuildTimeError(f"Unknown struct type: {type_}")
    struct = Struct(
        parent=module,
        name=str(node.args[0].value),
        struct_type=st_type,
        keep_order=keep_order,
    )
    ctx.structs[struct.name] = struct
    parse_struct(node.children, struct, ctx, lint)
    return struct


def handle_json(
    node: KdlNode, module: Module, ctx: ParseContext, lint: LintContext
) -> JsonDef:
    name = str(node.args[0].value) if node.args else ""
    is_array = node.type_annotation == "(array)"
    path = str(
        node.properties.get(
            "path", KdlArg(value="", span=node.span, is_identifier=False)
        ).value
    )
    json_def = JsonDef(parent=module, name=name, is_array=is_array, path=path)
    lint_json_node(node, lint, ctx)
    parse_json_fields(node.children, json_def)
    ctx.json_defs[json_def.name] = json_def
    if name:
        lint.json_kdl_nodes[name] = node
    return json_def


def handle_define(node: KdlNode, ctx: ParseContext, lint: LintContext) -> None:
    lint_define_node(node, ctx, lint)
    if node.children:
        ctx.children_defines[str(node.args[0].value)] = list(node.children)
        lint.defines[str(node.args[0].value)] = DefineInfo(
            name=str(node.args[0].value),
            kind=DefineKind.BLOCK,
            value=None,
            node=node,
        )
    else:
        for k, v in node.properties.items():
            value = v.value
            if isinstance(value, str):
                value = _resolve_define_references(value, ctx)
            ctx.property_defines[k] = value
            lint.defines[k] = DefineInfo(
                name=k, kind=DefineKind.SCALAR, value=str(value), node=node
            )


def handle_transform(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
    lint_transform_node(node, ctx, lint)
    name = str(node.args[0].value) if node.args else ""
    accept_str = str(
        node.properties.get(
            "accept", KdlArg(value="", span=node.span, is_identifier=True)
        ).value
    )
    ret_str = str(
        node.properties.get(
            "return", KdlArg(value="", span=node.span, is_identifier=True)
        ).value
    )
    if accept_str not in _VAR_TYPE_MAP:
        raise ParseError(
            f"transform '{name}': invalid accept type '{accept_str}' (AUTO not allowed)"
        )
    if ret_str not in _VAR_TYPE_MAP:
        raise ParseError(
            f"transform '{name}': invalid return type '{ret_str}' (AUTO not allowed)"
        )
    accept_type = _VAR_TYPE_MAP[accept_str]
    ret_type = _VAR_TYPE_MAP[ret_str]
    transform_def = TransformDef(name=name, accept=accept_type, ret=ret_type)
    for lang_node in node.children:
        lang = lang_node.name
        imports: list[str] = []
        code: list[str] = []
        for item in lang_node.children:
            if item.name == "import":
                imports.extend(str(a.value) for a in item.args)
            elif item.name == "code":
                code.extend(str(a.value) for a in item.args)
        transform_def.body.append(
            TransformTarget(
                parent=transform_def,
                lang=lang,
                imports=tuple(imports),
                code=tuple(code),
            )
        )
    ctx.transforms[name] = transform_def
    lang_nodes = node.children
    lint.transforms[name] = TransformInfo(
        name=name,
        accept=accept_str,
        ret=ret_str,
        langs=[n.name for n in lang_nodes],
        node=node,
    )


def resolve_imports(
    top_nodes: list[KdlNode],
    source_path: Path | None,
    ctx: ParseContext,
    lint: LintContext,
    diagnostics: list[ReadDiagnostic],
    visited: set[str] | None = None,
) -> list[KdlNode]:
    if visited is None:
        visited = set()
    if source_path is not None:
        visited.add(str(source_path.resolve()))

    result: list[KdlNode] = []
    for node in top_nodes:
        if node.name != "import":
            result.append(node)
            continue
        if not node.args:
            result.append(node)
            continue
        if source_path is None:
            diagnostics.append(
                ReadDiagnostic(
                    message="Cannot use 'import' when parsing from string without a file path",
                    severity=Severity.ERROR,
                    span=node.span,
                    path=lint.path,
                    code="E003",
                )
            )
            continue
        raw_path = str(node.args[0].value)
        import_path = (source_path.parent / raw_path).resolve()
        import_key = str(import_path)
        if import_key in visited:
            diagnostics.append(
                ReadDiagnostic(
                    message=f"Circular import detected: {import_path}",
                    severity=Severity.ERROR,
                    span=node.span,
                    path=lint.path,
                    code="E003",
                )
            )
            continue
        if not import_path.is_file():
            diagnostics.append(
                ReadDiagnostic(
                    message=f"import: file not found: {import_path}",
                    severity=Severity.ERROR,
                    span=node.span,
                    path=lint.path,
                    code="E003",
                )
            )
            continue
        visited.add(import_key)
        try:
            src = import_path.read_text(encoding=_KDL_TEXT_ENCODING)
        except OSError as e:
            diagnostics.append(
                ReadDiagnostic(
                    message=f"import: cannot read file: {e}",
                    severity=Severity.ERROR,
                    span=node.span,
                    path=lint.path,
                    code="E003",
                )
            )
            continue
        try:
            parser = KDL2CSTParser()
            doc = parser.parse(src)
        except Exception as e:
            diagnostics.append(
                ReadDiagnostic(
                    message=f"import: parse error in {import_path}: {e}",
                    severity=Severity.ERROR,
                    span=node.span,
                    path=lint.path,
                    code="E000",
                )
            )
            continue

        imported_nodes = resolve_imports(
            [KdlNode.from_cst(n) for n in doc.nodes],
            import_path,
            ctx,
            lint,
            diagnostics,
            visited,
        )
        imported_names: set[str] = set()
        for n in imported_nodes:
            if n.name == "struct":
                imported_names.add(str(n.args[0].value))
            elif n.name in ("json", "define", "transform"):
                imported_names.add(str(n.args[0].value) if n.args else "")
        for n in result:
            if n.name == "struct" and str(n.args[0].value) in imported_names:
                diagnostics.append(
                    ReadDiagnostic(
                        message=f"Name conflict: struct '{n.args[0].value}' conflicts with imported name",
                        severity=Severity.ERROR,
                        span=n.span,
                        path=lint.path,
                        code="E003",
                    )
                )
        result.extend(imported_nodes)
    return result
