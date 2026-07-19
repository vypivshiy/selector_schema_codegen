# Codegen Architecture (targets/ + traversal/ + generation/)

Replaces the old `converters/` package entirely.

## BaseWalker (traversal/walker.py)

Abstract traversal core — dispatches AST nodes to `visit_*` handlers via a
class-level `_DISPATCH` table. No codegen logic; just dispatch + body traversal.

```python
class PythonVisitor(BaseWalker):
    def visit_css_select(self, node, ctx) -> list[str]:
        return self._dom.css_select(ctx, node)
```

### Handler contract

```
visit_*(node, ctx) -> list[str]    # complete codegen lines
visit_*(node, ctx) -> str          # single line (auto-wrapped to [str])
visit_*(node, ctx) -> None         # no output
```

`""` is preserved as a blank line.

### Node categories (body traversal mode)

| Category | Behavior | Examples |
|---|---|---|
| Container | depth+1, index=0, no advance | JsonDef, TypeDef, StructBase, Init |
| Pipeline | index advances after each node | Field, InitField, PreValidate, CheckMethod, SplitDoc, Key, Value, Table* |
| Predicate | depth+1, index=0, advance between siblings | Filter, Assert, Match, LogicNot/And/Or |

`Fallback` is handled specially in `walk_pipeline` (try/catch block).

## WalkContext (traversal/context.py)

Immutable dataclass (frozen via `replace()`) — tracks traversal state:

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
| `.advance_n(n)` | New ctx with index+n |
| `.deeper()` | New ctx with depth+1 |
| `.reset_index()` | New ctx with index=0 |

## ModuleBuilder (generation/builder.py)

Pure data accumulator — replaces old hidden signal pools (`STD()` / `IMPORT()` yields).

| Method/property | Purpose |
|---|---|
| `require_import(line)` | Register an import line (idempotent, order-preserving) |
| `require_std(name, code=, imports=)` | Register a std-helper definition (idempotent by name) |
| `reset()` | Clear all accumulated state |
| `.imports` | List of registered import lines |
| `.std_names` | List of registered std-helper names |
| `.std_defs` | Dict of name → (imports, code) |
| `.std_imports` | List of std-scoped import lines |
| `.has_std` | True if any std helpers registered |

Target visitors access the builder via `self._builder` (PythonVisitor) or
`self._builder` (JsVisitor). DomSpelling instances receive the builder in
their constructor and use `self._builder.require_std(...)` / `.require_import(...)`.

## DomSpelling (targets/python/html_libs/base.py)

ABC — dialect-specific HTML extraction spelling (data + behavior).

Holds a `ModuleBuilder` reference for registering std helpers and imports.

**Contract:**
- Expression methods return `list[str]` (complete codegen lines)
- Predicate methods return `str` (condition fragment; visitor inlines with `prefix = "" if ctx.index == 0 else "and "`)

### Data attributes (override in subclasses)

```python
parser_imports: tuple[str, ...] = ()
document_type: str = "Any"
document_array_type: str = "List[Any]"
init_arg_type: str = "Any"
init_from_str_expr: str = "document"
extra_utilities: tuple[str, ...] = ()
supports_xpath: bool = False
```

### Expression methods (return list[str])

| Method | Node |
|---|---|
| `css_select(ctx, node)` | CssSelect |
| `css_select_all(ctx, node)` | CssSelectAll |
| `css_remove(ctx, node)` | CssRemove |
| `xpath_select(ctx, node)` | XpathSelect |
| `xpath_select_all(ctx, node)` | XpathSelectAll |
| `xpath_remove(ctx, node)` | XpathRemove |
| `text(ctx, node)` | Text |
| `raw(ctx, node)` | Raw |
| `attr(ctx, node)` | Attr |
| `to_bool(ctx, node)` | ToBool |

### Predicate methods (return str)

