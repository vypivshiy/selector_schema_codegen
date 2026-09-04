"""AST nodes for parser structs, field pipelines, tables, and HTTP request models.

This module defines the core structural intermediate representation nodes for both HTML/document
parsers (`Struct`) and REST API clients (`StructRest`), along with their constituent pipeline
components, initialization caches, table configurations, and HTTP transport specifications.

### Struct Categories and Lifecycles

1. **Parser Structs (`Struct`)**:
   - `ITEM`: Single document extraction mapping fields to dictionary properties.
   - `LIST`: Multi-item extraction with `@split-doc` yielding a list of item objects.
   - `DICT`: Key-value extraction with `@split-doc`, `@key`, and `@value` yielding a dynamic dictionary.
   - `TABLE`: Tabular data extraction matching table rows against field rules via `@table`, `@rows`,
     `@match`, and `@value`.
   - `FLAT`: Single-field flat list extraction with deduplication.
   - `RAW`: Plain text/document extraction without DOM parsing.

2. **Constructor Caching Lifecycle (`@init`)**:
   - `Init`: Container node holding cached computations.
   - `InitField`: Pipeline calculating an intermediate DOM element or value.
   - `InitFieldCall`: Invoked in `__init__` constructor and stored in `self._<name>`.
   - `Self` (in `control.py`): Injected at the start of a field pipeline to read from `self._<name>`.

3. **Pre-Validation Lifecycle (`@pre-validate`)**:
   - `PreValidate`: Assertion pipeline executed before parsing fields.
   - Generated as private `_pre_validate(self, document)` method called as the first statement in `parse()`.

4. **REST Client Structs (`StructRest`) & Transport (`@request`)**:
   - `MethodRest`: REST endpoint method returning a typed result union.
   - `MethodFetch`: HTTP request method returning a parsed document model.
   - `RequestHttp`: Normalized HTTP request definition supporting URL, headers, query params, cookies,
     and body templates.
   - `PlaceholderSpec` & `PlaceholderTemplate`: Tokenized parameter placeholders `{{name:type[]?|style}}`.
   - `ErrorResponse`: Declarative HTTP error status mapping.
"""

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
    """Parsed parameter placeholder token from an HTTP request template.

    Represents tokens of the form `{{name:type[]?|style}}`.

    Attributes:
        name: Identifier of the parameter placeholder.
        type_name: Primitive scalar type constraint (`"str"`, `"int"`, `"float"`, `"bool"`).
        is_array: Flag indicating whether the placeholder accepts a list of values.
        is_optional: Flag indicating whether the parameter is optional.
        style: Serialization style for array parameters (`"repeat"`, `"csv"`, `"bracket"`, `"pipe"`, `"space"`).
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
        """Parse text that is exactly one placeholder token.

        Args:
            text: Raw string containing a single placeholder (e.g. `{{name:int[]?|csv}}`).

        Returns:
            Parsed `PlaceholderSpec` instance, or `None` if syntax does not match.
        """
        m = PLACEHOLDER_RE.fullmatch(text)
        return parse_placeholder(m) if m else None

    @staticmethod
    def find_all(text: str) -> list[PlaceholderSpec]:
        """Return every placeholder found in text in order of appearance.

        Args:
            text: Input string to search for placeholders.

        Returns:
            List of parsed `PlaceholderSpec` objects.
        """
        return [parse_placeholder(m) for m in PLACEHOLDER_RE.finditer(text)]

    @staticmethod
    def search(text: str) -> bool:
        """Check whether text contains at least one placeholder token.

        Args:
            text: Input string to test.

        Returns:
            True if text contains at least one placeholder.
        """
        return PLACEHOLDER_RE.search(text) is not None

    @staticmethod
    def match_at(text: str, pos: int) -> tuple[int, PlaceholderSpec] | None:
        """Try to match a placeholder at the given string offset.

        Args:
            text: Input string.
            pos: Starting index in text to match.

        Returns:
            Tuple of `(end_position, spec)` on success, or `None` on failure.
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
        """Replace every placeholder token in text with a substitute string.

        Args:
            text: Input string containing placeholders.
            replacement: Literal string or callback receiving each parsed `PlaceholderSpec`.

        Returns:
            Substituted result string.
        """
        if callable(replacement):
            return PLACEHOLDER_RE.sub(
                lambda m: replacement(parse_placeholder(m)), text
            )
        return PLACEHOLDER_RE.sub(replacement, text)

    @staticmethod
    def rename(text: str, mapping: dict[str, str]) -> str:
        """Rename placeholder identifiers in text while preserving all type/style modifiers.

        Args:
            text: String containing placeholders.
            mapping: Map of old placeholder names to new placeholder names.

        Returns:
            String with remapped placeholder names.
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
        """Reconstruct the canonical source token representation."""
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
    """Construct a `PlaceholderSpec` from a regex match object."""
    return PlaceholderSpec(
        name=match.group(1),
        type_name=cast(
            Literal["str", "int", "float", "bool"],
            match.group(2) or "str",
        ),
        is_array=bool(match.group(3)),
        is_optional=bool(match.group(4)),
        style=cast(
            Literal["repeat", "csv", "bracket", "pipe", "space"] | None,
            match.group(5) or None,
        ),
    )


# ── Template: tokenized string value ─────────────────────────────────────────


@dataclass
class PlaceholderTemplate:
    """String template segmented into literal chunks and parsed placeholder tokens.

    Attributes:
        parts: Sequence of literal string segments and `PlaceholderSpec` tokens.
    """

    parts: list[str | PlaceholderSpec] = field(default_factory=list)

    # ── construction ─────────────────────────────────────────────────────

    @classmethod
    def parse(cls, raw: str) -> "PlaceholderTemplate":
        """Tokenize a raw string containing `{{...}}` tokens into parts.

        Args:
            raw: Raw input string to parse.

        Returns:
            Parsed `PlaceholderTemplate` instance.
        """
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
    def literal(cls, text: str) -> "PlaceholderTemplate":
        """Construct a template consisting of a single literal string segment.

        Args:
            text: Literal text content.

        Returns:
            `PlaceholderTemplate` wrapping the literal text.
        """
        return cls(parts=[text])

    # ── queries ──────────────────────────────────────────────────────────

    @property
    def is_single_placeholder(self) -> bool:
        """True if the template consists solely of one placeholder without literal text."""
        return len(self.parts) == 1 and isinstance(
            self.parts[0], PlaceholderSpec
        )

    def single_placeholder(self) -> PlaceholderSpec | None:
        """Return the sole placeholder if `is_single_placeholder` is True, else `None`."""
        if self.is_single_placeholder:
            return self.parts[0]  # type: ignore[return-value]
        return None

    @property
    def has_placeholders(self) -> bool:
        """True if the template contains at least one placeholder."""
        return any(isinstance(p, PlaceholderSpec) for p in self.parts)

    def placeholders(self) -> list[PlaceholderSpec]:
        """Return all placeholder specifications in order of appearance."""
        return [p for p in self.parts if isinstance(p, PlaceholderSpec)]

    def map(
        self,
        on_ph: "Callable[[PlaceholderSpec], str]",
        on_literal: "Callable[[str], str] | None" = None,
    ) -> str:
        """Assemble a string by transforming placeholders and literal segments.

        Args:
            on_ph: Renderer callback for `PlaceholderSpec` instances.
            on_literal: Optional renderer callback for literal string segments.

        Returns:
            Concatenated result string.
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
        """Reconstruct the original source string."""
        return self.map(lambda ph: ph.to_token())

    def renamed(self, mapping: dict[str, str]) -> "PlaceholderTemplate":
        """Return a new template with placeholder names remapped per mapping.

        Args:
            mapping: Map from current placeholder names to new names.

        Returns:
            New `PlaceholderTemplate` instance with updated placeholder names.
        """
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
        return PlaceholderTemplate(parts=new_parts)


