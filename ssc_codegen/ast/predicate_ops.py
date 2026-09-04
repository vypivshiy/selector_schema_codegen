"""AST operator nodes for scalar, DOM, and collection condition evaluation.

This module defines predicate operations evaluated inside `Filter`, `Assert`, `Match`, and `@check`:
- Comparisons: `PredEq`, `PredNe`, `PredGt`, `PredLt`, `PredGe`, `PredLe`, `PredRange`.
- String & Regex checks: `PredStarts`, `PredEnds`, `PredContains`, `PredIn`, `PredRe`, `PredReAny`, `PredReAll`.
- DOM & Attribute checks: `PredCss`, `PredXpath`, `PredHasAttr`, `PredAttr*`, `PredText*`.
- Collection size checks: `PredCount*`.
- Logical combinators: `LogicNot`, `LogicAnd`, `LogicOr`.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node


# =============================================================================
# Comparison
# =============================================================================


@dataclass
class PredEq(Node):
    """Checks if value equals any of the specified target values.

    Attributes:
        values: Tuple of candidate string or integer literal values (OR semantics).
    """

    values: tuple[str | int, ...] = field(default_factory=tuple)


@dataclass
class PredNe(Node):
    """Checks if value does not equal any of the specified values.

    Attributes:
        values: Tuple of disallowed string or integer literal values.
    """

    values: tuple[str | int, ...] = field(default_factory=tuple)


# =============================================================================
# String predicates
# =============================================================================


@dataclass
class PredStarts(Node):
    """Checks if string starts with any of the candidate prefixes.

    Attributes:
        values: Tuple of prefix candidate strings (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredEnds(Node):
    """Checks if string ends with any of the candidate suffixes.

    Attributes:
        values: Tuple of suffix candidate strings (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredContains(Node):
    """Checks if string contains any of the specified substrings.

    Attributes:
        values: Tuple of substring candidates (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


# =============================================================================
# Regex
# =============================================================================


@dataclass
class PredRe(Node):
    """Tests if string matches the regular expression pattern.

    Attributes:
        pattern: Regular expression pattern string.
    """

    pattern: str = ""


@dataclass
class PredReAny(Node):
    """Asserts that at least one item in a list matches the regex pattern.

    Attributes:
        pattern: Regular expression pattern string.
    """

    pattern: str = ""


@dataclass
class PredReAll(Node):
    """Asserts that all items in a list match the regex pattern.

    Attributes:
        pattern: Regular expression pattern string.
    """

    pattern: str = ""


# =============================================================================
# Document
# =============================================================================


@dataclass
class PredCss(Node):
    """Tests if the document element contains a child matching the CSS selector.

    Attributes:
        query: CSS selector query string.
    """

    query: str = ""


@dataclass
class PredXpath(Node):
    """Tests if the document element contains a child matching the XPath query.

    Attributes:
        query: XPath query string.
    """

    query: str = ""


@dataclass
class PredHasAttr(Node):
    """Tests if the element has any of the specified attribute names.

    Attributes:
        attrs: Tuple of attribute names to test (OR semantics).
    """

    attrs: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrEq(Node):
    """Tests if element attribute value equals any expected value.

    Attributes:
        name: Name of the attribute to test.
        values: Tuple of acceptable attribute string values (OR semantics).
    """

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrNe(Node):
    """Tests if element attribute value does not equal any disallowed value.

    Attributes:
        name: Name of the attribute to test.
        values: Tuple of disallowed attribute string values (AND semantics).
    """

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrStarts(Node):
    """Tests if element attribute value starts with any candidate prefix.

    Attributes:
        name: Name of the attribute to test.
        values: Tuple of prefix candidates (OR semantics).
    """

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrEnds(Node):
    """Tests if element attribute value ends with any candidate suffix.

    Attributes:
        name: Name of the attribute to test.
        values: Tuple of suffix candidates (OR semantics).
    """

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrContains(Node):
    """Tests if element attribute value contains any specified substring.

    Attributes:
        name: Name of the attribute to test.
        values: Tuple of substring candidates (OR semantics).
    """

    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredAttrRe(Node):
    """Tests if element attribute value matches a regular expression pattern.

    Attributes:
        name: Name of the attribute to test.
        pattern: Regular expression pattern string.
    """

    name: str = ""
    pattern: str = ""


@dataclass
class PredTextStarts(Node):
    """Tests if element inner text starts with any candidate prefix.

    Attributes:
        values: Tuple of prefix candidates (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextEnds(Node):
    """Tests if element inner text ends with any candidate suffix.

    Attributes:
        values: Tuple of suffix candidates (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextContains(Node):
    """Tests if element inner text contains any specified substring.

    Attributes:
        values: Tuple of candidate substrings (OR semantics).
    """

    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PredTextRe(Node):
    """Tests if element inner text matches a regular expression pattern.

    Attributes:
        pattern: Regular expression pattern string.
    """

    pattern: str = ""


# =============================================================================
# List (assert only)
# =============================================================================


@dataclass
class PredCountEq(Node):
    """Asserts that list length equals the specified count.

    Attributes:
        value: Expected element count.
    """

    value: int = 0


@dataclass
class PredCountGt(Node):
    """Asserts that list length is strictly greater than the threshold.

    Attributes:
        value: Exclusive lower bound on element count.
    """

    value: int = 0


@dataclass
class PredCountLt(Node):
    """Asserts that list length is strictly less than the threshold.

    Attributes:
        value: Exclusive upper bound on element count.
    """

    value: int = 0


@dataclass
class PredCountNe(Node):
    """Asserts that list length is not equal to the specified count.

    Attributes:
        value: Disallowed element count.
    """

    value: int = 0


@dataclass
class PredCountGe(Node):
    """Asserts that list length is greater than or equal to the minimum.

    Attributes:
        value: Inclusive minimum element count.
    """

    value: int = 0


@dataclass
class PredCountLe(Node):
    """Asserts that list length is less than or equal to the maximum.

    Attributes:
        value: Inclusive maximum element count.
    """

    value: int = 0


@dataclass
class PredCountRange(Node):
    """Asserts that list length falls within the exclusive range `(start, end)`.

    Attributes:
        start: Exclusive lower bound.
        end: Exclusive upper bound.
    """

    start: int = 0
    end: int = 0


# =============================================================================
# Logic
# =============================================================================


@dataclass
class LogicNot(Node):
    """Inverts the boolean evaluation result of wrapped predicate conditions."""

    pass


@dataclass
class LogicAnd(Node):
    """Explicit conjunction grouping (`AND`) of inner predicate conditions."""

    pass


@dataclass
class LogicOr(Node):
    """Disjunction grouping (`OR`) of inner predicate conditions."""

    pass
