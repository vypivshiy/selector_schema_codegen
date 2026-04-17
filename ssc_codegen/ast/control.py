from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .base import Node
from .types import VariableType


@dataclass
class Self(Node):
    """
    References a pre-computed value from -init by name.
    Must be the first operation in a Field pipeline.
    ret is resolved at AST build time from the matching InitField.ret.
    Build-time error if name not declared in -init.
    """

    name: str = ""
    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class Fallback(Node):
    """
    Catches any error in the pipeline and returns a literal value instead.
    Must be the last operation in a Field pipeline.
    ret is derived from the literal type at construction time.

    Literal types and their ret:
      int        → INT
      float      → FLOAT
      str        → STRING
      bool       → BOOL
      None       → NULL
      list (empty []) → LIST_STRING
    """

    value: Any = None
    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)

    def __post_init__(self) -> None:
        if self.ret != VariableType.AUTO:
            # already set explicitly, skip inference
            return
        if self.value is None:
            self.ret = VariableType.NULL
        elif isinstance(self.value, bool):
            # bool before int — bool is subclass of int in Python
            self.ret = VariableType.BOOL
        elif isinstance(self.value, int):
            self.ret = VariableType.INT
        elif isinstance(self.value, float):
            self.ret = VariableType.FLOAT
        elif isinstance(self.value, str):
            self.ret = VariableType.STRING
        elif isinstance(self.value, list):
            self.ret = VariableType.LIST_STRING


@dataclass
class FallbackStart(Fallback):
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class FallbackEnd(Fallback):
    pass


@dataclass
class Return(Node):
    """
    Implicit last node of every pipeline.
    Not written in DSL — inserted by the builder after the last op.
    Carries the final ret_type of the pipeline.
    """

    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)
