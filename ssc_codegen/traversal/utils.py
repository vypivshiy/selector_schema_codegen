"""AST utility functions shared across all code generation backends.

Provides inspection helpers for modules, REST structures, JSON schemas,
predicates, and placeholder templates used by converters during code generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ssc_codegen.ast import (
    Assert,
    Fallback,
    Field,
    Filter,
    FunctionDef,
    JsonDef,
    Key,
    Match,
    MethodBase,
    MethodFetch,
    Module,
    Node,
    PreValidate,
    Return,
    Struct,
    StructBase,
    StructRest,
    StructType,
    Value,
)
from ssc_codegen.naming import to_pascal_case


def module_has_rest(module: Module) -> bool:
    """Check if the module contains at least one REST struct.

    Args:
        module (Module): The AST `Module` to inspect.

    Returns:
        bool: `True` if any node in the module body is a `StructRest`, `False` otherwise.
    """
    return any(isinstance(n, StructRest) for n in module.body)


def module_has_fetch(module: Module) -> bool:
    """Check if the module contains at least one struct with a `MethodFetch` node.

    Args:
        module (Module): The AST `Module` to inspect.

    Returns:
        bool: `True` if any struct in the module body declares a `MethodFetch`,
        `False` otherwise.
    """
    for node in module.body:
        if isinstance(node, StructBase):
            for child in node.body:
                if isinstance(child, MethodFetch):
                    return True
    return False


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
        if isinstance(n, Struct) and n.type != StructType.RAW:
            return True
        if isinstance(n, FunctionDef) and not n.is_raw:
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


def is_return_after_fallback(node: Return) -> bool:
    """Check whether a `Return` node is immediately preceded by a `Fallback` sibling.

    Args:
        node: The `Return` AST node to inspect.

    Returns:
        `True` if `node` sits in a parent `body` right after a `Fallback` node.
    """
    if node.parent is None:
        return False
    body = node.parent.body
    try:
        idx = body.index(node)
    except ValueError:
        return False
    return idx > 0 and isinstance(body[idx - 1], Fallback)


def resolve_location(node: Node) -> str:
    """Walk the parent chain to build a ``{StructName}.{field_or_marker}`` label.

    Args:
        node: Starting AST node (such as `Assert` or `Re`).

    Returns:
        Language-agnostic location string used in default assertion and regex
        error messages.
    """
    struct_name = ""
    field_part = ""
    current = node.parent
    while current is not None:
        if isinstance(current, PreValidate) and not field_part:
            field_part = "@pre-validate"
        elif isinstance(current, Field) and not field_part:
            field_part = current.name or "key"
        elif isinstance(current, Key) and not field_part:
            field_part = "key"
        elif isinstance(current, Value) and not field_part:
            field_part = "value"
        if isinstance(current, StructBase):
            struct_name = to_pascal_case(current.name)
            break
        current = current.parent
    if field_part:
        return f"{struct_name}.{field_part}" if struct_name else field_part
    return struct_name


def resolve_source_file(node: Node) -> str:
    """Walk the parent chain to the enclosing `Module` and return its `source_file`.

    Args:
        node: Starting AST node.

    Returns:
        The `source_file` string from the enclosing `Module`, or ``""``.
    """
    module = find_enclosing_module(node)
    return module.source_file if module is not None else ""


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


@dataclass(frozen=True, slots=True)
class GjsonSegment:
    """Single parsed segment of a GJSON path expression."""

    kind: Literal["key", "index", "hash"]
    key: str = ""
    index: int | None = None


def parse_gjson_path(path: str) -> tuple[GjsonSegment, ...]:
    """Parse and validate a filter-free GJSON path expression into segments.

    Args:
        path (str): Raw GJSON path expression string.

    Returns:
        tuple[GjsonSegment, ...]: Ordered tuple of parsed key, index, or hash segments.

    Raises:
        ValueError: If the path is empty, contains empty segments, has an invalid
            or trailing escape sequence, uses negative array indices, or includes
            unsupported filter expressions.
    """
    if not path:
        raise ValueError("Empty GJSON path expression")

    raw_chars: list[str] = []
    unescaped_chars: list[str] = []
    has_escape = False
    has_unescaped_hash = False
    raw_segments: list[tuple[str, str, bool, bool]] = []

    i = 0
    n = len(path)
    while i < n:
        ch = path[i]
        if ch == "\\":
            if i + 1 >= n:
                raise ValueError(
                    f"Trailing unescaped backslash in GJSON path '{path}'"
                )
            nxt = path[i + 1]
            if nxt not in (".", "\\", "#"):
                raise ValueError(
                    f"Invalid escape sequence '\\{nxt}' in GJSON path '{path}'"
                )
            raw_chars.append(ch)
            raw_chars.append(nxt)
            unescaped_chars.append(nxt)
            has_escape = True
            i += 2
        elif ch == ".":
            if not raw_chars:
                raise ValueError(f"Empty segment in GJSON path '{path}'")
            raw_segments.append(
                (
                    "".join(raw_chars),
                    "".join(unescaped_chars),
                    has_escape,
                    has_unescaped_hash,
                )
            )
            raw_chars = []
            unescaped_chars = []
            has_escape = False
            has_unescaped_hash = False
            i += 1
        else:
            if ch == "#":
                has_unescaped_hash = True
            raw_chars.append(ch)
            unescaped_chars.append(ch)
            i += 1

    if not raw_chars:
        raise ValueError(f"Empty trailing segment in GJSON path '{path}'")
    raw_segments.append(
        (
            "".join(raw_chars),
            "".join(unescaped_chars),
            has_escape,
            has_unescaped_hash,
        )
    )

    segments: list[GjsonSegment] = []
    for (
        raw_seg,
        unescaped_seg,
        seg_has_escape,
        seg_has_hash,
    ) in raw_segments:
        if raw_seg == "#":
            segments.append(GjsonSegment(kind="hash", key="#"))
        elif seg_has_hash:
            raise ValueError(
                f"Unsupported GJSON filter or hash expression '{raw_seg}' in '{path}'"
            )
        elif (
            not seg_has_escape
            and raw_seg.startswith("-")
            and raw_seg[1:].isdigit()
        ):
            raise ValueError(
                f"Negative array index '{raw_seg}' is not supported in GJSON path '{path}'"
            )
        elif not seg_has_escape and raw_seg.isdigit():
            segments.append(
                GjsonSegment(kind="index", key=raw_seg, index=int(raw_seg))
            )
        else:
            segments.append(GjsonSegment(kind="key", key=unescaped_seg))

    return tuple(segments)


def is_malformed_gjson_path(path: str) -> bool:
    """Check whether a GJSON path expression violates the supported subset grammar.

    Args:
        path (str): Raw GJSON path expression string to validate.

    Returns:
        bool: ``True`` if the path is malformed, ``False`` if valid.
    """
    try:
        parse_gjson_path(path)
        return False
    except ValueError:
        return True


def classify_gjson_path(path: str) -> tuple[bool, str]:
    """Classify a GJSON path into a direct O(1) dictionary key or a path query.

    Args:
        path (str): GJSON path expression string.

    Returns:
        tuple[bool, str]: ``(True, unescaped_key)`` when the expression resolves
        to a single flat object key, or ``(False, path)`` when it requires
        multi-segment, index, or array projection evaluation.
    """
    try:
        segments = parse_gjson_path(path)
    except ValueError:
        return False, path
    if len(segments) == 1 and segments[0].kind == "key":
        return True, segments[0].key
    return False, path
