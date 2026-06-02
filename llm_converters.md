# Converter Architecture (converters/)

## BaseConverter (converters/base.py)

Callback-based visitor pattern:
```python
converter = BaseConverter(var_name="v", indent=" " * 4)

@converter.pre(NodeType, post_callback="handler_name")
def handler(node: NodeType, ctx: ConverterContext) -> str | list[str]: ...

@converter.post(NodeType)
def handler(node: NodeType, ctx: ConverterContext) -> str | list[str]: ...

@converter.file("support_file.py")
def provider(meta: dict) -> str: ...
```

## ConverterContext
Tracks conversion state:
- `index` → variable counter (v0, v1, v2...)
- `depth` → indentation level
- `prv` → previous variable name (input)
- `nxt` → next variable name (output)
- `indent` → current indentation string
- `advance()` → increment index
- `deeper()` → increase depth

## Converter hierarchy
```python
PY_BASE_CONVERTER = BaseConverter()  # shared Python handlers (py_bs4.py)
PY_BS4 = PY_BASE_CONVERTER          # BS4-specific
PY_LXML = PY_BASE_CONVERTER.extend()  # lxml overrides
PY_PARSEL = PY_BASE_CONVERTER.extend()
PY_SLAX = PY_BASE_CONVERTER.extend()
JS_CONVERTER = BaseConverter(indent=" " * 2)  # separate instance
```

All handlers are registered via `@converter.pre(NodeType)` / `@converter.post(NodeType)` decorators on PY_BASE_CONVERTER and JS_CONVERTER.

## Runtime templates (converters/runtime/)

Runtime helper functions (base utilities, REST types, JS helpers) live as string constants in `converters/runtime/`.
Converters import them instead of inlining — keeps converter files focused on handler logic.

| Module | Contents |
|--------|----------|
| `_helpers.py` | `_module_has_rest()`, `module_is_rest_only()`, `http_client_import()` — shared AST utilities |
| `py_base.py` | `NOT_REQUIRED_IMPORT`, `_BASE_UTILITY_LINES`, `_BASE_EXPORT_NAMES`, `base_utility_lines()` — Python base runtime strings |
| `py_rest.py` | `rest_imports()`, `rest_utilities()`, `runtime_export_names()`, `runtime_module_content()`, `register_runtime_file()` — REST assembly & `-R` support |
| `py_lxml.py` | `_FALLBACK_HTML_LINES`, `_FALLBACK_HTML_EXPORT` — lxml-specific fallback HTML constant |
| `js_base.py` | `JS_BASE_UTILITY_LINES`, `js_base_utility_lines()` — JS helper function strings |

`__init__.py` re-exports the public API. Converters do `from ssc_codegen.converters.runtime import ...`.

## RequestSpec pipeline (converters/request_spec.py)
`parse_to_spec(raw_payload) → RequestSpec` — parses curl/raw HTTP into normalized form.
`normalize_placeholder_names(spec, transform) → RequestSpec` — adapts placeholder names for target language.
Python rendering helpers live in `converters/py_render.py`.

---

## Transport layer (@request) — codegen behavior

Optional struct-level directive that embeds a raw HTTP request or POSIX curl command.
Converters parse it at codegen time (via `converters/request_spec.py`) and emit an HTTP fetch method.

```kdl
struct ApiData {
    @request response-path="payload.html" response-join="\n" """
    POST /api HTTP/1.1
    Host: example.com
    Content-Type: application/json

    {"id": "{{id}}"}
    """
}
```

`response-path` — dot-notation JSON path into the response body to extract the HTML string.
`response-join` — separator when the resolved path is a list of strings.

Generated code (Python `httpx`):
- Non-REST structs: `fetch(self, *, page_num: str) -> Self` and `async_fetch(...)`.
- `type=rest` structs: per-endpoint `@classmethod` methods with public Result type aliases.
  Each `@request name=X` produces `XResult = Union[Ok[T], ErrVariant, UnknownErr, TransportErr]`.

---

## Runtime separation (--separate-runtime / -R)

When enabled, helper functions are extracted into a separate runtime module instead of being inlined into each generated file.
- Default runtime module name: `sscgen_runtime` (customizable via `--runtime-name / -rn`)
- Generated parsers import helpers from the runtime module
- `@converter.file()` providers registered on the converter emit the runtime file
- Runtime content is assembled by `converters/runtime/py_rest.py` → `register_runtime_file()` and `runtime_module_content()`
