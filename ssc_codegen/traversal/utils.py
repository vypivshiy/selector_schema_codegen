"""AST utility functions shared across all backends."""

from __future__ import annotations

from ssc_codegen.ast import (
    Assert,
    ErrorResponse,
    Filter,
    Match,
    MethodBase,
    Module,
    Node,
    PlaceholderSpec,
    PlaceholderTemplate,
    PreValidate,
    StructBase,
    StructRest,
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
