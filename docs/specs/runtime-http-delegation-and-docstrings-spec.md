# Specification: Runtime HTTP Delegation, Multi-Line Docstring Normalization, and Runtime Block Cleanup

## Problem Statement

When generating parser and client code from **REST schemas**, **HTML schemas**, and **Raw schemas** that declare `@request` and `@doc` directives, developers and maintainers face three interconnected problems:

1. **Bloated Generated Request Methods Across All Four Targets**:
   Generated **Request** methods (`MethodRest` on **REST schemas** and `MethodFetch` on **HTML schemas** / **Raw schemas**) inline repetitive transport and request-preparation mechanics inside every emitted method rather than delegating them to the target runtime:
   - In Python and JavaScript, every generated method constructs intermediate dictionary builders (`_params`, `_headers`, `_cookies`) with conditional `None` / `undefined` checks for optional placeholders, initializes a mutable `_kw` / `_opts` object, and emits a multi-line shallow-merge loop (`for _k, _v in kwargs.items(): ...` / `for (const [_k, _v] of Object.entries(opts))`) before invoking the transport helper.
   - In Go, every generated REST method manually initializes `_opts`, loops over functional options (`for _, o := range opts`), calls `sscRestCall`, checks `err != nil`, extracts `response_path` via `gjson`, and unmarshals the JSON payload into the target struct. Similarly, every generated `MethodFetch` constructor (`New<Struct><Method>`) inlines 60+ lines of `http.NewRequestWithContext`, header/cookie/body assignment, status-code checking, and `gjson` extraction.
   - In Rust, there is no shared runtime helper for **Request** execution at all: every generated `MethodRest` and `MethodFetch` method inlines 45–65 lines of `reqwest` execution, HTTP status checks, `serde_json` parsing, error matcher dispatch, and `response_path` / `response_join` extraction.

2. **Corrupted Multi-Line `@doc` Docstrings in Generated Code**:
   When a schema author writes a multi-line `@doc """..."""` block on a module, struct, function, or `@request`, the parser stores the raw KDL string value without stripping uniform leading indentation or surrounding newlines (`inspect.cleandoc`). In the Python **Schema converter**, `node.doc` is emitted via `repr(node.doc)` (`f"{indent}{node.doc!r}"`), which collapses multi-line descriptions into a single-line single-quoted string literal containing raw `\n` escape sequences and KDL indentation spaces (e.g. `'\\n    Aniliberty API client.\\n    '`) instead of a properly indented Python docstring. In JavaScript, Go, and Rust, uncleaned `@doc` strings emit leading/trailing blank comment lines and preserve raw KDL indentation inside `//` and `/** ... */` docblocks.

3. **Noisy String-List Runtime Definitions in Schema Converters**:
   Target runtime modules and **HttpLibStrategy** implementations store 100–160 line runtime blocks as Python `list[str]` arrays of single-line string literals (`["def ssc_rest_call(", "    client: ...", ...]`) and thread manual indentation prefixes (`i1`, `i2`, `i3`) through helper functions, making the runtime source hard to read, audit, and maintain.

## Solution

1. **Delegate Request Preparation and Response Handling to Target Runtimes**:
   Move option filtering, caller option merging, `response_path` / `response_join` extraction, and JSON unmarshaling into the target runtime helpers across Python, JavaScript, Go, and Rust while preserving the exact public signatures and return types of all generated parser and client methods:
   - **Python**: Enrich `ssc_rest_call` / `ssc_rest_call_async` and introduce a shared request-options helper (`ssc_merge_kwargs` / transport fetch helpers) so the runtime automatically filters `None` values from DSL-supplied `params`, `headers`, and `cookies` dictionaries (while preserving `None` as JSON `null` inside `json` request bodies) and shallow-merges caller `**kwargs` on top. Generated `MethodRest` and `MethodFetch` bodies shrink to a single `return` statement (3–5 lines per method).
   - **JavaScript**: Enrich `sscRestCall` / `sscRestCallAxios` (and add `sscFetch` / `sscFetchAxios` runtime helpers for `MethodFetch`) to strip `undefined` / `null` entries from DSL `params` and `headers`, construct `URLSearchParams` when needed, merge caller `opts`, and extract `response_path` / `response_join`. Generated static async methods shrink to a single `return` statement.
   - **Go**: Add generic runtime helpers `sscRestCallValue[T any]`, `sscRestCallSlice[T any]`, `sscRestCallVoid`, and `sscFetchHTML` to the Go runtime. These helpers apply functional options (`opts ...sscReqOpt`), execute the HTTP request, extract `response_path` / `response_join` via `gjson`, and unmarshal typed JSON responses. Generated Go REST and fetch methods shrink from 35–65 lines to 3–5 lines.
   - **Rust**: Add `rt::rest_call`, `rt::rest_call_void`, and `rt::fetch_html` to the Rust runtime so generated `MethodRest` and `MethodFetch` methods only assemble the `reqwest::RequestBuilder` and delegate execution, status handling, error matching, and JSON/text decoding to `rt::*`.

