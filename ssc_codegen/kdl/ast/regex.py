from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType

# Re and ReSub support map semantics:
# STRING → STRING, LIST_STRING → LIST_STRING.
# accept/ret are set by the builder from cursor type.
#
# ReAll is scalar-only: STRING → LIST_STRING.
#
# ignore_case / dotall are extracted from re.Pattern defines at parse time
# and stored as explicit flags so codegen can emit them without inline (?i)(?s).


@dataclass
class Re(Node):
    """
    Returns first regex match per element.
    Map semantics: STRING → STRING, LIST_STRING → LIST_STRING.
    pattern may be a define name — substituted at parse time.
    Pattern is always normalized to inline form with (?i) and (?s) flags if needed.
    """

    pattern: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class ReAll(Node):
    """
    Returns all regex matches as a list.
    Scalar input only: STRING → LIST_STRING.
    pattern may be a define name — substituted at parse time.
    Pattern is always normalized to inline form with (?i) and (?s) flags if needed.
    """

    pattern: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.LIST_STRING)


@dataclass
class ReSub(Node):
    """
    Replaces all regex matches with repl per element.
    Map semantics: STRING → STRING, LIST_STRING → LIST_STRING.
    pattern may be a define name — substituted at parse time.
    Pattern is always normalized to inline form with (?i) and (?s) flags if needed.
    """

    pattern: str = ""
    repl: str = ""
    accept: VariableType = field(default=VariableType.STRING)
    ret: VariableType = field(default=VariableType.STRING)