| Method | Node |
|---|---|
| `pred_css(node)` | PredCss |
| `pred_xpath(node)` | PredXpath |
| `pred_has_attr(node)` | PredHasAttr |
| `pred_attr_contains(node)` | PredAttrContains |
| `pred_attr_starts(node)` | PredAttrStarts |
| `pred_attr_ends(node)` | PredAttrEnds |
| `pred_attr_eq(node)` | PredAttrEq |
| `pred_attr_ne(node)` | PredAttrNe |
| `pred_attr_re(node)` | PredAttrRe |
| `pred_text_contains(node)` | PredTextContains |
| `pred_text_starts(node)` | PredTextStarts |
| `pred_text_ends(node)` | PredTextEnds |
| `pred_text_re(node)` | PredTextRe |

## PythonVisitor (targets/python/visitor.py)

Self-contained `BaseWalker` subclass. No subclasses needed — configured via
`dom_spelling_cls` constructor parameter.

```python
class PythonVisitor(BaseWalker):
    def __init__(self, var_name="v", indent="    ", dom_spelling_cls=None):
        ...
```

- Creates `self._dom` from spelling class in `_reset_state()`
- 23 DOM delegation methods (`visit_css_select` → `self._dom.css_select`, etc.)
- Class-level type resolution attrs: `TYPES`, `ARRAY_TYPE_FMT`, `OPTIONAL_TYPE_FMT`, `DEFAULT_TYPE`, `OPTIONAL_ON_OMITEMPTY`, `STD_MODULE_NAME`
- `_HTTP_STRATEGIES` dict maps `"httpx"` → `HttpxStrategy()`, `"aiohttp"` → `AioHttpStrategy()`, `"requests"` → `RequestsStrategy()`
- REST rendering delegated to `rest.py`: `rest.emit_method_fetch`, `rest.emit_method_rest`, `rest.emit_result_variant_def`, `rest.emit_result_alias_def`, `rest.emit_matcher_list_def`
- Predicate formatting inlined: `prefix = "" if ctx.index == 0 else "and "` then `f"{ctx.indent}{prefix}{cond}"`

### Pre-built instances (targets/python/__init__.py)

```python
PY_BS4_CONVERTER = PythonVisitor(dom_spelling_cls=Bs4DomSpelling)
PY_LXML_CONVERTER = PythonVisitor(dom_spelling_cls=LxmlDomSpelling)
PY_PARSEL_CONVERTER = PythonVisitor(dom_spelling_cls=ParselDomSpelling)
PY_SLAX_CONVERTER = PythonVisitor(dom_spelling_cls=SlaxDomSpelling)
```

## JsVisitor (targets/javascript/visitor.py)

Self-contained `BaseWalker` subclass — vanilla DOM API. All codegen logic
inline (no DomSpelling pattern — JS has one DOM API).

- Class-level type resolution attrs: `TYPES` (JS types), `ARRAY_TYPE_FMT="{}[]"`, `OPTIONAL_TYPE_FMT="{}|null"`, `OPTIONAL_ON_OMITEMPTY=True`, `DEFAULT_TYPE="any"`
- `_HTTP_STRATEGIES` dict maps `"fetch"` → `FetchStrategy()`, `"axios"` → `AxiosStrategy()`
- REST rendering delegated to `rest.py`: `rest.emit_method_fetch`, `rest.emit_method_rest`, `rest.emit_result_variant_def`, `rest.emit_result_alias_def`, `rest.emit_matcher_list_def`
- Predicate formatting inlined: `prefix = "" if ctx.index == 0 else "&& "` then `f"{ctx.indent}{prefix}{cond}"`

Pre-built instance: `JS_CONVERTER = JsVisitor()` (targets/javascript/__init__.py)

## HttpLibStrategy (targets/python/http_libs/base.py)

ABC — HTTP client library strategy for REST codegen.

**Python strategies:**

