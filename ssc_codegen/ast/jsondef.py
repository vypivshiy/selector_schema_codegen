from __future__ import annotations
from dataclasses import dataclass

from .base import Node
from .types import VariableType


@dataclass
class JsonDefField(Node):
    """
    Single field in a JSON mapping definition.

    Type metadata is in ``ret_type_info`` (base, is_array, is_optional, ref, omitempty, skip).
    """

    name: str = ""
    type_name: str = ""
    alias: str = ""
    doc: str = ""


@dataclass
class JsonDef(Node):
    """
    JSON mapping definition.
    DSL: json Name { ... } / (array)json Name { ... } / json Name path="a.b" { ... }
    body: list[JsonDefField]
    """

    name: str = ""
    is_array: bool = False
    path: str = ""

    @property
    def has_alias_key(self) -> bool:
        """Whether this definition or a nested JSON definition has an alias."""
        if any(
            field.alias
            for field in self.body
            if isinstance(field, JsonDefField)
        ):
            return True
        module = self.parent
        while module is not None and not hasattr(module, "body"):
            module = module.parent
        if module is None:
            return False
        definitions = {
            node.name: node for node in module.body if isinstance(node, JsonDef)
        }
        return _has_nested_alias(self, definitions, ())


def _has_nested_alias(
    definition: JsonDef,
    definitions: dict[str, JsonDef],
    stack: tuple[str, ...],
) -> bool:
    if definition.name in stack:
        return False
    if any(
        field.alias
        for field in definition.body
        if isinstance(field, JsonDefField)
    ):
        return True
    next_stack = (*stack, definition.name)
    for field in definition.body:
        if not isinstance(field, JsonDefField):
            continue
        ref = field.type_info.ref
        nested = (
            definitions.get(ref)
            if ref and field.type_info.base == VariableType.JSON
            else None
        )
        if nested and _has_nested_alias(nested, definitions, next_stack):
            return True
    return False
