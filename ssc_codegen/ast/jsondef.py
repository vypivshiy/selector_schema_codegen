"""AST nodes for JSON schema models, projection mappings, and aliased fields.

This module defines `JsonDef` and `JsonDefField` nodes used to declare data structures
for deserializing JSON payloads in `jsonify` operations and REST HTTP responses.

### Naming Conventions and Type Disambiguation

To prevent naming collisions with parser classes or general domain models, code generators
append the `Json` suffix to generated model names (e.g. `User` -> `UserJson`, `NotFound` -> `NotFoundJson`).
"""

from __future__ import annotations
from dataclasses import dataclass

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class JsonDefField(Node):
    """Field declaration within a JSON schema mapping definition.

    Attributes:
        name: Target property name in the generated schema model.
        type_name: Raw type name string from the KDL declaration (e.g. `"int"`, `"str"`, `"User"`).
        alias: Original key or dot-notation path in the source JSON payload (`from="..."`).
            Supports nested dot-paths (e.g. `from="author.name"`, `from="data.0.id"`).
        doc: Field documentation comment.
        is_dict: Flag indicating whether this field is an inline dictionary block.
        key_type_info: TypeInfo for dictionary key if is_dict is True.
        value_type_info: TypeInfo for dictionary value if is_dict is True.

    Examples:
        - KDL: `fullName str from="full_name"`, `avatarUrl str from="profile.images.avatar"`
        - Projection: Extracts value at dot-path and maps it to `fullName` / `avatarUrl`.
    """

    name: str = ""
    type_name: str = ""
    alias: str = ""
    doc: str = ""
    is_dict: bool = False
    key_type_info: TypeInfo | None = None
    value_type_info: TypeInfo | None = None


@dataclass
class JsonDef(Node):
    """JSON schema mapping definition (`json Name { ... }`).

    Declares a strongly-typed schema model used for projecting and validating JSON payloads
    in `jsonify` operations and REST endpoint responses. Code generators should append
    the `Json` suffix (e.g. `UserJson`) to avoid name collisions with parser classes or structs.

    Attributes:
        name: Identifier of the JSON schema model (e.g. `"User"`).
        is_array: Flag indicating whether the schema represents an array of items (`(array)json`).
        is_dict: Flag indicating whether the schema represents a dictionary (`(dict)json`).
        path: Dot-notation nested path to extract from the raw JSON prior to deserialization.
        key_type_info: TypeInfo for dictionary key if is_dict is True.
        value_type_info: TypeInfo for dictionary value if is_dict is True.

    Examples:
        - KDL:
            ```kdl
            json User {
                id int
                fullName str from="user_full_name"
                city str from="address.city"
            }
            ```
        - Generated Python:
            ```python
            class UserJson(TypedDict):
                id: int
                fullName: str
                city: str
            ```
        - Generated JavaScript (JSDoc):
            ```javascript
            /**
             * @typedef {Object} UserJson
             * @property {number} id
             * @property {string} fullName
             * @property {string} city
             */
            ```
        - Generated Go:
            ```go
            type UserJson struct {
                Id       int    `json:"id"`
                FullName string `json:"user_full_name"`
                City     string `json:"city"`
            }
            ```
    """

    name: str = ""
    is_array: bool = False
    is_dict: bool = False
    path: str = ""
    key_type_info: TypeInfo | None = None
    value_type_info: TypeInfo | None = None

    @property
    def has_alias_key(self) -> bool:
        """Whether this definition or any nested JSON definitions contain aliased fields."""
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
    """Recursively check whether a JSON definition or referenced schemas contain aliased fields."""
    if definition.name in stack:
        return False
    if definition.is_dict:
        val_info = definition.value_type_info
        if val_info and val_info.base == VariableType.JSON and val_info.ref:
            nested = definitions.get(val_info.ref)
            if nested and _has_nested_alias(
                nested, definitions, (*stack, definition.name)
            ):
                return True
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
        info = field.ret_type_info
        if (field.is_dict or (info and info.is_dict)) and field.value_type_info:
            val_info = field.value_type_info
            if val_info.base == VariableType.JSON and val_info.ref:
                nested = definitions.get(val_info.ref)
                if nested and _has_nested_alias(
                    nested, definitions, next_stack
                ):
                    return True
            continue
        ref = info.ref if info else None
        nested = (
            definitions.get(ref)
            if ref and info and info.base == VariableType.JSON
            else None
        )
        if nested and _has_nested_alias(nested, definitions, next_stack):
            return True
    return False
