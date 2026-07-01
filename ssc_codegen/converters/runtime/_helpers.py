"""Shared AST utilities for runtime assembly."""

import ssc_codegen.ast as a


def _module_has_rest(module: a.Module) -> bool:
    return any(isinstance(n, a.StructRest) for n in module.body)