# ── Request/Method nodes ──────────────────────────────────────────────────────


@dataclass
class RequestHttp(Node):
    """Parsed HTTP request configuration payload.

    Attributes:
        method: HTTP method verb (e.g. `"GET"`, `"POST"`, `"PUT"`, `"DELETE"`).
        url: Tokenized request URL template containing literal parts and placeholders.
        headers: Mapping of HTTP header names to tokenized value templates.
        cookies: Mapping of cookie names to tokenized value templates.
        params: Mapping of query parameter names to tokenized value templates.
        body_kind: Kind of request body (`"empty"`, `"json"`, `"form"`, `"raw"`).
        payload: Tokenized request body payload template or key-value dictionary.
    """

    method: str = "GET"
    url: PlaceholderTemplate = field(default_factory=PlaceholderTemplate)
    headers: dict[str, PlaceholderTemplate] = field(default_factory=dict)
    cookies: dict[str, PlaceholderTemplate] = field(default_factory=dict)
    params: dict[str, PlaceholderTemplate] = field(default_factory=dict)
    body_kind: str = "empty"  # "empty" | "json" | "form" | "raw"
    payload: PlaceholderTemplate | dict[str, PlaceholderTemplate] | None = None

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        """Return list of unique placeholders found across all request fields."""
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
        if isinstance(self.payload, PlaceholderTemplate):
            yield self.payload
        elif isinstance(self.payload, dict):
            yield from self.payload.values()

    def with_renamed_placeholders(
        self, transform: Callable[[str], str]
    ) -> "RequestHttp":
        """Return a copy with placeholder names passed through a transformation function.

        Args:
            transform: Function converting old placeholder names to new names.

        Returns:
            New `RequestHttp` copy with updated placeholder names.
        """
        mapping = {ph.name: transform(ph.name) for ph in self.placeholders}
        if all(old == new for old, new in mapping.items()):
            return self

        def _rename_dict(
            d: dict[str, PlaceholderTemplate],
        ) -> dict[str, PlaceholderTemplate]:
            return {k: v.renamed(mapping) for k, v in d.items()}

        new_payload: (
            PlaceholderTemplate | dict[str, PlaceholderTemplate] | None
        ) = self.payload
        if isinstance(self.payload, PlaceholderTemplate):
            new_payload = self.payload.renamed(mapping)
        elif isinstance(self.payload, dict):
            new_payload = _rename_dict(self.payload)

        return RequestHttp(
            method=self.method,
            url=self.url.renamed(mapping),
            headers=_rename_dict(self.headers),
            cookies=_rename_dict(self.cookies),
            params=_rename_dict(self.params),
            body_kind=self.body_kind,
            payload=new_payload,
        )


