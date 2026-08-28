"""AST utility functions shared across all backends."""

from __future__ import annotations

from ssc_codegen.ast import (
    Assert,
    ErrorResponse,
    Filter,
    FunctionDef,
    JsonDef,
    JsonDefField,
    Match,
    MethodBase,
    Module,
    Node,
    PlaceholderSpec,
    PlaceholderTemplate,
    PreValidate,
    Struct,
    StructBase,
    StructRest,
    StructType,
    VariableType,
)


def module_has_rest(module: Module) -> bool:
    """True if the module contains at least one REST struct."""
    return any(isinstance(n, StructRest) for n in module.body)


def module_uses_http(module: Module) -> bool:
    """True if the module contains any fetch/rest method.

    Covers both ``StructRest`` (REST APIs) and HTML structs with a
    ``fetch`` method — both produce signatures like
    ``client: httpx.Client`` and therefore need ``import httpx``.
    """
    for node in module.body:
        if isinstance(node, StructRest):
            return True
        if isinstance(node, StructBase):
            for child in node.body:
                if isinstance(child, MethodBase):
                    return True
    return False


def module_is_rest_only(module: Module) -> bool:
    """True if ALL structs in the module are REST structs (or there are none)."""
    structs = [n for n in module.body if isinstance(n, StructBase)]
    return len(structs) == 0 or all(isinstance(s, StructRest) for s in structs)


def module_has_html_struct(module: Module) -> bool:
    """True if the module has at least one HTML-parsing struct or function.

    RAW structs, (raw)fn, and REST structs are excluded — they don't need
    an HTML parser backend (bs4/lxml/goquery/DOMParser).
    """
    for n in module.body:
        if isinstance(n, StructRest):
            continue
        if isinstance(n, Struct):
            if n.type != StructType.RAW:
                return True
        if isinstance(n, FunctionDef):
            if not n.is_raw:
                return True
    return False


def module_is_extension_only(module: Module) -> bool:
    """True when a module only contributes extension declarations."""
    if not module.extensions:
        return False
    return not any(
        isinstance(node, (JsonDef, StructBase, FunctionDef))
        for node in module.body
    )


def err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    """Deterministic error-subclass name from struct name + error spec."""
    from ssc_codegen.core.rest_artifacts import (
        err_subclass_name as _impl,
    )

    return _impl(struct_name, err)


def dict_entry_placeholder(
    tmpl: PlaceholderTemplate,
) -> "PlaceholderSpec | None":
    """Return the PlaceholderSpec for a dict entry value, or None."""
    return tmpl.single_placeholder()


def dict_needs_builder(d: dict[str, PlaceholderTemplate]) -> bool:
    """True if any dict entry has an optional or bracket-style array placeholder."""
    for tmpl in d.values():
        ph = tmpl.single_placeholder()
        if ph is None:
            continue
        if ph.is_optional:
            return True
        if ph.is_array and ph.style == "bracket":
            return True
    return False


def find_predicate_container(node: Node) -> Node | None:
    """Walk the parent chain to find the enclosing Filter/Assert/Match/PreValidate."""
    cur = node.parent
    while cur:
        if isinstance(cur, (Filter, Assert, Match, PreValidate)):
            return cur
        cur = cur.parent
    return None


def find_enclosing_module(node: Node) -> Module | None:
    """Walk the parent chain to find the enclosing Module."""
    cur: Node | None = node
    while cur is not None:
        if isinstance(cur, Module):
            return cur
        cur = cur.parent
    return None


def resolve_json_def(node: Node, schema_name: str) -> JsonDef | None:
    """Find a JsonDef by name in the enclosing module."""
    if not schema_name:
        return None
    module = find_enclosing_module(node)
    if module is None:
        return None
    for n in module.body:
        if isinstance(n, JsonDef) and n.name == schema_name:
            return n
    return None


def jsonify_path_to_segments(query: str) -> list[str]:
    """Split a dot-notation path into segments, quoting string keys.

    foo.0.bar -> ["foo", "0", "bar"]  (digits stay as strings)
    """
    if not query:
        return []
    parts: list[str] = []
    for part in query.split("."):
        if part.isdigit():
            parts.append(part)
        else:
            parts.append(repr(part))
    return parts


def json_def_needs_remap(
    definition: JsonDef,
    definitions: dict[str, JsonDef],
    stack: tuple[str, ...] = (),
) -> bool:
    """Return whether a JSON definition or nested definition has aliases."""
    if definition.name in stack:
        return False
    if definition.has_alias_key:
        return True
    next_stack = (*stack, definition.name)
    for field in definition.body:
        if not isinstance(field, JsonDefField):
            continue
        info = field.type_info
        if info.base == VariableType.JSON and info.ref:
            nested = definitions.get(info.ref)
            if nested and json_def_needs_remap(nested, definitions, next_stack):
                return True
    return False


def json_def_mapping(
    definition: JsonDef,
    definitions: dict[str, JsonDef],
    stack: tuple[str, ...] = (),
) -> dict[str, object]:
    """Build a complete source-key to canonical-key mapping tree."""
    if definition.name in stack:
        return {}
    next_stack = (*stack, definition.name)
    mapping: dict[str, object] = {}
    for field in definition.body:
        if not isinstance(field, JsonDefField) or field.type_info.skip:
            continue
        source = field.alias or field.name
        output = field.name
        info = field.type_info
        nested = (
            definitions.get(info.ref)
            if info.base == VariableType.JSON and info.ref
            else None
        )
        if nested and json_def_needs_remap(nested, definitions, next_stack):
            nested_mapping = json_def_mapping(nested, definitions, next_stack)
            mapping[source] = (
                output,
                [nested_mapping] if info.is_array else nested_mapping,
            )
        else:
            mapping[source] = output
    return mapping
