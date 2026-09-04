"""AST nodes for synthesized type definitions and data shape models.

This module defines `TypeDef` and `TypeDefField` nodes synthesized from parsing structs
(`Struct`) by `core/expressions.py:typedef_from_struct`.

### Naming Conventions and Conflict Disambiguation

When generating code, the parser class and its output data type must not collide:
- **Parser class**: Named directly after the struct (e.g. `Product`, `Catalog`).
- **Output data model (`TypeDef`)**: Generated with a suffix `Type` (e.g. `ProductType`, `CatalogType`)
  or `Item` to avoid shadowing the parser class in Python (`TypedDict`), JavaScript (`@typedef`),
  and Go (`struct`).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast

from .base import Node
from .types import StructType


@dataclass
class TypeDefField(Node):
    r"""Field declaration within a synthesized type definition model.

    Attributes:
        name: Name of the property in the type model.

    Examples:
        - Python: `title: str`
        - JavaScript (JSDoc): `@property {string} title`
        - Go: `Title string \`json:"title"\``
    """

    name: str = ""

    @property
    def typedef(self) -> "TypeDef":
        """Reference to the parent `TypeDef` AST node."""
        return self.parent  # type: ignore


@dataclass
class TypeDef(Node):
    """Synthesized type annotation model (e.g. `TypedDict` / JSDoc `@typedef` / Go struct).

    Synthesized from `Struct` nodes to declare the shape of the data returned by the `parse()` method.
    Code generators should append the `Type` suffix (e.g. `ProductType`) to prevent naming collisions
    with the parser class `Product`.

    Attributes:
        name: Identifier of the generated type definition model (e.g. `"Product"`).
        struct_type: Struct parsing flavor associated with this model (`ITEM`, `LIST`, `DICT`, etc.).

    Examples:
        - Python:
            ```python
            class ProductType(TypedDict):
                title: str
                price: int
            ```
        - JavaScript (JSDoc):
            ```javascript
            /**
             * @typedef {Object} ProductType
             * @property {string} title
             * @property {number} price
             */
            ```
        - Go:
            ```go
            type ProductType struct {
                Title string `json:"title"`
                Price int    `json:"price"`
            }
            ```
    """

    name: str = ""
    struct_type: StructType = StructType.ITEM

    @property
    def fields(self) -> list[TypeDefField]:
        """List of child `TypeDefField` nodes."""
        return cast(list[TypeDefField], self.body)
