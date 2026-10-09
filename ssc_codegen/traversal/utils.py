"""AST utility functions shared across all code generation backends.

Provides inspection helpers for modules, REST structures, JSON schemas,
predicates, and placeholder templates used by converters during code generation.
"""

from __future__ import annotations

from dataclasses import dataclass

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
from ssc_codegen.naming import json_descriptor_var_name  # noqa: F401


@dataclass(frozen=True)
class DescriptorRef:
    """Symbolic reference to another JSON schema descriptor constant."""

    schema_name: str


def module_has_rest(module: Module) -> bool:
    """Check if the module contains at least one REST struct.

    Args:
        module: The AST `Module` to inspect.

    Returns:
        `True` if any node in the module body is a `StructRest`, `False` otherwise.
    """
    return any(isinstance(n, StructRest) for n in module.body)


def module_uses_http(module: Module) -> bool:
    """Check if the module contains any fetch or REST HTTP method.

    Covers both `StructRest` (REST APIs) and HTML structs with a `fetch`
    method — both generate HTTP signatures (e.g. ``client: httpx.Client``)
    and require HTTP library imports.

    Args:
        module: The AST `Module` to inspect.

    Returns:
        `True` if the module requires HTTP client machinery, `False` otherwise.
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
    """Check if all structs in the module are REST structs.

    Args:
        module: The AST `Module` to inspect.

    Returns:
        `True` if there are no non-REST structs in the module, `False` otherwise.
    """
    structs = [n for n in module.body if isinstance(n, StructBase)]
    return len(structs) == 0 or all(isinstance(s, StructRest) for s in structs)


def module_has_html_struct(module: Module) -> bool:
    """Check if the module has at least one HTML-parsing struct or function.

    RAW structs, `(raw)fn`, and REST structs are excluded because they do not
    require an HTML parser engine (e.g. `bs4`, `lxml`, `goquery`, or `DOMParser`).

    Args:
        module: The AST `Module` to inspect.

    Returns:
        `True` if at least one HTML parser struct or function is present.
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
    """Check if a module only contributes extension declarations.

    Args:
        module: The AST `Module` to inspect.

    Returns:
        `True` if the module defines extensions and has no structs or functions.
    """
    if not module.extensions:
        return False
    return not any(
        isinstance(node, (JsonDef, StructBase, FunctionDef))
        for node in module.body
    )


def err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    """Derive deterministic error-subclass name from struct name and error spec.

    Args:
        struct_name: The name of the parent REST struct.
        err: The `ErrorResponse` AST node specifying the HTTP status and type.

    Returns:
        PascalCase error class name (e.g. ``"UserGetNotFoundError"``).
    """
    from ssc_codegen.core.rest_artifacts import (
        err_subclass_name as _impl,
    )

    return _impl(struct_name, err)


def dict_entry_placeholder(
    tmpl: PlaceholderTemplate,
) -> PlaceholderSpec | None:
    """Return the single `PlaceholderSpec` for a dictionary entry value template.

    Args:
        tmpl: The placeholder template to inspect.

    Returns:
        The `PlaceholderSpec` if the template contains exactly one placeholder,
        or `None`.
    """
    return tmpl.single_placeholder()


def dict_needs_builder(d: dict[str, PlaceholderTemplate]) -> bool:
    """Check if any dictionary entry requires dynamic query/body builder logic.

    Returns `True` if any entry has an optional placeholder or bracket-style array.

    Args:
        d: Mapping from key names to `PlaceholderTemplate` values.

    Returns:
        `True` if runtime dictionary assembly helper is required, `False` otherwise.
    """
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
    """Walk up the parent chain to find enclosing Filter, Assert, Match, or PreValidate.

    Args:
        node: Starting AST node.

    Returns:
        The enclosing container node if found, or `None`.
    """
    cur = node.parent
    while cur:
        if isinstance(cur, (Filter, Assert, Match, PreValidate)):
            return cur
        cur = cur.parent
    return None


def find_enclosing_module(node: Node) -> Module | None:
    """Walk up the parent chain to find the enclosing `Module` AST root.

    Args:
        node: Starting AST node.

    Returns:
        The enclosing `Module` node if found, or `None`.
    """
    cur: Node | None = node
    while cur is not None:
        if isinstance(cur, Module):
            return cur
        cur = cur.parent
    return None