| Strategy | Class attrs | Behavior |
|---|---|---|
| `HttpxStrategy` | `import_line`, `sync_client_type`, `async_client_type`, `transport_exception` | sync + async native |
| `AioHttpStrategy` | same pattern | async-only; sync via `asyncio.run()` + `ThreadPoolExecutor` fallback for running-loop |
| `RequestsStrategy` | same pattern | sync-only; async via `run_in_executor` |

Each owns `rest_runtime_lines() -> list[str]` — REST runtime source with
library-specific `except` clause.

**JS strategies** (`JsHttpLibStrategy`):

| Strategy | `fn_name` |
|---|---|
| `FetchStrategy` | `"sscRestCall"` |
| `AxiosStrategy` | `"sscRestCallAxios"` |

JS emits both fetch and axios runtime helpers regardless of selection.
Strategy only determines which helper name generated methods delegate to.

## Shared utility functions (traversal/utils.py)

Language-agnostic functions used by both backends:

```python
module_has_rest(module) -> bool
module_is_rest_only(module) -> bool
err_subclass_name(struct_name, err) -> str
dict_entry_placeholder(tmpl) -> PlaceholderSpec | None
dict_needs_builder(d) -> bool
find_predicate_container(node) -> Node | None
jsonify_path_to_segments(path) -> list[str | tuple[str, bool]]
```

## Runtime file (generation/runtime.py)

Flat module that assembles the separate runtime file emitted by `-R` /
`--separate-runtime`.

| Symbol | Role |
|--------|------|
| `_BASE_UTILITY_LINES` | Base text-helper source lines (repl_map, normalize_text, unescape_text, rm_prefix/suffix, UNMATCHED_TABLE_ROW) |
| `rest_runtime_lines()` | REST runtime source lines (Ok/Err/UnknownErr/TransportErr/ErrMatcher/ssc_dispatch_err/ssc_rest_call[_async]) |
| `runtime_module_content(module)` | Full runtime file source for one reference module |
| `register_runtime_file(converter, runtime_name, *, include_fallback)` | Registers a `@converter.file(...)` provider and returns a `generate_runtime(modules) -> str` callable |

## Target resolution (targets/)

```
TargetSpec (raw user input)
    → resolve(spec) → TargetProfile (validated capabilities + factory)
        → profile.create_converter() → PythonVisitor | JsVisitor
```

| Component | File | Role |
|---|---|---|
| `TargetSpec` | `spec.py` | Raw user input: `lang`, `lib`, `http_client`, `separate_runtime` |
| `TargetProfile` | `profile.py` | Frozen dataclass: `language`, `file_extension`, `create_converter: Callable`, `http_clients`, `supports_separate_runtime`, `runtime_include_fallback` |
| `resolve(spec)` | `resolver.py` | Validates input, returns `TargetProfile` with factory. Raises `ResolutionError` on invalid combos. |

## RequestHttp pipeline (request_spec.py + ast/struct.py)

`parse_to_http(raw_payload) → RequestHttp` — parses curl/raw HTTP into the
`RequestHttp` AST node. String fields (url, headers, cookies, params, body) are
`Template` instances: tokenized into `list[str | PlaceholderSpec]` parts at parse
time via `Template.parse`. Placeholder identity is structural (PlaceholderSpec
inline in parts), not text-embedded.

`RequestHttp.with_renamed_placeholders(transform) → RequestHttp` — returns a
copy with placeholder names passed through a target-language transform
(`to_snake_case` for Python, `to_camel_case` for JS). Walks structured parts,
replacing `PlaceholderSpec.name` — **no string rewriting, no regex**.

Renderers walk `Template.parts` instead of regex-parsing strings:
- Python: `rest.render_value(Template)`, `rest.render_dict`, `rest.emit_dict_builder`, `rest.render_json_body`, `rest.render_body` in `targets/python/rest.py`
- JS: `rest.render_value(Template)`, `rest.render_obj`, `rest.emit_obj_builder`, `rest.emit_params_builder`, `rest.render_json_body`, `rest.render_body` in `targets/javascript/rest.py`
- `Template.map(on_ph, on_literal)` assembles a string from parts (used by JS template-literal rendering)
- `Template.single_placeholder()` / `is_single_placeholder` — queries for dict-entry / bare-name cases

