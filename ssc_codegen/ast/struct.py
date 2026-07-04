from __future__ import annotations
import re as _re
import warnings
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Literal
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
    type_name: Literal["str", "int", "float", "bool"] = "str"
    is_array: bool = False
    is_optional: bool = False
    style: Literal["repeat", "csv", "bracket", "pipe", "space"] | None = (
        None  # None == default "repeat" when is_array
    )

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

    def to_token(self) -> str:
        """Reconstruct the ``{{name:type[]?|style}}`` source token."""
        s = "{{" + self.name
        if self.type_name != "str":
            s += f":{self.type_name}"
        if self.is_array:
            s += "[]"
        if self.is_optional:
            s += "?"
        if self.style:
            s += f"|{self.style}"
        return s + "}}"


def parse_placeholder(match: "_re.Match[str]") -> PlaceholderSpec:
    return PlaceholderSpec(
        name=match.group(1),
        type_name=match.group(2) or "str",
        is_array=bool(match.group(3)),
        is_optional=bool(match.group(4)),
        style=match.group(5) or None,
    )


# ── Template: tokenized string value ─────────────────────────────────────────


@dataclass
class Template:
    """A string value tokenized into literal segments and placeholder specs.

    Created once at parse time (``Template.parse``) from raw ``{{...}}`` text.
    All codegen renderers walk ``parts`` instead of re-parsing strings with
    regex.  Placeholder identity is structural (``PlaceholderSpec`` instances
    inline), so renaming is a parts-walk — no string rewriting.
    """

    parts: list[str | PlaceholderSpec] = field(default_factory=list)

    # ── construction ─────────────────────────────────────────────────────

    @classmethod
    def parse(cls, raw: str) -> "Template":
        """Tokenize *raw* into literal / placeholder parts."""
        parts: list[str | PlaceholderSpec] = []
        buf: list[str] = []
        i = 0
        n = len(raw)
        while i < n:
            matched = PlaceholderSpec.match_at(raw, i)
            if matched is not None:
                end, ph = matched
                if buf:
                    parts.append("".join(buf))
                    buf = []
                parts.append(ph)
                i = end
            else:
                buf.append(raw[i])
                i += 1
        if buf:
            parts.append("".join(buf))
        return cls(parts=parts)

    @classmethod
    def literal(cls, text: str) -> "Template":
        """Wrap a placeholder-free string."""
        return cls(parts=[text])

    # ── queries ──────────────────────────────────────────────────────────

    @property
    def is_single_placeholder(self) -> bool:
        """True when parts is exactly ``[PlaceholderSpec]`` (no literals)."""
        return len(self.parts) == 1 and isinstance(
            self.parts[0], PlaceholderSpec
        )

    def single_placeholder(self) -> PlaceholderSpec | None:
        """The sole placeholder if ``is_single_placeholder``, else ``None``."""
        if self.is_single_placeholder:
            return self.parts[0]  # type: ignore[return-value]
        return None

    @property
    def has_placeholders(self) -> bool:
        return any(isinstance(p, PlaceholderSpec) for p in self.parts)

    def placeholders(self) -> list[PlaceholderSpec]:
        """All placeholder specs in this template, in order of appearance."""
        return [p for p in self.parts if isinstance(p, PlaceholderSpec)]

    def map(
        self,
        on_ph: "Callable[[PlaceholderSpec], str]",
        on_literal: "Callable[[str], str] | None" = None,
    ) -> str:
        """Walk parts assembling a string.

        ``on_ph`` renders each placeholder; ``on_literal`` (identity by
        default) transforms each literal segment.
        """
        out: list[str] = []
        for part in self.parts:
            if isinstance(part, PlaceholderSpec):
                out.append(on_ph(part))
            elif on_literal is not None:
                out.append(on_literal(part))
            else:
                out.append(part)
        return "".join(out)

    @property
    def source(self) -> str:
        """Reconstruct the original ``{{...}}`` source text from parts."""
        return self.map(lambda ph: ph.to_token())

    def renamed(self, mapping: dict[str, str]) -> "Template":
        """Return a copy with placeholder names remapped via *mapping*."""
        if not self.has_placeholders:
            return self
        new_parts: list[str | PlaceholderSpec] = []
        for part in self.parts:
            if isinstance(part, PlaceholderSpec):
                new_parts.append(
                    replace(part, name=mapping.get(part.name, part.name))
                )
            else:
                new_parts.append(part)
        return Template(parts=new_parts)


