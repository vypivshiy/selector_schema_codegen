"""AST nodes for array and list collection operations.

This module defines nodes operating on lists of elements (`is_array=True`):
- `Index`: Extracts a single element at a 0-based offset (`first`, `last`, `index N`).
- `Slice`: Extracts a sublist slice `[start:end]`.
- `Len`: Returns the integer count of elements in a list.
- `Unique`: Deduplicates elements in a list with optional order preservation (`keep_order`).
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType

# Index, First, Last, Slice accept LIST_AUTO / return AUTO or LIST_AUTO.
# Concrete types are resolved by the builder from the cursor type via
# VariableType.scalar / VariableType.as_list helpers.


@dataclass
class Index(Node):
    """Extracts a single element from a list by its index position.

    Index is 0-based; negative indices count backwards from the end of the list (`-1` is the last item).
    Target-specific backends without native negative or 0-based indexing must adapt expressions
    accordingly during code generation (e.g. converting negative index `-k` to `len(arr) - k`,
    or adding `+1` for 1-based index targets).

    Attributes:
        i: Zero-based integer index (negative values index backwards from the end).

    Examples:
        - KDL: `index 0`, `first`, `last`
        - Python: `v1 = v[0]`, `v1 = v[-1]`
        - JavaScript: `const v1 = v[0];`, `const v1 = v[v.length - 1];`
        - Go: `v1 := v[0]`, `v1 := v[len(v)-1]`
    """

    i: int = 0
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class Slice(Node):
    """Extracts a sublist slice from start to end index `[start:end]`.

    Indices are 0-based with half-open interval semantics `[start, end)`. Negative values
    count backwards from the end of the collection. Backend codegen must adapt boundary
    calculations to target language slice conventions.

    Attributes:
        start: Starting index of the slice (0-based, inclusive).
        end: Ending index of the slice (0-based, exclusive).

    Examples:
        - KDL: `slice 0 5`
        - Python: `v1 = v[0:5]`
        - JavaScript: `const v1 = v.slice(0, 5);`
        - Go: `v1 := v[0:5]`
    """

    start: int = 0
    end: int = 0
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO, is_array=True)
    )
    is_array: bool = True


@dataclass
class Len(Node):
    """Calculates the number of elements in a list.

    Examples:
        - KDL: `len`
        - Python: `v1 = len(v)`
        - JavaScript: `const v1 = v.length;`
        - Go: `v1 := len(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.INT)
    )


@dataclass
class Unique(Node):
    """Deduplicates string elements in a list.

    When `keep_order=True`, the generator preserves the first-seen item order (e.g. `list(dict.fromkeys(v))`
    in Python or helper in Go). When `keep_order=False`, backends may use faster unordered deduplication
    (e.g. `list(set(v))` if target language optimizes set conversion).

    Attributes:
        keep_order: Flag indicating whether to preserve the original element order.

    Examples:
        - KDL: `unique`
        - Python (keep_order=True): `v1 = list(dict.fromkeys(v))`
        - Python (keep_order=False): `v1 = list(set(v))`
        - JavaScript: `const v1 = Array.from(new Set(v));`
        - Go: `v1 := stdUnique(v)`
    """

    keep_order: bool = False
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.STRING, is_array=True
        )
    )
    is_array: bool = True