## REST result artifacts (ast/rest.py + core/rest_artifacts.py)

REST result types are modeled as synthesizable AST nodes, mirroring
`TypeDef`/`JsonDef`. `core/rest_artifacts.py:rest_artifacts_from_struct`
builds them from a `StructRest` and they are inserted into `Module.body`
before the struct by `core/reader.py` (same pattern as `typedef_from_struct`).

| Node | Carries | Visitor emits |
|------|---------|---------------|
| `ResultVariantDef` | name, status, schema_name, schema_is_array (RAW) | per-error subclass decl (`@dataclass class XErr(Err[T])` / JSDoc `@typedef`) |
| `ResultAliasDef` | name, response_schema, response_is_array, err_variants | per-method union alias (`XResult = Union[...]`); also stamps `result_alias_name` on the matching `MethodRest` |
| `MatcherListDef` | struct_name, entries: list[MatcherEntry] | per-struct matchers list (`_x_matchers = [ErrMatcher(...)]`); visitor renders the var-name spelling + check expression per language |

`MatcherEntry` carries RAW condition data (`required_keys` + `conditions`) —
each language renders its own check spelling (`lambda _b: ...` in Python,
`(_b) => ...` in JS). The synthesizer is language-agnostic.

## REST codegen — rest.py per backend

Each backend has a `rest.py` module containing pure functions for REST/fetch
codegen. Visitors delegate to these via thin `visit_*` wrappers.

| File | Key functions |
|------|---------------|
| `targets/python/rest.py` | `render_value`, `render_dict`, `emit_dict_builder`, `render_json_body`, `render_body`, `placeholder_params`, `emit_method_rest`, `emit_method_fetch`, `emit_result_variant_def`, `emit_result_alias_def`, `emit_matcher_list_def`, `runtime_export_names` |
| `targets/javascript/rest.py` | `render_value`, `render_obj`, `emit_obj_builder`, `emit_params_builder`, `render_json_body`, `render_body`, `emit_method_rest`, `emit_method_fetch`, `emit_result_variant_def`, `emit_result_alias_def`, `emit_matcher_list_def`, `REST_SHARED` |

All `emit_*` functions accept `(node, ctx, http)` where `http` is the
backend's `HttpLibStrategy`. Result artifact functions (`emit_result_*`,
`emit_matcher_list_def`) only take `(node)` / `(node, ...)`.

---

## Transport layer (@request) — codegen behavior

Optional struct-level directive that embeds a raw HTTP request or POSIX curl command.
Parsed at codegen time via `request_spec.py:parse_to_http` into a `RequestHttp` AST node.

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

### What moves to the runtime file

| Symbol | Source | Notes |
|--------|--------|-------|
| Text helpers | `_BASE_UTILITY_LINES` in `generation/runtime.py` | `repl_map`, `normalize_text`, `unescape_text`, `rm_prefix/suffix`, `UNMATCHED_TABLE_ROW` |
| REST runtime | `rest_runtime_lines()` in `generation/runtime.py` | `Ok`/`Err`/`UnknownErr`/`TransportErr` dataclasses, `ErrMatcher`, `ssc_dispatch_err`, `ssc_rest_call`, `ssc_rest_call_async` |
| Optional HTML fallback | `include_fallback=True` (resolver: `lib == "lxml"`) | Prepends `FALLBACK_HTML_STR = "<html><body></body></html>"` to the runtime |
| Transport import | `transport_import_line` parameter | `import httpx` / `import aiohttp` / `import requests` — resolved in `main.py` from the chosen HTTP client and threaded through `register_runtime_file` → `runtime_module_content`. **Required when `has_rest`**: `ssc_rest_call` references the transport exception (`httpx.HTTPError` etc.) in its `except` clause. |