# ── Request/Method nodes ──────────────────────────────────────────────────────


@dataclass
class RequestHttp(Node):
    """Parsed HTTP request — child node of MethodBase.

    Created once at parse time from ``parse_to_http(raw_payload)``;
    converters read fields directly instead of re-parsing raw_payload.
    String fields (url, headers, cookies, params, body) are ``Template``
    instances: tokenized literal/placeholder parts.
    """

    method: str = "GET"
    url: Template = field(default_factory=Template)
    headers: dict[str, Template] = field(default_factory=dict)
    cookies: dict[str, Template] = field(default_factory=dict)
    params: dict[str, Template] = field(default_factory=dict)
    body_kind: str = "empty"  # "empty" | "json" | "form" | "raw"
    body: Template | dict[str, Template] | None = None

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        """Unique placeholders across all string fields."""
        seen: set[str] = set()
        result: list[PlaceholderSpec] = []
        for tmpl in self._all_templates():
            for ph in tmpl.placeholders():
                if ph.name not in seen:
                    seen.add(ph.name)
                    result.append(ph)
        return result

    def _all_templates(self):
        """Yield every Template in this request."""
        yield self.url
        for d in (self.headers, self.cookies, self.params):
            yield from d.values()
        if isinstance(self.body, Template):
            yield self.body
        elif isinstance(self.body, dict):
            yield from self.body.values()

    def with_renamed_placeholders(
        self, transform: Callable[[str], str]
    ) -> "RequestHttp":
        """Return a copy with placeholder names passed through *transform*.

        Only the ``PlaceholderSpec.name`` field changes — type/array/optional/
        style modifiers are preserved.  Operates on structured parts, no string
        rewriting.
        """
        mapping = {ph.name: transform(ph.name) for ph in self.placeholders}
        if all(old == new for old, new in mapping.items()):
            return self

        def _rename_dict(d: dict[str, Template]) -> dict[str, Template]:
            return {k: v.renamed(mapping) for k, v in d.items()}

        new_body: Template | dict[str, Template] | None = self.body
        if isinstance(self.body, Template):
            new_body = self.body.renamed(mapping)
        elif isinstance(self.body, dict):
            new_body = _rename_dict(self.body)

        return RequestHttp(
            method=self.method,
            url=self.url.renamed(mapping),
            headers=_rename_dict(self.headers),
            cookies=_rename_dict(self.cookies),
            params=_rename_dict(self.params),
            body_kind=self.body_kind,
            body=new_body,
        )


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
    # Set by ``core/rest_artifacts.py`` to the matching ``ResultAliasDef.name``
    # so the visitor can reference the result union in the method signature.
    result_alias_name: str = ""


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
    body: list[InitFieldCall]
    """

    pass


@dataclass
class InitFieldCall(Node):
    """
    Call-site marker inside ``Init`` — emits the constructor line that
    invokes the corresponding ``InitField`` method and caches the result.

    The ``InitField`` method definition lives in ``Struct.body`` (at
    class-body level), emitted naturally like a regular ``Field``.
    """

    name: str = ""


@dataclass
class InitField(Node):
    """
    Single named cached pipeline, originally declared inside ``@init``.
    Lives at ``Struct.body`` level (same as ``Field``) so converters emit
    it as a standalone method at class-body depth.
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
