"""Parsing and type resolution for user-defined pipeline extensions."""

from __future__ import annotations

from kdlquery import KdlNode

from ssc_codegen.ast import (
    ExtensionDef,
    ExtensionHelper,
    ExtensionImport,
    ExtensionTarget,
    ExtensionType,
    Module,
    TypeInfo,
    VariableType,
)
from ssc_codegen.core.contexts import LintContext, ParseContext
from ssc_codegen.exceptions import BuildTimeError

_TYPE_NAMES: dict[str, VariableType] = {
    "bool": VariableType.BOOL,
    "doc": VariableType.DOCUMENT,
    "float": VariableType.FLOAT,
    "int": VariableType.INT,
    "str": VariableType.STRING,
}


def parse_extension_type(value) -> ExtensionType:
    name = str(value.value)
    is_optional = name.endswith("?")
    if is_optional:
        name = name[:-1]
    is_array = value.type_annotation == "(array)"
    if name == "T":
        if is_array or is_optional:
            raise BuildTimeError("generic type T cannot have modifiers")
        return ExtensionType(generic="T")
    base = _TYPE_NAMES.get(name)
    if base is None:
        raise BuildTimeError(f"unknown extension signature type: {name}")
    return ExtensionType(base=base, is_array=is_array, is_optional=is_optional)


def resolve_extension_call(
    definition: ExtensionDef, input_type: TypeInfo
) -> TypeInfo:
    if not definition.accept.accepts(input_type):
        return TypeInfo(base=VariableType.AUTO)
    return definition.resolve_return(input_type)


def _parse_import(node: KdlNode) -> ExtensionImport:
    return ExtensionImport(
        value=str(node.args[0].value),
        alias=str(node.get_prop("alias") or ""),
    )


def _parse_helper(node: KdlNode) -> ExtensionHelper:
    name = str(node.args[0].value)
    imports = tuple(
        _parse_import(child)
        for child in node.children
        if child.name == "import" and child.args
    )
    source_node = next(
        (child for child in node.children if child.name == "source"), None
    )
    source = (
        str(source_node.args[0].value)
        if source_node is not None and source_node.args
        else ""
    )
    return ExtensionHelper(name=name, source=source, imports=imports)


def _parse_target(node: KdlNode) -> ExtensionTarget:
    imports = tuple(
        _parse_import(child)
        for child in node.children
        if child.name == "import" and child.args
    )
    helpers = tuple(
        _parse_helper(child)
        for child in node.children
        if child.name == "helper" and child.args
    )
    emit_node = next(
        (child for child in node.children if child.name == "emit"), None
    )
    emit = (
        str(emit_node.args[0].value)
        if emit_node is not None and emit_node.args
        else ""
    )
    return ExtensionTarget(
        language=node.name,
        emit=emit,
        imports=imports,
        helpers=helpers,
    )


def handle_extension(
    node: KdlNode,
    module: Module,
    ctx: ParseContext,
    lint: LintContext,
) -> list[ExtensionDef]:
    if not node.args:
        raise BuildTimeError("'extension' requires a namespace")
    namespace = str(node.args[0].value)
    definitions: list[ExtensionDef] = []
    for operation in node.children:
        sig = next(
            (child for child in operation.children if child.name == "sig"),
            None,
        )
        if sig is None or len(sig.args) != 2:
            continue
        definition = ExtensionDef(
            namespace=namespace,
            name=operation.name,
            accept=parse_extension_type(sig.args[0]),
            ret=parse_extension_type(sig.args[1]),
            targets={
                child.name: _parse_target(child)
                for child in operation.children
                if child.name in ("py", "js", "go")
            },
        )
        qualified_name = definition.qualified_name
        if qualified_name in ctx.extensions:
            lint.error(
                operation,
                message=f"duplicate extension operation '{qualified_name}'",
                code="E402",
            )
            continue
        ctx.extensions[qualified_name] = definition
        module.extensions[qualified_name] = definition
        definitions.append(definition)
    return definitions
