from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node


# =============================================================================
# Comparison
# =============================================================================


@dataclass
class PredEq(Node):
    """
    Equals any of values.
    int value → compare string length.
    Multiple values use OR semantics.
    """

    values: tuple[str | int, ...] = field(default_factory=tuple)


@dataclass
class PredNe(Node):
    """
    Not equals any of values.
    int value → compare string length.
    Multiple values use OR semantics.
    """

    values: tuple[str | int, ...] = field(default_factory=tuple)


@dataclass
class PredGt(Node):
    """len > value"""

    value: int = 0


@dataclass
class PredLt(Node):
    """len < value"""

    value: int = 0


@dataclass
class PredGe(Node):
    """len >= value"""

    value: int = 0


@dataclass
class PredLe(Node):
    """len <= value"""

    value: int = 0


@dataclass
class PredRange(Node):
    """start < len < end. Shortcut for PredGt + PredLt."""

    start: int = 0
    end: int = 0


# =============================================================================
# String predicates
# =============================================================================


@dataclass
class PredStarts(Node):
    """str.startswith any of values. Multiple values use OR."""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredEnds(Node):
    """str.endswith any of values. Multiple values use OR."""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredContains(Node):
    """any of values in str. Multiple values use OR."""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredIn(Node):
    """str must equal one of values."""

    values: tuple[str, ...] = field(default_factory=tuple)


# =============================================================================
# Regex
# =============================================================================


@dataclass
class PredRe(Node):
    """Element matches pattern."""

    pattern: str = ""


@dataclass
class PredReAny(Node):
    """At least one element in list matches pattern. Assert only."""

    pattern: str = ""


@dataclass
class PredReAll(Node):
    """All elements in list match pattern. Assert only."""

    pattern: str = ""


# =============================================================================
# Document
# =============================================================================


@dataclass
class PredCss(Node):
    """Element contains a child matching CSS query."""

    query: str = ""


@dataclass
class PredXpath(Node):
    """Element contains a child matching XPath query."""

    query: str = ""


@dataclass
class PredHasAttr(Node):
    """Element has the named attribute. Multiple converts OR"""

    attrs: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrEq(Node):
    """Element attr equal. Multiple converts OR"""

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrNe(Node):
    """Element attr equal. Multiple converts AND"""

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrStarts(Node):
    """Element attr value startswith. Multiple converts OR"""

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrEnds(Node):
    """Element attr value startswith. Multiple converts OR"""

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrContains(Node):
    """Element attr value contains. Multiple converts OR"""

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrRe(Node):
    """Element attr value match"""

    name: str = ""
    pattern: str = ""
    ignore_case: bool = False
    dotall: bool = False


@dataclass
class PredTextStarts(Node):
    """Element text starts. Multiple converts OR"""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextEnds(Node):
    """Element text ends. Multiple converts OR"""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextContains(Node):
    """Element text contains. Multiple converts OR"""

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextRe(Node):
    """Element text match"""

    pattern: str = ""
    ignore_case: bool = False
    dotall: bool = False


# =============================================================================
# List (assert only)
# =============================================================================


@dataclass
class PredCountEq(Node):
    """len(list) == value. Assert only."""

    value: int = 0


@dataclass
class PredCountGt(Node):
    """len(list) > value. Assert only."""

    value: int = 0


@dataclass
class PredCountLt(Node):
    """len(list) < value. Assert only."""

    value: int = 0


# =============================================================================
# Logic
# =============================================================================


@dataclass
class LogicNot(Node):
    """Inverts result of inner predicate block."""

    pass


@dataclass
class LogicAnd(Node):
    """Explicit AND grouping (default behaviour when no logic op is specified)."""

    pass


@dataclass
class LogicOr(Node):
    """OR grouping."""

    pass
