from __future__ import annotations
import re as _re
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable
from typing import cast

from .base import Node
from .types import TypeInfo, VariableType, StructType

# Typed placeholder grammar:
#   {{ NAME ( : PRIM )? ( [] )? ( ? )? ( | STYLE )? }}
#   NAME   = [A-Za-z][A-Za-z0-9_-]*         (first char must be a letter)
#   PRIM   = str | int | float | bool       (default: str)
#   STYLE  = repeat | csv | bracket | pipe | space   (arrays only; default: repeat)
# Legacy `{{name}}` remains valid (groups 2-5 = None → str, scalar, required).
PLACEHOLDER_RE = _re.compile(
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
PLACEHOLDER_WIDE_RE = _re.compile(r"\{\{([^{}]*)\}\}")


@dataclass
class PlaceholderSpec:
    """Parsed `{{...}}` token from an @request payload.

    All placeholder parsing goes through these methods so the regex stays
    an internal implementation detail of this module.
    """

    name: str = ""
    type_name: str = "str"  # "str" | "int" | "float" | "bool"
    is_array: bool = False
    is_optional: bool = False
    style: str | None = None  # None == default "repeat" when is_array

    # ── parsing ──────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, text: str) -> PlaceholderSpec | None:
        """Parse *text* that is exactly one placeholder (``{{name:int[]?|csv}}``).

        Returns ``None`` when *text* is not a valid placeholder.
        """
        m = PLACEHOLDER_RE.fullmatch(text)
        return parse_placeholder(m) if m else None

    @staticmethod
    def find_all(text: str) -> list[PlaceholderSpec]:
        """Return every placeholder found in *text*, in order of appearance."""
        return [parse_placeholder(m) for m in PLACEHOLDER_RE.finditer(text)]

    @staticmethod
    def search(text: str) -> bool:
        """True when *text* contains at least one placeholder."""
        return PLACEHOLDER_RE.search(text) is not None

    @staticmethod
    def match_at(text: str, pos: int) -> tuple[int, PlaceholderSpec] | None:
        """Try to match a placeholder at *pos*.

        Returns ``(end_pos, spec)`` on success, ``None`` otherwise.
        """
        m = PLACEHOLDER_RE.match(text, pos)
        if m is None:
            return None
        return m.end(), parse_placeholder(m)

    # ── substitution ─────────────────────────────────────────────────────

    @staticmethod
    def sub(
        text: str, replacement: "str | Callable[[PlaceholderSpec], str]"
    ) -> str:
        """Replace every placeholder in *text*.

        *replacement* may be a literal string or a callable receiving the
        parsed ``PlaceholderSpec`` and returning the replacement string.
        """
        if callable(replacement):
            return PLACEHOLDER_RE.sub(
                lambda m: replacement(parse_placeholder(m)), text
            )
        return PLACEHOLDER_RE.sub(replacement, text)

    @staticmethod
    def rename(text: str, mapping: dict[str, str]) -> str:
        """Rename placeholder names per *mapping*, preserving all modifiers.

        ``mapping`` maps old name → new name.  Unmapped names are left as-is.
        """

        def _repl(m: "_re.Match[str]") -> str:
            new_name = mapping.get(m.group(1), m.group(1))
            type_part = f":{m.group(2)}" if m.group(2) else ""
            array_part = m.group(3) or ""
            optional_part = m.group(4) or ""
            style_part = f"|{m.group(5)}" if m.group(5) else ""
            return (
                "{{"
                + new_name
                + type_part
                + array_part
                + optional_part
                + style_part
                + "}}"
            )

        return PLACEHOLDER_RE.sub(_repl, text)


def parse_placeholder(match: "_re.Match[str]") -> PlaceholderSpec:
    return PlaceholderSpec(
        name=match.group(1),
        type_name=match.group(2) or "str",
        is_array=bool(match.group(3)),
        is_optional=bool(match.group(4)),
        style=match.group(5) or None,
    )


# ── Request/Method nodes ──────────────────────────────────────────────────────


def _iter_http_strings(http: RequestHttp):
    """Yield every string value that may contain placeholders."""
    yield http.url
    yield from http.headers.values()
    yield from http.cookies.values()
    yield from http.params.values()
    if isinstance(http.body, str) and http.body:
        yield http.body
    elif isinstance(http.body, dict):
        yield from _iter_dict_strings(http.body)


def _iter_dict_strings(d: dict):
    for v in d.values():
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            yield from _iter_dict_strings(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    yield item


@dataclass
class RequestHttp(Node):
    """Parsed HTTP request — child node of MethodBase.

    Created once at parse time from ``parse_to_spec(raw_payload)``;
    converters read fields directly instead of re-parsing raw_payload.
    """

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body_kind: str = "empty"  # "empty" | "json" | "form" | "raw"
    body: str | dict | None = None

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        """Unique placeholders across all string fields."""
        seen: set[str] = set()
        result: list[PlaceholderSpec] = []
        for text in _iter_http_strings(self):
            for spec in PlaceholderSpec.find_all(text):
                if spec.name not in seen:
                    seen.add(spec.name)
                    result.append(spec)
        return result


@dataclass
class MethodBase(Node):
    """Base class for @request method nodes."""

    name: str = ""  # method name suffix; "" = default fetch()

    @property
    def http_request(self) -> RequestHttp:
        return [n for n in self.body if isinstance(n, RequestHttp)][0]

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        return self.http_request.placeholders

    @property
    def placeholder_names(self) -> list[str]:
        return [p.name for p in self.placeholders]


@dataclass
class MethodFetch(MethodBase):
    """Fetch shortcut for regular schemas (Item/List/etc).

    ``fetch()`` returns a parser instance constructed from the HTTP response body.
    """

    response_path: str = ""  # dot-notation JSON path, e.g. "payload.html"
    response_join: str = (
        ""  # join separator when response-path resolves to list[str]
    )


@dataclass
class MethodRest(MethodBase):
    """REST method for ``type=rest`` schemas.

    Method returns ``Ok/TransportErr`` union; no HTML parsing.
    """

    doc: str = ""  # per-method docstring
    response_schema: str = ""  # json schema name for typed 2xx response


# ── Base struct ──────────────────────────────────────────────────────────────


@dataclass
class StructBase(Node):
    """Base class for all struct AST nodes."""

    type: StructType = StructType.ITEM
    name: str = ""
    keep_order: bool = False  # StructFlatList-specific
    doc: str = ""

    @property
    def docstring(self) -> StructDocstring:
        warnings.warn(
            "StructBase.docstring is deprecated; use the .doc field instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return StructDocstring(parent=self, value=self.doc)

    @docstring.setter
    def docstring(self, value: "StructDocstring | str") -> None:
        warnings.warn(
            "StructBase.docstring is deprecated; use the .doc field instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.doc = (
            value.value if isinstance(value, StructDocstring) else str(value)
        )

    @property
    def request_config(self) -> MethodBase | None:
        for node in self.body:
            if isinstance(node, MethodBase):
                return node
        return None

    @property
    def request_configs(self) -> list[MethodBase]:
        return [n for n in self.body if isinstance(n, MethodBase)]

    @property
    def use_request(self) -> bool:
        return bool(self.request_configs)

    @property
    def errors(self) -> list[ErrorResponse]:
        return [n for n in self.body if isinstance(n, ErrorResponse)]

    @property
    def _typedef_type(self) -> StructType:
        return self.type


# ── Concrete struct types ────────────────────────────────────────────────────


@dataclass
class Struct(StructBase):
    """HTML-parsing struct.

    DSL: ``struct Name { ... }`` with ``type=item|list|flat|dict|table``.

    The ``type`` field (StructType) discriminates the parsing strategy:
      ITEM  → single object/dict
      LIST  → repeating elements → list[dict] (requires @split-doc)
      FLAT  → deduplicated scalars → list[str]
      DICT  → key-value map (requires @split-doc + @key + @value)
      TABLE → HTML table (requires @table + @rows + @match + @value)

    body[0] is always an ``Init`` node (appended in __post_init__).
    """

    type: StructType = StructType.ITEM  # overrided

    @property
    def init(self) -> Init:
        return self.body[0]  # type: ignore

    def __post_init__(self):
        self.body.append(Init(parent=self))


@dataclass
class StructRest(StructBase):
    """REST API endpoint namespace. Stores @request methods, no HTML parsing.

    Unlike ``Struct``, has no ``Init``/``StartParse`` nodes and no field pipelines.
    """

    type: StructType = StructType.REST

    def __post_init__(self):
        pass


# ── Struct child nodes ───────────────────────────────────────────────────────


@dataclass
class StructDocstring(Node):
    """DEPRECATED: use the ``doc`` field on ``StructBase`` instead.

    DSL: ``-doc "text"`` (struct-level documentation).
    Retained only for backward-compatibility imports; the class emits a
    DeprecationWarning on instantiation and is no longer added to struct
    bodies by ``Struct*.__post_init__``.
    """

    value: str = ""

    def __post_init__(self) -> None:
        warnings.warn(
            "StructDocstring node is deprecated; use StructBase.doc instead.",
            DeprecationWarning,
            stacklevel=2,
        )


@dataclass
class PreValidate(Node):
    """
    Validates the document before parsing begins.
    Raises error on failure (caught by fallback if present).
    DSL: -pre-validate { ... }
    accept: DOCUMENT, ret: DOCUMENT (pass-through)
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.NULL)
    )


@dataclass
class CheckMethod(Node):
    """
    Boolean check method on the parsed class.
    DSL: @check <name> { pipeline ... }
    Runs a pipeline on the document and returns True on success, False on failure.
    Called manually by the user before parse().
    """

    name: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.BOOL)
    )


@dataclass
class Init(Node):
    """
    Pre-computed named values cached before field parsing.
    Execution order: after PreValidate, before SplitDoc and Fields.
    DSL: @init { name { pipeline... } ... }
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
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class SplitDoc(Node):
    """
    Splits document into items for list-type structs.
    DSL: @split-doc { ... }
    accept: DOCUMENT, ret: DOCUMENT with is_array=True
    Only valid in struct type=list.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )
    is_array: bool = True


@dataclass
class Key(Node):
    """
    Key extraction pipeline for dict-type structs.
    DSL: @key { ... }
    accept: DOCUMENT, ret: STRING
    Only valid in struct type=dict.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Value(Node):
    """
    Value extraction pipeline for dict/table-type structs.
    DSL: @value { ... }
    dict:  ret can be any type.
    table: ret must be STRING.
    Only valid in struct type=dict or type=table.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class TableConfig(Node):
    """
    Selects the table element.
    DSL: @table { ... }
    accept: DOCUMENT, ret: DOCUMENT
    Only valid in struct type=table.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )


@dataclass
class TableRows(Node):
    """
    Selects table rows.
    DSL: @row { ... }
    accept: DOCUMENT, ret: DOCUMENT with is_array=True
    Only valid in struct type=table.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )
    is_array: bool = True


@dataclass
class TableMatchKey(Node):
    """
    Extracts key cell text from a row for match comparison.
    DSL: @match { ... }
    accept: DOCUMENT (row), ret: STRING
    Only valid in struct type=table.
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


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
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )

    @property
    def struct(self) -> Struct:
        return cast(Struct, self.parent)


@dataclass
class StartParse(Node):
    """Endpoint where need run parser"""

    @property
    def struct(self) -> Struct:
        return cast(Struct, self.parent)

    @property
    def use_split_doc(self) -> bool:
        return any(isinstance(f, SplitDoc) for f in self.struct.body)

    @property
    def use_pre_validate(self) -> bool:
        return any(isinstance(f, PreValidate) for f in self.struct.body)

    @property
    def fields(self) -> list[Field]:
        return [f for f in self.struct.body if isinstance(f, Field)]