@dataclass
class MethodBase(Node):
    """Abstract base node for HTTP method declarations (`@request`).

    Attributes:
        name: Suffix for the generated method name (empty string generates default `fetch`).
        response_path: Dot-notation JSON path extracted from 2xx response bodies before schema mapping.
        response_join: Delimiter string to join multiple string items when extracting lists.
    """

    name: str = ""  # method name suffix; "" = default fetch()

    #: Dot-notation JSON path extracted from the 2xx response body before it
    #: becomes ``Ok.value`` (REST) or the parser input (fetch). Example:
    #: ``"data.user"`` resolves ``{"data": {"user": ...}}`` to the inner
    #: object. When set together with ``response_schema`` (REST), the path
    #: wins: the schema type-checks the *extracted* sub-object, not the
    #: whole envelope. ``@error`` matchers always run against the full body.
    response_path: str = ""

    #: Join separator applied when ``response_path`` resolves to a
    #: ``list[str]`` (fetch-only). Forbidden on ``MethodRest``; the linter
    #: rejects ``response-join`` on ``type=rest`` structs.
    response_join: str = ""

    @property
    def http_request(self) -> RequestHttp:
        """The child `RequestHttp` configuration node."""
        return [n for n in self.body if isinstance(n, RequestHttp)][0]

    @property
    def placeholders(self) -> list[PlaceholderSpec]:
        """List of all placeholders required by the underlying HTTP request."""
        return self.http_request.placeholders


@dataclass
class MethodFetch(MethodBase):
    """Fetch request method for document/HTML parsing structs."""


@dataclass
class MethodRest(MethodBase):
    """REST endpoint method declaration for `type=rest` client structs.

    Attributes:
        doc: Documentation string for the REST endpoint method.
        response_schema: Name of the JSON schema model for successful 2xx responses.
        result_alias_name: Identifier of the generated synthetic result union type alias.
    """

    doc: str = ""  # per-method docstring
    response_schema: str = ""  # json schema name for typed 2xx response
    # Set by ``core/rest_artifacts.py`` to the matching ``ResultAliasDef.name``
    # so the visitor can reference the result union in the method signature.
    result_alias_name: str = ""


# ── Base struct ──────────────────────────────────────────────────────────────


@dataclass
class StructBase(Node):
    """Base class for all struct AST nodes.

    Attributes:
        type: Struct parsing category (`ITEM`, `LIST`, `DICT`, `TABLE`, `FLAT`, `REST`, `RAW`).
        name: Declared name of the struct class or client container.
        keep_order: Flag to preserve source item order in flat list deduplication.
        doc: Struct-level docstring documentation.
    """

    type: StructType = StructType.ITEM
    name: str = ""
    keep_order: bool = False  # StructFlatList-specific
    doc: str = ""

    @property
    def docstring(self) -> StructDocstring:
        """Deprecated property for accessing struct docstring."""
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
        """First request method configuration node if declared on this struct."""
        for node in self.body:
            if isinstance(node, MethodBase):
                return node
        return None

    @property
    def request_configs(self) -> list[MethodBase]:
        """List of all request method nodes declared in this struct."""
        return [n for n in self.body if isinstance(n, MethodBase)]

    @property
    def use_request(self) -> bool:
        """True if this struct declares at least one `@request` method."""
        return bool(self.request_configs)

    @property
    def errors(self) -> list[ErrorResponse]:
        """List of all `@error` response mapping nodes declared in this struct."""
        return [n for n in self.body if isinstance(n, ErrorResponse)]

    @property
    def _typedef_type(self) -> StructType:
        return self.type