### What stays in the parser file

The parser file still needs the bulk of its imports under `-R`, because it
declares the schema `TypedDict`s, the `@dataclass class XErr(Err[T])`
subclasses with `Literal[<status>]` status fields, the HTML struct bodies,
and the method signatures (`client: httpx.Client`). Concretely:

| Import surface | Under `-R` | Without `-R` | Reason |
|----------------|------------|--------------|--------|
| `from typing import Any, Dict, List, Optional, TypedDict, Union` | always | always | TypedDict schema declarations |
| `from typing_extensions import NotRequired` | always | always | Optional JSON fields |
| `import re`, `import json` | always | always | Regex/jsonify ops |
| `from typing import Literal` | always | always | Err subclass `status: Literal[<code>]` |
| `from dataclasses import dataclass` | always | always | `@dataclass` on Err subclasses |
| `import httpx` (or chosen lib) | always when `has_rest` | always when `has_rest` | Method signatures `client: httpx.Client` |
| `from lxml import html` / `from lxml.html import HtmlElement` etc. | always when HTML struct | always when HTML struct | HTML extraction |
| `from dataclasses import field` | **not needed** | always when `has_rest` | `field(default_factory=dict)` in inlined Ok/Err/ErrMatcher defs |
| `from typing import Callable, Generic, Mapping, TypeVar` | **not needed** | always when `has_rest` | Runtime-internal generic/dataclass machinery |

The split is implemented in `PythonVisitor.visit_module` — see
`_builder.require_import(...)` calls gated on `if not runtime:` for the
runtime-internal subset only.

### `runtime_export_names(module, *, need_fallback=False)` (rest.py)

Returns the exact list of names the parser file imports from the runtime.
Conditional selection:

- **REST-only module** (`module_is_rest_only == True`): REST names only.
  `ssc_dispatch_err` is omitted — it is internal to `ssc_rest_call`.
- **Module with HTML structs** (`module_is_rest_only == False`): table
  markers (`UNMATCHED_TABLE_ROW`, `_UnmatchedTableRow`) are always
  imported; `FALLBACK_HTML_STR` is added when `need_fallback=True`
  (caller passes `any("FALLBACK_HTML_STR" in l for l in self._dom.extra_utilities)`).
- **Module with REST structs** (`module_has_rest == True`): REST names
  appended on top.

This replaces the previous greedy export list that pulled every HTML
helper even into REST-only modules.

### End-to-end verification

`tests/test_rest_api.py::TestSeparateRuntime` exercises:

- `test_main_imports_present_under_runtime` — pins the required import
  surface (TypedDict/Literal/dataclass/httpx) under `-R`.
- `test_runtime_file_imports_httpx_when_rest` — runtime file contains
  `import httpx` and is itself executable.
- `test_combined_rest_and_html_module_under_runtime` — mixed module
  (REST struct + HTML struct in one `.kdl`) keeps lxml imports, the
  `FALLBACK_HTML_STR` import from runtime, AND REST-side imports. This
  is the cdnvideohub/kodik/aniboom regression from `anicli-api`.
- `test_main_valid_python` — exec'd via `_exec_with_runtime`, not
  `pyast.parse`. `pyast.parse` only checks syntax and silently passes
  code with unresolved `NameError`s; `exec(compile(...))` actually
  resolves names.

### Known follow-ups (out of scope)

- `convert_batch` (`visitor.py`) does not propagate `runtime_module` /
  `http_client` meta between modules in batch mode. Unused by `main.py`
  (which calls `converter.convert(ast)` per file).
- `_imports` and `_std_imports` pools in `ModuleBuilder` are separate
  dicts without cross-dedup. Pre-existing duplicates (`import re` may
  appear in both sections of the output). Legal Python, cosmetic only.
- std helpers (`std_repl_map`, `std_unescape_text`) are inlined into
  every parser file under `-R` (N copies for N files). Could be moved
  to the runtime file — separate refactor.
