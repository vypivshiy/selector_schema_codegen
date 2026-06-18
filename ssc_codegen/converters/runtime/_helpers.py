"""Shared AST utilities for runtime assembly."""

from ssc_codegen.converters.base import ConverterContext

import ssc_codegen.ast as a


def _module_has_rest(module: a.Module) -> bool:
    return any(isinstance(n, a.StructRest) for n in module.body)


def module_is_rest_only(module: a.Module) -> bool:
    structs = [n for n in module.body if isinstance(n, a.StructBase)]
    return len(structs) == 0 or all(
        isinstance(s, a.StructRest) for s in structs
    )


def http_client_import(ctx: ConverterContext) -> list[str]:
    client = ctx.meta.get("http_client", "")
    if client == "httpx":
        return ["import httpx"]
    return []