# ── Concrete struct types ────────────────────────────────────────────────────


@dataclass
class Struct(StructBase):
    """HTML/document parser struct node.

    Emitted as a parser class with constructor and field extraction methods.

    Attributes:
        type: Parsing strategy (`ITEM`, `LIST`, `DICT`, `TABLE`, `FLAT`, `RAW`).
    """

    type: StructType = StructType.ITEM  # overrided

    @property
    def init(self) -> Init:
        """Reference to the pre-computed `@init` block node."""
        return self.body[0]  # type: ignore

    def __post_init__(self):
        self.body.append(Init(parent=self))


@dataclass
class StructRest(StructBase):
    """REST API endpoint client struct node.

    Emitted as an API client class with typed HTTP methods returning result unions.
    """

    type: StructType = StructType.REST

    def __post_init__(self):
        pass


# ── Struct child nodes ───────────────────────────────────────────────────────


@dataclass
class StructDocstring(Node):
    """DEPRECATED: Struct-level documentation node.

    Retained only for backward-compatibility; use `StructBase.doc` instead.

    Attributes:
        value: Documentation string.
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
    """Document pre-validation assertion pipeline executed prior to parsing fields.

    Declared via `@pre-validate { assert { ... } }` inside a struct. The code generator emits
    a private validation method `_pre_validate(self, document)` that runs assertions against
    the input document before any field extraction is performed in `parse()`.

    Examples:
        - KDL:
            ```kdl
            struct ProductInfo type=table {
                @pre-validate {
                    assert { css "table.product_page" }
                }
            }
            ```
        - Generated Python:
            ```python
            def _pre_validate(self, v: Any) -> None:
                std_assert(bool(v.select("table.product_page")), "ProductInfo.@pre-validate assertion failed")

            def parse(self) -> ProductInfoType:
                self._pre_validate(self._doc)
                return { ... }
            ```
        - Generated JavaScript:
            ```javascript
            _preValidate(v) {
                sscAssert(v.querySelectorAll("table.product_page").length > 0, "ProductInfo.@pre-validate assertion failed");
            }
            ```
        - Generated Go:
            ```go
            func (p *ProductInfo) preValidate(v *goquery.Selection) error {
                if !stdAssert(v.Find("table.product_page").Length() > 0) {
                    return errors.New("ProductInfo.@pre-validate assertion failed")
                }
                return nil
            }
            ```
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.NULL)
    )


