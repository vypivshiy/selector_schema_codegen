# Converter Architecture (converters/)

## Visitor (converters/visitor.py)

Abstract base class — the single codegen abstraction. Walks the AST via a
dispatch table, two-pass signal collection, and concrete shared methods.

```python
class PyBs4(PyHtmlBase):  # PyHtmlBase(Visitor)
    TYPES = {VT.STRING: "str", ...}        # override class attrs
    def visit_css_select(self, node, ctx): # override visit_* methods
        yield f"{ctx.indent}{ctx.nxt} = ..."
```

### CONTRACT for visit_* methods (generators)

```
yield "..."       -> emit a line
yield TRAVERSE    -> traverse node.body, then resume the method (pre/post hook)
yield [...]       -> extend with a list of lines (signals allowed inside)
yield STD(...)    -> register a co-located std helper (name + code + imports)
yield IMPORT(ln)  -> register a main-module import line
yield from it     -> delegate to an iterable
return            -> no-op
```

`""` is preserved as a blank line; `TRAVERSE` (None) is the traverse-children signal.

### Two-pass reliability

`convert_all` runs every `visit_*` **twice**: pass 1 collects `STD()` / `IMPORT()`
signals (output discarded); pass 2 emits. visit_* methods MUST be deterministic
and side-effect-free (same node+ctx → same yields).

### Node categories (body traversal mode)

| Category | Behavior | Examples |
|---|---|---|
| Container | depth+1, index=0, no advance | JsonDef, TypeDef, StructBase, Init |
| Pipeline | index advances after each node | Field, InitField, PreValidate, CheckMethod, SplitDoc, Key, Value, Table* |
| Predicate | depth+1, index=0, advance between siblings | Filter, Assert, Match, LogicNot/And/Or |

`Fallback` is handled specially in `_emit_pipeline` (try/catch block).

## ConverterContext (converters/base.py)

Frozen dataclass — tracks conversion state:

| Field/property | Meaning |
|---|---|
| `index` | Variable counter (v0, v1, v2...) |
| `depth` | Indentation level |
| `var_name` | Base variable name ("v") |
| `indent_char` | Indent string ("    " py, "  " js) |
| `meta` | Build kwargs (http_client, runtime_module, ...) |
| `.prv` | Previous variable name (input) |
| `.nxt` | Next variable name (output) |
| `.indent` | Current indentation string |
| `.advance()` | New ctx with index+1 |
| `.deeper()` | New ctx with depth+1 |

## Class-level config (override in subclasses)

### Type resolution spelling (data, not behaviour)

```python
DEFAULT_TYPE: str = "Any"              # js: "any"
TYPES: dict[VT, str] = {}              # {VT.STRING: "str", ...}
ARRAY_TYPE_FMT: str = "List[{}]"       # js: "{}[]"
OPTIONAL_TYPE_FMT: str = "Optional[{}]"# js: "{}|null"
OPTIONAL_ON_OMITEMPTY: bool = False    # js: True
DOCUMENT_TYPE: str = "Any"             # bs4: "Union[Tag, BeautifulSoup]"
DOCUMENT_ARRAY_TYPE: str = "List[Any]" # js: "Array<Element>"
```

### Predicate formatting

```python
AND_OP: str = "and"                    # js: "&&"
```

## Shared concrete methods (inherited, not overridden)

| Method | Purpose |
|---|---|
| `_resolve_type(type_info) -> str` | TypeInfo → target-language annotation (driven by class attrs) |
| `_resolve_start_parse_t_ret(struct, name) -> str` | Return type for parse() (derived from ARRAY_TYPE_FMT + TYPES) |
| `_pred_line(ctx, cond) -> str` | Format one predicate condition, join siblings with AND_OP |

## Shared module-level functions (language-agnostic)

```python
module_has_rest(module) -> bool
module_is_rest_only(module) -> bool
err_subclass_name(struct_name, err) -> str
dict_entry_placeholder(v) -> PlaceholderSpec | None
dict_needs_builder(d) -> bool
find_predicate_container(node) -> Node | None
```

