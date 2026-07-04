"""AST nodes for REST result artifacts.

Synthesized from ``StructRest`` by ``core/rest_artifacts.py`` and inserted
into ``Module.body`` before the struct — mirroring how ``TypeDef`` is
synthesized from ``Struct`` by ``core/expressions.py``.

Each node is a leaf declaration (no walkable body); the visitor emits one
block per node.  This replaces the procedural ``emit_*`` functions that used
to run inside ``visit_struct_rest``.

  ResultVariantDef  → per-error ``@dataclass class XErr(Err[T])``
  ResultAliasDef    → per-method ``Name = Union[Ok[T], *Errs, ...]``
  MatcherListDef    → per-struct ``_x_matchers = [ErrMatcher(...), ...]``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Node


@dataclass
class ResultVariantDef(Node):
    """One error subclass declaration.

    Synthesized from a unique ``ErrorResponse`` on a ``StructRest``.
    Carries RAW schema reference (name + array flag); each target-language
    visitor renders the value-type spelling ("Any"/"XJson"/"List[XJson]"
    vs "*"/"XJson"/"Array<XJson>").
    """

    name: str = ""  # "UsersClient404Err"
    status: int = 0
    schema_name: str = ""  # raw JsonDef name, "" → no schema
    schema_is_array: bool = False


@dataclass
class ResultAliasDef(Node):
    """One per-method result union alias.

    Synthesized from a ``MethodRest``.  The matching ``MethodRest`` gets its
    ``result_alias_name`` field set to this node's ``name`` so the visitor
    can reference the alias in the method signature.  Carries RAW response
    schema reference (name + array flag); visitors render the Ok payload type.
    """

    name: str = ""  # "GetUserResult"
    response_schema: str = ""  # raw JsonDef name, "" → void
    response_is_array: bool = False
    err_variants: list[str] = field(default_factory=list)


@dataclass
class MatcherEntry:
    """One ``ErrMatcher(...)`` entry inside a ``MatcherListDef``.

    Carries RAW condition data so each target-language visitor renders the
    check expression in its own spelling (Python ``lambda _b: ...`` vs JS
    ``(_b) => ...``).  Plain dataclass (not a ``Node``) — consumed inline by
    the matcher-list visitor, no dedicated ``visit_*`` method.
    """

    status: int
    required_keys: list[str]  # keys that must exist in the JSON body
    conditions: dict[str, Any]  # path=value checks against the JSON body
    factory_name: str  # ResultVariantDef.name to construct on match


@dataclass
class MatcherListDef(Node):
    """Per-struct matchers list.

    Synthesized once per ``StructRest`` from its unique errors.  Carries the
    raw struct name; each visitor renders the var-name spelling
    (``_x_matchers`` in Python, ``_xMatchers`` in JS).
    """

    struct_name: str = ""
    entries: list[MatcherEntry] = field(default_factory=list)
