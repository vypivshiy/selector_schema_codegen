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

import re

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

_UNESCAPED_DOT_RE = re.compile(r"(?<!\\)\.")


def _leaf_key_pascal(path: str) -> str:
    """Extract the leaf non-numeric segment of a dot-path in PascalCase."""
    raw_segs = _UNESCAPED_DOT_RE.split(path)
    segs = [
        seg.replace(r"\.", ".").replace(r"\\", "\\") for seg in raw_segs if seg
    ]
    if not segs:
        return ""
    non_numeric = [seg for seg in segs if not seg.isdigit()]
    leaf = non_numeric[-1] if non_numeric else segs[-1]
    return to_pascal_case(leaf.replace(".", "_").replace("-", "_"))


def err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    """Return the canonical error variant class name for an `ErrorResponse` in a REST struct.

    Args:
        struct_name (str): Name of the enclosing REST struct.
        err (ErrorResponse): Error response mapping node.

    Returns:
        str: Canonical PascalCase error variant class name (e.g. `UserClientErr404NotFound`).
    """
    base = f"{to_pascal_case(struct_name)}Err{err.status}"
    if err.suffix:
        return f"{base}{to_pascal_case(err.suffix.replace('-', '_'))}"
    all_keys = [*err.required_keys, *err.conditions.keys()]
    for key in all_keys[:2]:
        base += _leaf_key_pascal(key)
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
    """Synthesize companion REST result AST nodes from a `StructRest` declaration.

    Generates `ResultVariantDef` nodes for unique error conditions, `ResultAliasDef`
    type aliases for method returns, and `MatcherListDef` condition lists.

    Args:
        struct: Source `StructRest` AST node.
        parent: The root `Module` AST node owning the generated definitions.

    Returns:
        List of synthesized AST nodes in emission order (variants, aliases, matchers).
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
                error_schema=err.schema_name,
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
