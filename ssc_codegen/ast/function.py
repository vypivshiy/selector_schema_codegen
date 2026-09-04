"""AST nodes for module-level standalone parsing and transformation functions.

This module defines `FunctionDef` nodes representing top-level functions declared via `fn`
(operating on DOM documents) or `(raw)fn` (operating on raw strings).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class FunctionDef(Node):
    """Standalone module-level extraction function declaration (`fn` / `(raw)fn`).

    Attributes:
        name: Function identifier name.
        is_raw: Flag indicating whether function operates on raw text (`STRING`) rather than DOM (`DOCUMENT`).
        doc: Docstring documentation for the function.
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