def resolve_json_def(node: Node, schema_name: str) -> JsonDef | None:
    """Find a `JsonDef` declaration by name in the enclosing module.

    Args:
        node: Starting AST node (used to locate the module root).
        schema_name: The identifier of the JSON schema to look up.

    Returns:
        The matching `JsonDef` node, or `None` if not found or if schema_name is empty.
    """
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
    """Split a dot-notation query path into segments, quoting string keys.

    For example, ``"foo.0.bar"`` becomes ``["'foo'", "0", "'bar'"]``.

    Args:
        query: Dot-separated JSON path string.

    Returns:
        List of formatted path segment expressions.
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
    """Check whether a JSON definition or any nested definition uses field aliases.

    Args:
        definition: The `JsonDef` node to check.
        definitions: Mapping of all available `JsonDef` schemas in the module.
        stack: Cycle-prevention stack of visited schema names.

    Returns:
        `True` if field alias remapping is required, `False` otherwise.
    """
    if definition.name in stack:
        return False
    if definition.has_alias_key:
        return True
    next_stack = (*stack, definition.name)
    for field in definition.body:
        if not isinstance(field, JsonDefField):
            continue
        info = field.ret_type_info
        if info.base == VariableType.JSON and info.ref:
            nested = definitions.get(info.ref)
            if nested and json_def_needs_remap(nested, definitions, next_stack):
                return True
    return False


def json_def_descriptors(
    definition: JsonDef,
    definitions: dict[str, JsonDef] | None = None,
    stack: tuple[str, ...] = (),
) -> dict[str, tuple[str, bool, bool, object]]:
    """Build dictionary of field descriptors for strict JSON allowlist projection.

    Args:
        definition: The root `JsonDef` node.
        definitions: Optional mapping of all available `JsonDef` schemas in the module.
        stack: Cycle-prevention stack of visited schema names.

    Returns:
        Dictionary mapping canonical field names to a tuple of
        ``(wire_path, is_optional, is_omitempty, nested_descriptors)``.
    """
    if definition.name in stack:
        return {}
    if definition.is_dict:
        val_desc: object = None
        val_info = definition.value_type_info
        if val_info and val_info.base == VariableType.JSON and val_info.ref:
            ref = DescriptorRef(val_info.ref)
            val_desc = [ref] if val_info.is_array else ref
        return {"__dict__": True, "__value__": val_desc}  # type: ignore[return-value, dict-item]
    descriptors: dict[str, tuple[str, bool, bool, object]] = {}
    for field in definition.body:
        if not isinstance(field, JsonDefField) or (
            field.ret_type_info and field.ret_type_info.skip
        ):
            continue
        wire_path = field.alias if field.alias else field.name
        info = field.ret_type_info
        is_optional = info.is_optional if info else False
        is_omitempty = info.omitempty if info else False
        nested_desc: object = None
        if field.is_dict or (info and info.is_dict):
            f_val_desc: object = None
            f_val_info = field.value_type_info or (
                info.value_type_info if info else None
            )
            if (
                f_val_info
                and f_val_info.base == VariableType.JSON
                and f_val_info.ref
            ):
                ref = DescriptorRef(f_val_info.ref)
                f_val_desc = [ref] if f_val_info.is_array else ref
            nested_desc = {"__dict__": True, "__value__": f_val_desc}
        elif info and info.base == VariableType.JSON and info.ref:
            ref = DescriptorRef(info.ref)
            nested_desc = [ref] if info.is_array else ref
        descriptors[field.name] = (
            wire_path,
            is_optional,
            is_omitempty,
            nested_desc,
        )
    return descriptors


def json_def_mapping(
    definition: JsonDef,
    definitions: dict[str, JsonDef],
    stack: tuple[str, ...] = (),
) -> dict[str, object]:
    """Build complete wire-to-canonical key mapping tree for JSON dictionaries.

    Args:
        definition: The root `JsonDef` node.
        definitions: Mapping of all available `JsonDef` schemas in the module.
        stack: Cycle-prevention stack of visited schema names.

    Returns:
        Dictionary mapping wire keys to canonical names or nested mapping tuples.
    """
    if definition.name in stack:
        return {}
    next_stack = (*stack, definition.name)
    mapping: dict[str, object] = {}
    for field in definition.body:
        if not isinstance(field, JsonDefField) or field.ret_type_info.skip:
            continue
        source = field.alias or field.name
        output = field.name
        info = field.ret_type_info
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
