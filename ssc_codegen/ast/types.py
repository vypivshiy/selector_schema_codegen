from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum, auto


class VariableType(IntEnum):
    """Primitive and structural data types supported by the AST and pipelines.

    Attributes:
        AUTO: Type to be inferred automatically during AST construction/type checking.
        DOCUMENT: HTML/XML DOM document or element node.
        STRING: Text string value.
        INT: Integer numeric value (targets typically represent this as signed 64-bit integer `int64` / `int`).
        FLOAT: Floating-point numeric value (targets typically represent this as IEEE 754 64-bit float `float64` / `number`).
        BOOL: Boolean truth value (`bool` / `boolean`).
        NULL: Null / None / nil value.
        NESTED: Result of parsing via a nested struct parser.
        JSON: Deserialized typed JSON object or model.
    """

    AUTO = auto()
    DOCUMENT = auto()
    STRING = auto()
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    NULL = auto()
    NESTED = auto()
    JSON = auto()


VT = VariableType


@dataclass(frozen=True)
class TypeInfo:
    """Unified type specification container.

    Carries base primitive type, modifiers (array, optional), reference names,
    and serialization hints. Target-language rendering is performed by backend visitors.

    Attributes:
        base: Primary variable type category.
        is_array: Flag indicating whether this type is a list/array of items.
        is_optional: Flag indicating whether the value may be null or omitted.
        ref: Referenced struct or JSON schema name for `NESTED` and `JSON` types.
        omitempty: Flag indicating that the field key may be absent from JSON payloads.
        skip: Flag indicating that the field is parsed internally but omitted from public output.
    """

    base: VariableType  # STRING, INT, FLOAT, BOOL, NULL, NESTED, JSON, DOCUMENT, AUTO
    is_array: bool = False
    is_optional: bool = False
    ref: str | None = None  # raw struct/JsonDef name — converter adds suffix
    omitempty: bool = False  # @omitempty — key may be absent from JSON
    skip: bool = False  # @skip — field parsed but excluded from output

    @property
    def is_list(self) -> bool:
        """Alias for is_array."""
        return self.is_array

    @property
    def is_ref(self) -> bool:
        """True if the type references a named struct or JSON schema."""
        return self.base in (VT.NESTED, VT.JSON) and self.ref is not None


class StructType(IntEnum):
    """Structural parsing strategies and generator templates for structs.

    Attributes:
        ITEM: Single object parser yielding a dictionary/struct of fields.
        LIST: Repeating elements parser yielding a list of parsed item dictionaries.
        DICT: Dynamic key-value dictionary parser.
        TABLE: Tabular data parser matching row keys to extract corresponding values.
        FLAT: Single list parser extracting flat scalar elements.
        REST: REST API client container declaring HTTP endpoints and typed response models.
        RAW: Raw plain text extraction parser.
    """

    ITEM = auto()
    LIST = auto()
    DICT = auto()
    TABLE = auto()
    FLAT = auto()
    REST = auto()
    RAW = auto()
