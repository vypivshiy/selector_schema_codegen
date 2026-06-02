"""Shared AST utilities for runtime assembly."""

from ssc_codegen.converters.base import ConverterContext

import ssc_codegen.ast as a


def _module_has_rest(node: a.Node) -> bool:
    module: a.Node | None = node
    while module is not None and not isinstance(module, a.Module):
        module = getattr(module, "parent", None)
    if module is None:
        return False
    return any(isinstance(n, a.StructRest) for n in getattr(module, "body", []))


def module_is_rest_only(node: a.Node) -> bool:
    module: a.Node | None = node
    while module is not None and not isinstance(module, a.Module):
        module = getattr(module, "parent", None)
    if module is None:
        return False
    structs = [
        n for n in getattr(module, "body", []) if isinstance(n, a.StructBase)
    ]
    return len(structs) == 0 or all(
        isinstance(s, a.StructRest) for s in structs
    )


def http_client_import(ctx: ConverterContext) -> list[str]:
    client = ctx.meta.get("http_client", "")
    if client == "httpx":
        return ["import httpx"]
    return []
