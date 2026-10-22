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
from .types import TypeInfo


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