2. **Normalize `@doc` Strings with `cleandoc` and Emit Multi-Line Python Docstrings**:
   - Normalize all `@doc` directive values and `@request doc="..."` properties at parse time using `inspect.cleandoc` so AST `.doc` fields contain clean, dedented text across all targets.
   - In the Python **Schema converter**, format `.doc` strings via a dedicated docstring helper that emits `"""..."""` with every line indented to the enclosing block's `WalkContext` indentation rather than emitting `repr(node.doc)`.

3. **Replace Line-Array Runtime Definitions with `cleandoc` Multi-Line Blocks**:
   Replace `list[str]` line arrays in Python, JavaScript, and Go runtime definitions and **HttpLibStrategy** implementations with readable triple-quoted blocks normalized via `inspect.cleandoc(...).splitlines()`.

## User Stories

1. As a schema author writing a multi-line `@doc """..."""` block on a module, struct, function, or `@request`, I want leading KDL indentation and surrounding blank lines stripped automatically, so that generated docstrings and doc comments are cleanly formatted in Python, JavaScript, Go, and Rust.
2. As a Python developer inspecting a generated parser module with multi-line `@doc` blocks, I want proper `"""..."""` docstrings indented to the class or function body level instead of single-line `'\\n    ...'` literals with escaped newlines, so that IDE tooltips, `help()`, and linters render documentation properly.
3. As a Python developer inspecting generated **REST schema** and **HTML schema** classes, I want each generated request method (`fetch`, `async_fetch`, `<endpoint>`, `async_<endpoint>`) to consist of a clean signature, optional docstring, and a direct `return` call to the runtime helper, so that generated parser files are compact and easy to read.
4. As a Python consumer calling a generated request method with optional placeholders omitted (defaulting to `None`), I want the runtime to omit `None`-valued keys from DSL `params`, `headers`, and `cookies`, so that optional query parameters and headers are not sent as `"None"`.
5. As a Python, JavaScript, Go, or Rust consumer calling a generated POST/PUT/PATCH **Request** with a JSON body containing an optional placeholder set to `None` / `null`, I want the serialized JSON payload to preserve `"key": null`, so that nullable JSON body fields work without needing sentinel values.
6. As a Python consumer passing custom `headers={"X-Custom": "1"}` or `params={"extra": "yes"}` via `**kwargs` to a generated request method, I want the runtime to shallow-merge my dictionary entries on top of the DSL-defined `headers` or `params`, so that per-call overrides do not wipe out static headers or parameters declared in the schema.
7. As a Python developer using any supported **HttpLibStrategy** (`httpx`, `httpx2`, `aiohttp`, `requests`) and **HTTP I/O mode** (`both`, `sync`, `async`), I want both `MethodRest` and `MethodFetch` to preserve their exact public signatures, return types, and exception semantics whether runtime code is inlined or emitted via `--separate-runtime` (`-R`).
8. As a JavaScript developer using either the `fetch` or `axios` **HttpLibStrategy**, I want `sscRestCall` / `sscRestCallAxios` and `MethodFetch` runtime helpers to handle `URLSearchParams` construction, optional parameter filtering, and `opts` merging centrally in the runtime, so that generated class methods are single-statement delegations.
9. As a Go developer compiling multiple generated **REST schemas** and **HTML schemas** in the same package, I want `sscRestCallValue[T]`, `sscRestCallSlice[T]`, `sscRestCallVoid`, and `sscFetchHTML` in `sscgen_runtime.go` to encapsulate functional option application, `gjson` path extraction, and `json.Unmarshal`, so that generated `.go` parser files contain minimal boilerplate and compile cleanly under `go test`.
10. As a Rust developer compiling generated **REST schemas** and **HTML schemas**, I want `rt::rest_call`, `rt::rest_call_void`, and `rt::fetch_html` in the runtime module to handle `reqwest` execution, HTTP status checks, error matcher dispatch, and JSON/text path extraction, so that generated Rust endpoint methods are concise and pass `cargo test`.
11. As a maintainer of `ssc_codegen`, I want `emit_dict_builder`, `emit_obj_builder`, `emit_params_builder`, `_build_kw_dict`, `_prepare_request`, and manual `i1`/`i2`/`i3` indentation threading removed from the target `rest` generators, so that modifying HTTP codegen does not require editing deeply nested string-append loops.
12. As a maintainer of `ssc_codegen`, I want static runtime definitions in Python, JavaScript, and Go stored as `inspect.cleandoc("""...""")` blocks rather than `list[str]` arrays of quoted lines, so that runtime code can be read and edited as normal code.

