from __future__ import annotations

from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class FunctionDef(Node):
    """Module-level single-value extraction function.

    DSL: ``fn <name> { pipeline }`` or ``(raw)fn <name> { pipeline }``.

    Generates a standalone function instead of a class.
    ``is_raw`` selects the document type: HTML (DOCUMENT) or plain text (STRING).
    ``ret_type_info`` is resolved after pipeline build (AUTO → concrete type).
    """

    name: str = ""
    is_raw: bool = False
    doc: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
