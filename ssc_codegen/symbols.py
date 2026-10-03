"""Pure generated-symbol policy.

The linter owns CST traversal.  This module only processes normalized records;
the small duck-typed adapter at bottom exists for older public callers.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from ssc_codegen.naming import to_camel_case, to_pascal_case, to_snake_case


class SymbolKind(str, Enum):
    STRUCT = "struct"
    TYPE = "type"
    JSON = "json"
    FUNCTION = "fn"
    FIELD = "field"
    METHOD = "method"
    INIT = "init"
    PLACEHOLDER = "placeholder"
    REST_VARIANT = "rest-variant"
    REST_ALIAS = "rest-alias"
    REST_MATCHERS = "rest-matchers"
    RUNTIME_HELPER = "runtime-helper"


class SymbolScope(str, Enum):
    MODULE = "module"
    STRUCT = "struct"
    METHOD = "method"
    REQUEST = "request"
    PLACEHOLDER = "placeholder"
    RUNTIME = "runtime"


TARGETS = ("python", "javascript", "go", "rust")
_ALIASES = {"py": "python", "js": "javascript"}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\Z")
PYTHON_RESERVED = frozenset(keyword.kwlist)
JAVASCRIPT_RESERVED = frozenset(
    "await break case catch class const constructor debugger default delete do else enum export extends false finally for function if implements import in instanceof interface let new null package private protected public return static super switch this throw true try typeof var void while with yield".split()
)
GO_RESERVED = frozenset(
    "break default func interface select case defer go map struct chan else goto package switch const fallthrough if range type continue for import return var".split()
)
RUST_RESERVED = frozenset(
    "as break const continue crate else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while async await dyn abstract become box do final macro override priv typeof unsized virtual yield try".split()
)
RUST_CANNOT_BE_RAW = frozenset({"crate", "self", "super", "Self", "_"})


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    kind: SymbolKind
    raw_name: str
    target: str
    symbol: str
    scope: SymbolScope
    source: str
    span: Any
    declaration: Any = None


@dataclass(frozen=True, slots=True)
class SymbolFinding:
    record: SymbolRecord
    code: str
    message: str
    hint: str
    previous: SymbolRecord | None = None


HTTP_REQUEST_SIGNATURES: tuple[str, ...] = (
    "curl ",
    "http://",
    "https://",
    "GET ",
    "POST ",
)

REQUEST_LINE_CONTINUATION_HINT: str = (
    "KDL terminates line continuations ('\\') at single-line '//' comments; "
    "move comments outside multi-line '@request' continuations or escape them"
)


def normalize_targets(targets: Iterable[str] | None = None) -> tuple[str, ...]:
    result: list[str] = []
    for target in TARGETS if targets is None else targets:
        canonical = _ALIASES.get(target, target)
        if canonical not in TARGETS:
            raise ValueError(
                f"Unknown target '{target}'. Use: {', '.join(TARGETS)}."
            )
        if canonical not in result:
            result.append(canonical)
    return tuple(result)


def target_reserved_words(target: str) -> frozenset[str]:
    target = normalize_targets((target,))[0]
    return {
        "python": PYTHON_RESERVED,
        "javascript": JAVASCRIPT_RESERVED,
        "go": GO_RESERVED,
        "rust": RUST_CANNOT_BE_RAW,
    }[target]


def is_valid_symbol(target: str, symbol: str) -> bool:
    return bool(
        _IDENTIFIER.fullmatch(symbol)
    ) and symbol not in target_reserved_words(target)


def target_symbol_plan(
    records: Iterable[SymbolRecord],
    targets: Iterable[str] | None = None,
) -> tuple[SymbolFinding, ...]:
    """Validate normalized records and report findings in record order."""
    requested = normalize_targets(targets)
    records = tuple(records)
    seen: dict[tuple[str, SymbolScope, str], dict[str, SymbolRecord]] = {}
    findings: list[SymbolFinding] = []
    for record in records:
        if record.target not in requested:
            continue
        if not is_valid_symbol(record.target, record.symbol):
            hint = (
                REQUEST_LINE_CONTINUATION_HINT
                if (
                    record.kind is SymbolKind.FIELD
                    and record.raw_name.startswith(HTTP_REQUEST_SIGNATURES)
                )
                else f"rename '{record.raw_name}' to a portable identifier"
            )
            findings.append(
                SymbolFinding(
                    record,
                    "E403",
                    f"{record.kind.value} '{record.raw_name}' produces invalid {record.target} identifier '{record.symbol}'",
                    hint,
                )
            )
            continue
        # Module symbols share one namespace. Local names are scoped to their
        # owning declaration, represented by collector-provided source key.
        namespace = (
            record.target,
            record.scope,
            "" if record.scope is SymbolScope.MODULE else record.source,
        )
        previous = seen.setdefault(namespace, {}).get(record.symbol)
        if previous is None:
            seen[namespace][record.symbol] = record
            continue
        if (
            record.scope is SymbolScope.MODULE
            and previous.kind in (SymbolKind.STRUCT, SymbolKind.TYPE)
            and record.kind in (SymbolKind.STRUCT, SymbolKind.TYPE)
            and previous.raw_name == record.raw_name
            and previous.source == record.source
        ):
            continue
        findings.append(
            SymbolFinding(
                record,
                "E402",
                f"{record.target} symbol collision: {record.kind.value} '{record.raw_name}' and {previous.kind.value} '{previous.raw_name}' both produce '{record.symbol}'",
                f"rename one declaration so {record.target} names differ",
                previous,
            )
        )
    return tuple(findings)


def top_symbol_names(
    kind: SymbolKind, raw: str, target: str
) -> tuple[str, ...]:
    pascal = to_pascal_case(raw)
    if kind is SymbolKind.STRUCT:
        return (pascal, f"{pascal}Type")
    if kind is SymbolKind.JSON:
        return (f"{pascal}Json",)
    return {
        "python": (to_snake_case(raw),),
        "javascript": (to_camel_case(raw),),
        "go": (pascal,),
        "rust": (to_snake_case(raw),),
    }[target]


def local_symbol(kind: SymbolKind, raw: str, target: str) -> str:
    snake, pascal = to_snake_case(raw), to_pascal_case(raw)
    if kind is SymbolKind.FIELD:
        return {
            "python": f"_parse_{snake}",
            "javascript": f"_parse{pascal}",
            "go": f"parse{pascal}",
            "rust": snake,
        }[target]
    if kind is SymbolKind.METHOD:
        return {
            "python": snake,
            "javascript": to_camel_case(snake),
            "go": pascal,
            "rust": snake,
        }[target]
    if kind is SymbolKind.PLACEHOLDER:
        return {
            "python": snake,
            "javascript": to_camel_case(snake),
            "go": to_camel_case(raw),
            "rust": snake,
        }[target]
    return {
        "python": f"_init_{snake}",
        "javascript": f"_init{pascal}",
        "go": f"init{pascal}",
        "rust": f"init_{snake}",
    }[target]