@dataclass
class CheckMethod(Node):
    """Boolean document validation predicate method (`@check`).

    Generates a public boolean method on the parser class to verify document validity,
    presence of elements, or business rules.

    Attributes:
        name: Identifier of the generated boolean check method (e.g. `"is_available"`).

    Examples:
        - KDL:
            ```kdl
            @check is_in_stock {
                css ".instock"
                to-bool
            }
            ```
        - Generated Python:
            ```python
            def is_in_stock(self) -> bool:
                v1 = self._doc.select_one(".instock")
                return bool(v1)
            ```
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
    """Container for pre-computed cached values initialized in constructor (`@init`).

    Acts as the parent AST container node for all `InitField` computations declared
    inside `@init { ... }`.
    """

    pass


@dataclass
class InitFieldCall(Node):
    """Constructor invocation marker for a cached `@init` computation.

    Emitted during constructor generation to execute the matching `InitField` calculation
    and store the result in an internal property (e.g. `self._container = self._init_container()`).

    Attributes:
        name: Identifier of the cached field to initialize.
    """

    name: str = ""


@dataclass
class InitField(Node):
    """Cached pipeline computation declared inside `@init`.

    Generates a private calculation method (e.g. `_init_container(self)`) whose result
    is cached in the constructor and referenced by field pipelines via `Self` (`@container`).

    Attributes:
        name: Field identifier used for internal caching and `@<name>` references.

    Examples:
        - KDL:
            ```kdl
            @init {
                main_box {
                    css "div.main-container"
                }
            }
            ```
        - Generated Python:
            ```python
            def _init_main_box(self) -> Any:
                return self._doc.select_one("div.main-container")

            def __init__(self, document: Any) -> None:
                self._doc = document
                self._main_box = self._init_main_box()
            ```
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
    """Document splitter pipeline extracting item documents for `type=list` or `type=dict`.

    Attributes:
        is_array: Always `True` for document splitters.

    Examples:
        - KDL: `@split-doc { css-all "article.product_pod" }`
        - Generated Python:
            ```python
            for item_doc in self._doc.select("article.product_pod"):
                # yield/append parsed item
            ```
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
    """Dictionary key extraction pipeline for `type=dict` structs.

    Executed on each item document extracted by `@split-doc` to derive the dictionary entry key.

    Examples:
        - KDL: `@key { css ".attr-name"; text; trim; }`
        - Generated Python:
            ```python
            k = row_doc.select_one(".attr-name").get_text(strip=True)
            ```
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Value(Node):
    """Value extraction pipeline for `type=dict` or `type=table` structs.

    Executed on each item document or matching table row to extract the corresponding payload value.

    Examples:
        - KDL: `@value { css ".attr-val"; text; to-int; }`
        - Generated Python:
            ```python
            v = int(row_doc.select_one(".attr-val").get_text(strip=True))
            ```
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.AUTO)
    )


@dataclass
class TableConfig(Node):
    """Table root element selection pipeline for `type=table` structs.

    Extracts the root `<table>` element container from the document.

    Examples:
        - KDL: `@table { css "table.specs-table" }`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )


@dataclass
class TableRows(Node):
    """Table rows selection pipeline for `type=table` structs.

    Extracts all row container elements (`<tr>`) from the table.

    Attributes:
        is_array: Always `True` for row selection lists.

    Examples:
        - KDL: `@rows { css-all "tr" }`
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
    """Table row key extraction pipeline for matching against field conditions.

    Evaluated on each row element to extract the row identifier string (e.g. from `<th>` or `<td>`),
    which is then tested against `Match` predicate rules in table fields.

    Examples:
        - KDL: `@match { css "th"; text; trim; lower; }`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class ErrorResponse(Node):
    """HTTP error response mapping declaration for REST client structs.

    Declares handling rules for non-2xx HTTP status codes in `(rest)struct`.
    Synthesized into `ResultVariantDef` and `MatcherListDef` during compiler AST passes.

    Attributes:
        status: HTTP status code constraint (100–599, e.g. `404`, `500`).
        schema_name: Identifier of the JSON schema model used for error payload deserialization.
        required_keys: Top-level keys required to exist in the error response body.
        conditions: Map of dot-path property checks against the error JSON body.

    Examples:
        - KDL:
            ```kdl
            @error 404 schema=NotFoundJson {
                body-matches "code" "RESOURCE_NOT_FOUND"
            }
            ```
    """

    status: int = 0
    schema_name: str = ""
    required_keys: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Field(Node):
    """Output property field pipeline node.

    Defines a single extracted attribute method on a parser struct, transforming
    input document `self._doc` through an ordered sequence of child operation nodes.

    Attributes:
        name: Name of the extracted field property.

    Examples:
        - KDL:
            ```kdl
            title {
                css "h1.product-title"
                text
                trim
            }
            ```
        - Generated Python:
            ```python
            def title(self) -> str:
                v1 = self._doc.select_one("h1.product-title")
                v2 = v1.get_text(strip=True)
                return v2.strip()
            ```
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
        """Reference to the parent `Struct` AST node."""
        return cast(Struct, self.parent)


@dataclass
class StartParse(Node):
    """Technical marker node representing the generated primary `parse()` method.

    Coordinates document pre-validation, `@split-doc` iteration, and field aggregation
    into the final output model.
    """

    @property
    def struct(self) -> Struct:
        """Reference to the parent `Struct` AST node."""
        return cast(Struct, self.parent)

    @property
    def use_split_doc(self) -> bool:
        """True if the parent struct contains a `SplitDoc` node."""
        return any(isinstance(f, SplitDoc) for f in self.struct.body)

    @property
    def use_pre_validate(self) -> bool:
        """True if the parent struct contains a `PreValidate` node."""
        return any(isinstance(f, PreValidate) for f in self.struct.body)

    @property
    def fields(self) -> list[Field]:
        """List of all output fields in the parent struct."""
        return [f for f in self.struct.body if isinstance(f, Field)]
