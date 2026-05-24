from __future__ import annotations
import re as _re
from dataclasses import dataclass, field
from typing import Any
from typing import cast

from .base import Node
from .types import VariableType, StructType

# Typed placeholder grammar:
#   {{ NAME ( : PRIM )? ( [] )? ( ? )? ( | STYLE )? }}
#   NAME   = [A-Za-z][A-Za-z0-9_-]*         (first char must be a letter)
#   PRIM   = str | int | float | bool       (default: str)
#   STYLE  = repeat | csv | bracket | pipe | space   (arrays only; default: repeat)
# Legacy `{{name}}` remains valid (groups 2-5 = None → str, scalar, required).
_PLACEHOLDER_RE = _re.compile(
    r"\{\{"
    r"([A-Za-z][A-Za-z0-9_-]*)"
    r"(?::(str|int|float|bool))?"
    r"(\[\])?"
    r"(\?)?"
    r"(?:\|(repeat|csv|bracket|pipe|space))?"
    r"\}\}"
)

# Widened pattern — any `{{…}}`-shaped token. Used by the linter to flag
# malformed placeholders that the strict _PLACEHOLDER_RE would silently skip.
_PLACEHOLDER_WIDE_RE = _re.compile(r"\{\{([^{}]*)\}\}")


@dataclass
class PlaceholderSpec:
    """Parsed `{{…}}` token from an @request payload."""

    name: str = ""
    type_name: str = "str"  # "str" | "int" | "float" | "bool"
    is_array: bool = False
    is_optional: bool = False
    style: str | None = None  # None == default "repeat" when is_array


def _parse_placeholder(match: "_re.Match[str]") -> PlaceholderSpec:
    return PlaceholderSpec(
        name=match.group(1),
        type_name=match.group(2) or "str",
        is_array=bool(match.group(3)),
        is_optional=bool(match.group(4)),
        style=match.group(5) or None,
    )


# ── Base struct ──────────────────────────────────────────────────────────────


@dataclass
class StructBase(Node):
    """Base class for all struct AST nodes."""

    name: str = ""
    keep_order: bool = False  # StructFlatList-specific

    @property
    def _typedef_type(self) -> StructType:
        raise NotImplementedError

    @property
    def docstring(self) -> StructDocstring:
        return self.body[0]  # type: ignore

    @property
    def request_config(self) -> RequestConfig | None:
        for node in self.body:
            if isinstance(node, RequestConfig):
                return node
        return None

    @property
    def request_configs(self) -> list[RequestConfig]:
        return [n for n in self.body if isinstance(n, RequestConfig)]

    @property
    def use_request(self) -> bool:
        return bool(self.request_configs)

    @property
    def errors(self) -> list[ErrorResponse]:
        return [n for n in self.body if isinstance(n, ErrorResponse)]


# ── Concrete struct types ────────────────────────────────────────────────────


@dataclass
class StructItem(StructBase):
    """Single object → dict. DSL: struct Name { ... }"""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.ITEM

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])


@dataclass
class StructList(StructBase):
    """Repeating elements → list[dict]. Requires @split-doc."""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.LIST

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])


@dataclass
class StructFlatList(StructBase):
    """Deduplicated scalars → list[str]."""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.FLAT

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])


@dataclass
class StructDict(StructBase):
    """Key-value map → dict[str, any]. Requires @split-doc + @key + @value."""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.DICT

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore

    @property
    def key(self) -> Key:
        return [n for n in self.body if isinstance(n, Key)][0]

    @property
    def value(self) -> Value:
        return [n for n in self.body if isinstance(n, Value)][0]

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])


@dataclass
class StructTable(StructBase):
    """HTML table → dict. Requires @table + @rows + @match + @value."""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.TABLE

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore

    @property
    def table_config(self) -> TableConfig:
        return [n for n in self.body if isinstance(n, TableConfig)][0]

    @property
    def table_row(self) -> TableRow:
        return [n for n in self.body if isinstance(n, TableRow)][0]

    @property
    def table_match_key(self) -> TableMatchKey:
        return [n for n in self.body if isinstance(n, TableMatchKey)][0]

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])


@dataclass
class StructRest(StructBase):
    """REST API endpoint namespace. Stores @request methods, no HTML parsing."""

    @property
    def _typedef_type(self) -> StructType:
        return StructType.REST

    def __post_init__(self):
        self.body.append(StructDocstring(parent=self))


# Backward-compatible alias
Struct = StructBase


# ── Struct child nodes ───────────────────────────────────────────────────────


@dataclass
class StructDocstring(Node):
    """DSL: -doc "text" """

    value: str = ""


