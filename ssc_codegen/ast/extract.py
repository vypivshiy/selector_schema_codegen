from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType


@dataclass
class Text(Node):
    """
    Extracts text content from element(s).
    DOCUMENT → STRING, LIST_DOCUMENT → LIST_STRING.
    accept/ret set by builder from cursor type.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Raw(Node):
    """
    Extracts raw HTML string from element(s).
    DOCUMENT → STRING, LIST_DOCUMENT → LIST_STRING.
    accept/ret set by builder from cursor type.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Attr(Node):
    """
    Extracts attribute value(s) from element(s).

    Single key:
      - DOCUMENT → STRING (error if attribute not found)
      - LIST_DOCUMENT → LIST_STRING (error if attribute not found)

    Multiple keys:
      - always returns LIST_STRING
      - missing attributes are skipped silently
      - DOCUMENT → LIST_STRING, LIST_DOCUMENT → LIST_STRING

    accept/ret set by builder from cursor type and len(keys).
    """

    keys: tuple[str, ...] = field(default_factory=tuple)
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)