## Converter hierarchy

```
Visitor (ABC, visitor.py)
├── PyHtmlBase (py_base.py) — shared Python HTML codegen
│   ├── PyBs4   (py_bs4.py)   — BeautifulSoup4
│   ├── PyLxml  (py_lxml.py)   — lxml.html
│   ├── PyParsel(py_parsel.py) — parsel (Scrapy)
│   └── PySlax  (py_slax.py)   — selectolax
└── JsPure (js_pure.py) — vanilla DOM API
```

- `PY_BASE_CONVERTER = PyBs4()` — module-level instance
- `JS_CONVERTER = JsPure()` — module-level instance
- Adding a dialect: subclass `PyHtmlBase`, set config attrs, override the
  expression methods whose spelling differs (selectors, text/raw/attr, to_bool,
  predicates). All shared logic is inherited.

## Adding a new target language

1. Subclass `Visitor` directly (or `PyHtmlBase` if it's a Python parser dialect)
2. Set class attrs: `TYPES`, `ARRAY_TYPE_FMT`, `OPTIONAL_TYPE_FMT`,
   `DOCUMENT_TYPE`, `DOCUMENT_ARRAY_TYPE`, `AND_OP`, etc.
3. Implement ALL `visit_*` methods (the ABC enforces completeness)
4. Use `STD(name, code=, imports=)` for multi-line helpers
5. Register in `main.py` Target enum and converter mapping

## Runtime templates (converters/runtime/)

| Module | Contents |
|--------|----------|
| `_helpers.py` | `module_is_rest_only()`, `http_client_import()` — legacy shared AST utils (now also in visitor.py) |
| `py_base.py` | `NOT_REQUIRED_IMPORT`, `_BASE_UTILITY_LINES`, `base_utility_lines()` — Python base runtime strings |
| `py_rest.py` | `rest_imports()`, `rest_utilities()`, `runtime_export_names()`, `runtime_module_content()`, `register_runtime_file()` — REST assembly & `-R` support |
| `py_lxml.py` | `_FALLBACK_HTML_LINES`, `_FALLBACK_HTML_EXPORT` — lxml-specific fallback HTML |
| `js_base.py` | `JS_BASE_UTILITY_LINES`, `js_base_utility_lines()` — JS helper function strings |

## RequestSpec pipeline (converters/request_spec.py)

`parse_to_spec(raw_payload) → RequestSpec` — parses curl/raw HTTP into normalized form.
`normalize_placeholder_names(spec, transform) → RequestSpec` — adapts placeholder names.

Request rendering is currently per-dialect (not shared):
- Python: `render_value`, `render_dict`, `emit_dict_builder`, `render_json_body`, `render_body` in py_base.py
- JS: `_js_render_value`, `_js_render_obj`, `_js_emit_obj_builder`, `_js_render_json_body`, `_js_render_body` in js_pure.py

---

## Transport layer (@request) — codegen behavior

Optional struct-level directive that embeds a raw HTTP request or POSIX curl command.
Parsed at codegen time via `converters/request_spec.py`.

`RequestHttp` node (child of `MethodBase`) stores normalized HTTP config:
`method`, `url`, `headers`, `cookies`, `params`, `body_kind`, `body`.

Two visitor nodes:
- `MethodFetch` — for HTML-parser structs: emits `fetch()` / `async_fetch()` classmethods
- `MethodRest` — for REST structs: emits per-endpoint methods returning monadic Result types

Generated code (Python `httpx`):
- Non-REST structs: `fetch(self, *, page_num: str) -> Self` and `async_fetch(...)`.
- `type=rest` structs: per-endpoint `@classmethod` methods with `XResult = Union[Ok[T], ErrVariant, UnknownErr, TransportErr]`.

---

## Runtime separation (--separate-runtime / -R)

Extracts helper functions into a separate runtime module (default: `sscgen_runtime`).
Generated parsers import from it instead of inlining.
Runtime content assembled by `converters/runtime/py_rest.py` → `register_runtime_file()`.