@dataclass
class PreValidate(Node):
    """
    Validates the document before parsing begins.
    Raises error on failure (caught by fallback if present).
    DSL: -pre-validate { ... }
    accept: DOCUMENT, ret: DOCUMENT (pass-through)
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class CheckMethod(Node):
    """
    Boolean check method on the parsed class.
    DSL: @check <name> { pipeline ... }
    Runs a pipeline on the document and returns True on success, False on failure.
    Called manually by the user before parse().
    """

    name: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.BOOL)


@dataclass
class Init(Node):
    """
    Pre-computed named values cached before field parsing.
    Execution order: after PreValidate, before SplitDoc and Fields.
    DSL: -init { name { pipeline... } ... }
    body: list[InitField]
    """

    pass


@dataclass
class InitField(Node):
    """
    Single named cached pipeline inside -init.
    Referenced in Fields via Self(name=...).
    ret is resolved after pipeline is built.

    Separate node from Field — semantics differ:
    InitField is cached and reachable via Self; Field produces output.
    """

    name: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class SplitDoc(Node):
    """
    Splits document into items for list-type structs.
    DSL: -split-doc { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=list.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class Key(Node):
    """
    Key extraction pipeline for dict-type structs.
    DSL: -key { ... }
    accept: DOCUMENT, ret: STRING
    Only valid in struct type=dict.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Value(Node):
    """
    Value extraction pipeline for dict/table-type structs.
    DSL: -value { ... }
    dict:  ret can be any type.
    table: ret must be STRING.
    Only valid in struct type=dict or type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class TableConfig(Node):
    """
    Selects the table element.
    DSL: -table { ... }
    accept: DOCUMENT, ret: DOCUMENT
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class TableRow(Node):
    """
    Selects table rows.
    DSL: -row { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class TableMatchKey(Node):
    """
    Extracts key cell text from a row for match comparison.
    DSL: -match { ... }
    accept: DOCUMENT (row), ret: STRING
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class RequestConfig(Node):
    """
    Optional transport layer config for a struct.
    DSL: @request [name="suffix"] [response-path="..."] [response-join="..."]
                  [response=JsonSchema] [doc="..."] \"""...\"""

    raw_payload stores the verbatim curl or raw HTTP string (with {{placeholders}}).
    Transport normalization (curl/HTTP parse → kwargs) happens at converter stage.

    name="" (unnamed) generates fetch()/async_fetch().
    name="by-id" generates fetch_by_id()/async_fetch_by_id() (Python)
    or fetchById() (JS).

    response_schema (type=rest only): json schema name for typed 2xx response.
        Empty string = void return.
    doc (type=rest only): per-method docstring.
    """

    raw_payload: str = ""
    response_path: str = ""  # dot-notation JSON path, e.g. "payload.html"
    response_join: str = (
        ""  # join separator when response-path resolves to list[str]
    )
    name: str = ""  # method name suffix; "" = default fetch()
    response_schema: str = ""  # type=rest: json schema for 2xx body
    doc: str = ""  # type=rest: per-method docstring

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        """Unique placeholders in declaration order (dedup by name)."""
        seen: set[str] = set()
        result: list[PlaceholderSpec] = []
        for m in _PLACEHOLDER_RE.finditer(self.raw_payload):
            spec = _parse_placeholder(m)
            if spec.name not in seen:
                seen.add(spec.name)
                result.append(spec)
        return result

    @property
    def placeholder_names(self) -> list[str]:
        """Unique placeholder names in declaration order."""
        return [p.name for p in self.placeholders]


@dataclass
class ErrorResponse(Node):
    """
    Error response mapping for type=rest struct.
    DSL: @error <status> <SchemaName> [keys...] [field=value ...]

    status: HTTP status code [100..599].
    schema_name: json schema reference for deserialised error body.
    required_keys: key names that must exist in the JSON body (positional args).
        Error triggers on matching status + all keys present.
    conditions: field=value pairs checked against the parsed JSON body.
        Keys are dot-paths (e.g. "response.success", "data.0.type").
        When non-empty, the error triggers on matching status + all conditions.
    """

    status: int = 0
    schema_name: str = ""
    required_keys: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Field(Node):
    """
    Regular output field.
    DSL: field-name { pipeline... }
    ret is resolved after pipeline is built.

    For struct type=table fields, accept is set to STRING
    (the value cell produced by -value after match resolves the row).
    For all other struct types, accept defaults to DOCUMENT.
    """

    name: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class StartParse(Node):
    """Endpoint where need run parser"""

    @property
    def struct(self) -> StructBase:
        return cast(StructBase, self.parent)

    @property
    def use_split_doc(self) -> bool:
        return any(isinstance(f, SplitDoc) for f in self.struct.body)

    @property
    def use_pre_validate(self) -> bool:
        return any(isinstance(f, PreValidate) for f in self.struct.body)

    @property
    def fields(self) -> list[Field]:
        return [f for f in self.struct.body if isinstance(f, Field)]
