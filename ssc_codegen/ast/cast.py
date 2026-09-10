"""AST nodes for scalar type casting, JSON deserialization, and struct nesting.

This module defines data conversion operations within field pipelines:
- `ToInt`: Casts string/numeric values to 64-bit integer (`int` / `int64`).
- `ToFloat`: Casts string/numeric values to 64-bit float (`float` / `float64`).
- `ToBool`: Converts input to a boolean truth value.
- `Jsonify`: Deserializes JSON string into a strongly-typed `JsonDef` model with key remapping.
- `Nested`: Instantiates another parser struct passing current DOM element and invokes `.parse()`.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class ToInt(Node):
    """Casts string or numeric values directly to integers.

    Validation of the input format is not performed prior to casting; the operation directly
    attempts conversion and is allowed to fail with a runtime error (e.g. `ValueError` in Python,
    `NaN` / `parseInt` error in JS, `strconv.Atoi` error in Go) unless protected by a `Fallback` node.

    Examples:
        - KDL: `to-int`
        - Python: `v1 = int(v)`
        - JavaScript: `const v1 = parseInt(v, 10);`
        - Go: `v1, _ := strconv.Atoi(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.INT)
    )


@dataclass
class ToFloat(Node):
    """Casts string or numeric values directly to floating-point numbers.

    Validation of the input format is not performed prior to casting; the operation directly
    invokes standard target language float parsing and may raise a runtime error unless
    handled by `Fallback`.

    Examples:
        - KDL: `to-float`
        - Python: `v1 = float(v)`
        - JavaScript: `const v1 = parseFloat(v);`
        - Go: `v1, _ := strconv.ParseFloat(v, 64)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.FLOAT)
    )


@dataclass
class ToBool(Node):
    """Casts input values to boolean truth values.

    Scalar values are cast using standard truthiness rules of the target language.

    Examples:
        - KDL: `to-bool`
        - Python: `v1 = bool(v)`
        - JavaScript: `const v1 = Boolean(v);`
        - Go: `v1 := bool(len(v) > 0)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.BOOL)
    )


@dataclass
class Jsonify(Node):
    """Deserializes a JSON string into a structured model per a `JsonDef` schema.

    Parses JSON text into an object or array. If `path` is specified, extracts the nested
    sub-tree first. If the referenced `JsonDef` contains field aliases (`from="..."`),
    remapping logic is executed to project keys into canonical schema properties.
    Allowed to fail with a JSON parsing error if input is malformed.

    Attributes:
        schema_name: Identifier of the target `JsonDef` mapping schema.
        path: Optional dot-notation path to extract from the parsed JSON before schema projection.

    Examples:
        - KDL: `jsonify User`, `jsonify Article path="data.item"`
        - Python: `v1 = json.loads(v)` + `ssc_remap_json_keys(v1, ...)`
        - JavaScript: `const v1 = sscRemapJsonKeys(JSON.parse(v), ...);`
        - Go: `var v1 UserJson; json.Unmarshal([]byte(v), &v1)`
    """

    schema_name: str = ""
    path: str | None = None
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.JSON)
    )


@dataclass
class Nested(Node):
    """Passes the current document to another struct parser and returns its result.

    Instantiates the target parser struct passing the current DOM element as the root document,
    then executes its `.parse()` entry point.

    Attributes:
        struct_name: Identifier of the target parser struct.

    Examples:
        - KDL: `nested AuthorInfo`
        - Python: `v1 = AuthorInfo(v).parse()`
        - JavaScript: `const v1 = new AuthorInfo(v).parse();`
        - Go: `v1 := NewAuthorInfo(v).Parse()`
    """

    struct_name: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.NESTED)
    )
