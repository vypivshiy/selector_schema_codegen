"""AST container nodes for predicate evaluation, list filtering, assertions, and table matching.

This module defines top-level predicate containers used in field pipelines:
- `Filter`: Filters list collections according to inner condition nodes.
- `Assert`: Asserts that the current value satisfies inner condition nodes, raising `SscAssertionError` on failure.
- `Match`: Table row matcher testing key conditions and mapping values.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class Filter(Node):
    """Filters a list of items according to inner predicate conditions.

    Inner conditions are joined with `AND` logic by default unless `or { ... }` is used.

    Examples:
        - KDL: `filter { starts "http"; ends ".png"; }`
        - Python: `v1 = [x for x in v if x.startswith("http") and x.endswith(".png")]`
        - JavaScript: `const v1 = v.filter(x => x.startsWith("http") && x.endsWith(".png"));`
        - Go: filter loop over slice matching predicate helper
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.STRING, is_array=True
        )
    )
    is_array: bool = True


@dataclass
class Assert(Node):
    """Validates the current pipeline value against inner conditions.

    Raises an assertion error (`SscAssertionError` / `std_assert`) if any inner predicate fails.
    Source location (`span`) and source file are embedded in the default assertion message.

    Attributes:
        message: Optional custom failure error message.

    Examples:
        - KDL: `assert "Price must be positive" { gt 0 }`
        - Python: `std_assert(v > 0, "Price must be positive")`
        - JavaScript: `sscAssert(v > 0, "Price must be positive");`
        - Go: `stdAssert(v > 0, "Price must be positive")`
    """

    message: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class Match(Node):
    """Matches table row keys against conditions to extract corresponding values.

    Iterates over rows of a `type=table` struct, applying key extraction (`@match`).
    When key satisfies all inner predicates, evaluates and returns the row's `@value`.

    Examples:
        - KDL: `match { eq "SKU" }`
        - Python: iterates over rows checking key text, returns value cell
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
