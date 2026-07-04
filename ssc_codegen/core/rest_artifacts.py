"""Synthesize REST result-artifact AST nodes from a ``StructRest``.

Mirrors ``core/expressions.typedef_from_struct``: builds ``ResultVariantDef``
/ ``ResultAliasDef`` / ``MatcherListDef`` nodes and inserts them into
``Module.body`` before the struct.  Each ``MethodRest`` gets its
``result_alias_name`` field populated so converters can reference the alias
in method signatures.

Language-agnostic: carries raw data only.  Per-language spelling (lambda
syntax, JSDoc, dataclass layout) is the converter's job.
"""

from __future__ import annotations

from ssc_codegen.ast import (
    JsonDef,
    MatcherEntry,
    MatcherListDef,
    MethodRest,
    ResultAliasDef,
    ResultVariantDef,
    StructRest,
)
from ssc_codegen.ast.module import Module
from ssc_codegen.ast.struct import ErrorResponse
from ssc_codegen.naming import to_pascal_case


def err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    """Deterministic error-subclass name from struct name + error spec.

    Concatenates PascalCase(struct) + 'Err' + status + PascalCase(required_keys)
    + PascalCase(condition_keys).  Identical across all languages.
    """
    base = f"{to_pascal_case(struct_name)}Err{err.status}"
    for key in err.required_keys:
        base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    if err.conditions:
        for key in err.conditions:
            base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    return base


def _schema_array_flag(schema: str, module: Module | None) -> bool:
    """True if the named JsonDef is an array schema. Language-agnostic fact."""
    if not schema or module is None:
        return False
    for n in module.body:
        if isinstance(n, JsonDef) and n.name == schema:
            return n.is_array
    return False


def _result_alias_name(raw_name: str) -> str:
    return to_pascal_case(raw_name or "fetch") + "Result"


def rest_artifacts_from_struct(struct: StructRest, parent: Module) -> list:
    """Build result/matcher nodes for a ``StructRest``.

    Returns nodes in emission order: error subclass declarations, per-method
    result aliases, then the per-struct matcher list.  The caller inserts
    them into ``Module.body`` before the struct (same pattern as
    ``typedef_from_struct``).

    Side effect: sets ``result_alias_name`` on each ``MethodRest`` so the
    converter can reference the alias in the method signature.

    Carries RAW data only (schema names + array flags, raw condition specs);
    per-language type/check spelling is the converter's job.
    """
    out: list = []

    # 1. unique error subclass declarations (deduped by class name)
    seen_variants: set[str] = set()
    err_variant_names: list[str] = []
    for err in struct.errors:
        cls_name = err_subclass_name(struct.name, err)
        if cls_name in seen_variants:
            continue
        seen_variants.add(cls_name)
        err_variant_names.append(cls_name)
        out.append(
            ResultVariantDef(
                parent=parent,
                name=cls_name,
                status=err.status,
                schema_name=err.schema_name,
                schema_is_array=_schema_array_flag(err.schema_name, parent),
            )
        )

    # 2. per-method result aliases — also stamps result_alias_name on the method
    for child in struct.body:
        if not isinstance(child, MethodRest):
            continue
        alias_name = _result_alias_name(child.name)
        out.append(
            ResultAliasDef(
                parent=parent,
                name=alias_name,
                response_schema=child.response_schema,
                response_is_array=_schema_array_flag(
                    child.response_schema, parent
                ),
                err_variants=list(err_variant_names),
            )
        )
        child.result_alias_name = alias_name

    # 3. per-struct matcher list (raw condition data; visitor renders).
    # Always emitted — the method body references the matchers var unconditionally,
    # so an empty list must exist even when there are no @error declarations.
    seen_entries: set[tuple[int, str]] = set()
    unique_entries: list[MatcherEntry] = []
    for err in struct.errors:
        key = (err.status, err_subclass_name(struct.name, err))
        if key in seen_entries:
            continue
        seen_entries.add(key)
        unique_entries.append(
            MatcherEntry(
                status=err.status,
                required_keys=list(err.required_keys),
                conditions=dict(err.conditions),
                factory_name=key[1],
            )
        )

    out.append(
        MatcherListDef(
            parent=parent,
            struct_name=struct.name,
            entries=unique_entries,
        )
    )

    return out