## Implementation Decisions

1. **Compile-Time `@doc` Normalization and Python Docstring Formatting**:
   - Normalize `@doc` arguments and `@request doc="..."` properties with `inspect.cleandoc` when populating `Module.doc`, `StructBase.doc`, `MethodRest.doc`, and `FunctionDef.doc` in the KDL reader and struct parser.
   - Introduce a Python docstring formatting helper used across `Module`, `Struct`, `StructRest`, `FunctionDef`, and `MethodRest`:
     - Single-line docstrings without embedded newlines emit `f'{indent}"""{escaped}"""'` (escaping `\` and `"""` safely).
     - Multi-line docstrings emit an opening `f'{indent}"""'`, each line prefixed with `indent` (or empty line for blank lines), and a closing `f'{indent}"""'`.

2. **Python Runtime Request Delegation (`ssc_rest_call`, `ssc_merge_kwargs`, and `MethodFetch`)**:
   - Add a compact runtime helper `ssc_merge_kwargs(base_kw, user_kw)` (or integrate directly into `ssc_rest_call` / `ssc_rest_call_async` and `MethodFetch` helpers) that:
     - For dictionary request options (`headers`, `params`, `cookies`), filters out entries whose value is `None` from the DSL-supplied dictionary, then shallow-merges any corresponding dictionary from caller `kwargs`.
     - Preserves `json` and `data` payload values as-is (without stripping `None` values inside `json` dicts) unless overridden by caller `kwargs`.
   - Remove `emit_dict_builder`, `dict_needs_builder`, `_build_kw_dict`, and `_merge_loop_lines` from Python REST codegen.
   - Emit `MethodRest` and `MethodFetch` methods as thin 3–5 line classmethods that pass DSL `headers`, `params`, `cookies`, and `json`/`data` expressions plus `**kwargs` directly to the runtime / strategy call.
   - When `--separate-runtime` (`-R`) is used, export any new shared helper names in `runtime_export_names`.

3. **JavaScript Runtime Request Delegation (`sscRestCall`, `sscRestCallAxios`, `sscFetch`, `sscFetchAxios`)**:
   - Extend the JavaScript REST and fetch runtime helpers so they accept a DSL options object (`{ params, headers, body }`) and caller `opts = {}`:
     - Strip `undefined` and `null` values from DSL `params` and `headers`.
     - Handle array query parameter styles (`repeat` / `bracket` / `csv` / `pipe` / `space`) and `URLSearchParams` construction inside the runtime helper for `fetch` and `axios`.
     - Shallow-merge caller `opts` (merging nested object keys such as `headers` key-by-key).
     - Handle `response_path` and `response_join` extraction for `MethodFetch` inside the runtime helper.
   - Remove `emit_obj_builder`, `emit_params_builder`, `_params_need_builder`, `_prepare_request`, and inline `Object.entries(opts)` merge loops from JavaScript REST codegen.

4. **Go Generic Runtime Helpers (`sscRestCallValue`, `sscRestCallSlice`, `sscRestCallVoid`, `sscFetchHTML`)**:
   - Extend the Go runtime (`sscgen_runtime.go`) with:
     - `sscRestCallValue[T any](client *http.Client, matchers []sscErrMatcher, method, url, responsePath string, dslOpts *sscReqOpts, opts ...sscReqOpt) (*T, error)`
     - `sscRestCallSlice[T any](client *http.Client, matchers []sscErrMatcher, method, url, responsePath string, dslOpts *sscReqOpts, opts ...sscReqOpt) ([]T, error)`
     - `sscRestCallVoid(client *http.Client, matchers []sscErrMatcher, method, url string, dslOpts *sscReqOpts, opts ...sscReqOpt) (struct{}, error)`
     - `sscFetchHTML(ctx context.Context, client *http.Client, structName, method, url, responsePath, responseJoin string, dslOpts *sscReqOpts, opts ...sscReqOpt) (string, error)`
   - Update Go `emit_method_rest` and `emit_method_fetch` to delegate to these runtime helpers, reducing generated Go methods to 3–5 lines while keeping identical public function/method signatures.

5. **Rust Runtime Request Helpers (`rt::rest_call`, `rt::rest_call_void`, `rt::fetch_html`)**:
   - Extend the Rust runtime (`runtime.rs`) with async helper functions:
     - `pub async fn fetch_html(req: reqwest::RequestBuilder, context: &str, response_path: Option<&str>, response_join: Option<&str>) -> Result<String, SscError>`
     - `pub async fn rest_call<T, E, M, D>(req: reqwest::RequestBuilder, context: &str, response_path: Option<&str>, match_err: M, decode: D, unknown_err: fn(u16, Value) -> E) -> Result<T, E>` (and `rest_call_void` for unit `()` responses).
   - Update Rust `emit_method_fetch` and `emit_method_rest` to build `req` via `_emit_request_builder` and end with a single `rt::fetch_html(...).await` or `rt::rest_call(...).await` call.

6. **Multi-Line `cleandoc` Runtime Blocks**:
   - Convert `list[str]` runtime source arrays in Python (`generation/runtime.py` and `targets/python/http_libs/*.py`), JavaScript (`REST_SHARED` and `targets/javascript/http_libs/*.py`), and Go (`BASE_RUNTIME` and `BASE_REST_RUNTIME` in `targets/golang/runtime.py`) to `inspect.cleandoc("""...""").splitlines()`.

## Testing Decisions

- **Single High-Level Seam (`parse_module` -> `converter.convert` / `converter.convert_all` -> target runtime execution)**:
  - All tests must validate external behavior through the existing end-to-end compilation and **Toolchain validation** seam: parsing KDL schemas via `parse_module`, generating target code via the **Schema converter**, and executing the generated parser/client methods against mocked HTTP transports (`respx`, `aioresponses`, `responses` in Python; `node` in JavaScript; `go test` in Go; `cargo test` in Rust).
  - Verify multi-line `@doc` formatting by parsing schemas with multi-line `@doc """..."""` blocks on modules, structs, functions, and `@request` nodes, confirming valid syntax (`ast.parse` in Python, `gofmt`, `rustfmt`, `node --check`) and checking `cls.__doc__` / `fn.__doc__` in Python.
  - Update any codegen smoke assertions that previously coupled to inlined method-body boilerplate (such as asserting literal `_kw["json"] = ...` inside the method body rather than testing that the request sends the expected JSON body and keyword arguments) so tests assert on public contracts and runtime behavior.
- **Prior Art**:
  - `tests/test_rest_api.py`
  - `tests/test_http_io.py`
  - `tests/integration/test_rest_codegen.py`
  - `tests/integration/test_html_fetch_codegen.py`
  - `tests/js/test_js_codegen.py`
  - `tests/go/test_go_codegen.py`
  - `tests/rust/test_rust_codegen.py`

## Out of Scope

- Introducing external templating dependencies such as `jinja2` into `pyproject.toml`.
- Changing `BaseWalker` AST node granularity or pipeline/predicate visitor handlers (`visit_*` for selectors, string operations, regexes, or predicates).
- Changing the public signatures, method names, parameter types, or return types (`Ok`/`Err` unions in Python/JS, `(*T, error)` in Go, `Result<T, EndpointError>` in Rust) of generated parser and REST client classes.

## Further Notes

- Documented in `ADR-0006` (`docs/adr/0006-runtime-http-delegation-and-no-template-engine.md`).
- Uses canonical vocabulary from `CONTEXT.md` (**REST schema**, **HTML schema**, **Raw schema**, **Request**, **Schema converter**, **HttpLibStrategy**, **HTTP I/O mode**, **WalkContext**, **Runtime HTTP delegation**, **Toolchain validation**).
