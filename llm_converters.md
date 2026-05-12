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

## RequestSpec pipeline (converters/request_spec.py)
`parse_to_spec(raw_payload) → RequestSpec` — parses curl/raw HTTP into normalized form.
`normalize_placeholder_names(spec, transform) → RequestSpec` — adapts placeholder names for target language.
Python rendering helpers live in `converters/py_helpers.py`.

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
