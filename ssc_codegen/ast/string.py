from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType

# All string nodes (except Split and Join) support map semantics:
# STRING → STRING, LIST_STRING → LIST_STRING.
# accept/ret are set by the builder from cursor type.


@dataclass
class Trim(Node):
    """Strips leading and trailing whitespace."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
    substr: str = ""


@dataclass
class Ltrim(Node):
    """Strips leading whitespace."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
    substr: str = ""


@dataclass
class Rtrim(Node):
    """Strips trailing whitespace."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
    substr: str = ""


@dataclass
class NormalizeSpace(Node):
    """Collapses inner whitespace to single space, then trims."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class RmPrefix(Node):
    """Removes prefix substr if present."""

    substr: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class RmSuffix(Node):
    """Removes suffix substr if present."""

    substr: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class RmPrefixSuffix(Node):
    """Removes both prefix and suffix substr if present."""

    substr: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Fmt(Node):
    """
    Formats string using template.
    {{}} is replaced with the current value.
    template may be a define name — substituted at parse time.
    """

    template: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Repl(Node):
    """Replaces all occurrences of old with new."""

    old: str = ""
    new: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class ReplMap(Node):
    """
    Replaces multiple substrings via a mapping.
    DSL map form:
      repl {
        "old1" "new1"
        "old2" "new2"
      }
    """

    replacements: dict[str, str] = field(default_factory=dict)
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Lower(Node):
    """Converts to lowercase."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Upper(Node):
    """Converts to uppercase."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Split(Node):
    """
    Splits string into list by separator.
    STRING → LIST_STRING always (no map semantics).
    """

    sep: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.LIST_STRING)


@dataclass
class Join(Node):
    """
    Joins list into single string by separator.
    LIST_STRING → STRING always.
    """

    sep: str = ""
    accept: VariableType = field(default=VariableType.LIST_STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Unescape(Node):
    """Unescapes HTML entities and unicode escapes."""

    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
