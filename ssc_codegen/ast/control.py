from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class Self(Node):
    """
    References a pre-computed value from -init by name.
    Must be the first operation in a Field pipeline.
    ret is resolved at AST build time from the matching InitField.ret.
    Build-time error if name not declared in -init.
    """

    name: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class Fallback(Node):
    """Catches any error in the pipeline and returns a literal value instead.

    Must be the last operation in a Field pipeline. All previously parsed ops
    are moved into ``body`` — they form the try-block.

    ``body`` ops are emitted inside the try/catch (or language equivalent).
    The visitor intercepts ``yield TRAVERSE`` from ``visit_fallback`` to walk
    ``body`` at ``depth+1`` with advancing pipeline index, then syncs the
    outer index so subsequent nodes (e.g. Return) see the correct variable.

    ret is derived from the literal type at construction time, unless
    ``ret_type_info`` is set explicitly (parser sets it to prev_ti).

    Literal types and their ret:
      int        -> INT
      float      -> FLOAT
      str        -> STRING
      bool       -> BOOL
      None       -> NULL
      list (empty []) -> STRING with is_array=True
    """

    value: Any = None
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )

    def __post_init__(self) -> None:
        if self.ret_type_info.base != VariableType.AUTO:
            # already set explicitly, skip inference
            return
        if self.value is None:
            self.ret_type_info = TypeInfo(base=VariableType.NULL)
        elif isinstance(self.value, bool):
            # bool before int — bool is subclass of int in Python
            self.ret_type_info = TypeInfo(base=VariableType.BOOL)
        elif isinstance(self.value, int):
            self.ret_type_info = TypeInfo(base=VariableType.INT)
        elif isinstance(self.value, float):
            self.ret_type_info = TypeInfo(base=VariableType.FLOAT)
        elif isinstance(self.value, str):
            self.ret_type_info = TypeInfo(base=VariableType.STRING)
        elif isinstance(self.value, list):
            self.ret_type_info = TypeInfo(
                base=VariableType.STRING, is_array=True
            )
            self.is_array = True


@dataclass
class Return(Node):
    """
    Implicit last node of every pipeline.
    Not written in DSL — inserted by the builder after the last op.
    Carries the final ret_type of the pipeline.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
