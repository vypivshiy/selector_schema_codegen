# Specification: Rust Target Feature Parity — HTML fn, Raw Nested, Async Reqwest Transport, and Typed REST Endpoints

## Problem Statement

Users of `ssc_codegen` who generate scrapers, data extractors, and HTTP client modules in Rust currently face substantial functional limitations and feature gaps compared to the Python and Go backend targets:

1. **Top-Level HTML Functions**: While `(raw)fn` is supported for plain-text pipelines, non-raw HTML `fn` declarations cannot be compiled to Rust. The code generator lacks the capability to instantiate a DOM document tree, initialize an arena root selection, and evaluate pipeline operations outside the context of a parser struct instance.
2. **Nested Invocations in Raw Contexts**: In `(raw)struct` or `(raw)fn` pipelines, passing extracted string slices into `nested` child parsers fails. The generator unconditionally assumes an HTML DOM context, attempting to clone DOM handles and extract arena node identifiers rather than instantiating the child parser with the input string. Furthermore, the compiler's pipeline type checking restricts `nested` inputs to `DOCUMENT`, rejecting valid string pipelines targeting raw or HTML child parsers.
3. **Automated HTTP Transport for HTML Scrapers**: HTML schemas specifying `@request` directives cannot generate automated network transport in Rust. Users must manually orchestrate HTTP clients, assemble URLs with placeholder interpolation, encode query parameters, construct headers and cookie strings, and deserialize payload bodies.
4. **Typed REST Client Endpoints**: Scraper developers defining `(rest)struct` endpoints cannot generate idiomatic Rust API client libraries. The generator does not synthesize strongly typed error enums (`EndpointError`) representing declared `@error <status>` codes, cannot match JSON property conditions on error payloads, does not produce canonical `Result<T, EndpointError>` aliases, and lacks response deserialization into declared `json` models.

Rust developers need a fully capable target converter that produces safe, strongly typed, asynchronous, and idiomatic Rust parser and client modules matching the operational capabilities of Python and Go.

## Solution

Extend the Rust target backend to achieve complete operational parity with Python and Go across top-level functions, nested parsing, network transport, and REST endpoints:

1. **Dynamic DOM and Top-Level HTML Functions**: Enable compilation of top-level `fn` declarations by parsing input text into `dom_query::Document`, creating reference-counted interior mutability DOM handles (`Rc<RefCell<Document>>`), resolving root node IDs, and evaluating pipelines from the document root. Dynamic visitor targeting helpers allow pipeline operations to bind seamlessly to either local function bindings or struct instance fields.
2. **Raw Context and String `nested` Dispatch**: Extend `nested` handling to inspect enclosing context and child parser types. In raw contexts or when targeting raw child structs, the generated code directly invokes `ChildParser::new(&input)?.parse()?`. Update compiler type checking so `nested` accepts `STRING` pipelines in addition to `DOCUMENT`.
3. **Asynchronous `reqwest` Transport (`MethodFetch`)**: Generate asynchronous associated methods `pub async fn fetch(client: &reqwest::Client, ...) -> Result<Self, rt::SscError>` on parser structs. Implement template rendering for URL path placeholders, query parameters (with scalar, optional, and array serialization styles), custom request headers, semicolon-delimited cookie headers, and JSON/form/raw request bodies. Support `response-path` JSON dot-path navigation and `response-join` array concatenation.
4. **Typed `(rest)struct` Endpoints and `EndpointError` Enums**: For each `(rest)struct`, synthesize a strongly typed enum deriving `Debug`, implementing `std::fmt::Display`, `std::error::Error`, `From<reqwest::Error>`, and exposing `pub fn status(&self) -> Option<u16>`. Synthesize typed error variants for each declared `@error` status code, a `Transport(reqwest::Error)` variant for network failures, and an `Unknown(u16, serde_json::Value)` variant for unhandled status codes. Emit canonical `pub type {Alias} = Result<{OkType}, {Struct}Error>;` type aliases and asynchronous endpoint methods that execute requests, evaluate status and key condition matchers, and deserialize responses into typed `json` models.
5. **Runtime Support**: Extend the shared runtime (`sscgen_runtime.rs`) with `rt::json_opt` for zero-allocation dot-path navigation over `serde_json::Value` instances to power error condition matching and response path extraction.

## User Stories

1. As a Rust scraper developer, I want to compile a top-level HTML `fn` declaration into a standalone Rust function using `ssc-gen generate rust`, so that I can execute lightweight extraction pipelines without instantiating a parser struct.
2. As a Rust scraper developer, I want a generated top-level HTML function to accept any type implementing `Into<String>`, so that I can pass string slices, owned strings, or reference-counted text without manual conversions.
3. As a Rust scraper developer, I want a generated top-level HTML function to instantiate `dom_query::Document`, wrap it in an `Rc<RefCell<Document>>`, resolve the root node ID, and evaluate pipeline operations from that root, so that standard CSS selectors execute predictably.
4. As a Rust scraper developer, I want docstrings on top-level `fn` declarations to be emitted as Rust documentation comments (`///`), so that public functions are clearly documented in generated crates.
5. As a Rust scraper developer, I want top-level HTML functions to support DOM side effects like `css-remove`, so that unneeded elements can be pruned during function-level extraction.
6. As a Rust scraper developer, I want to invoke `nested` inside a `(raw)struct` pipeline on an extracted string value, so that sub-component parsers can process raw substrings or embedded markup fragments.
7. As a Rust scraper developer, I want a raw `nested` call to emit `ChildParser::new(&input)?.parse()?`, so that the child parser is constructed directly from the string slice without DOM overhead.
8. As a Rust scraper developer, I want to invoke `nested` on a raw child struct from an HTML DOM pipeline, so that plain-text child parsers can process extracted HTML text or attribute values.
9. As a Rust scraper developer, I want compiler type checking to accept `STRING` inputs for `nested` pipelines when targeting raw or HTML child structs, so that schemas with string-to-parser delegation pass schema validation (`ssc-gen check`).
10. As a Rust scraper developer, I want compiler type checking to reject incompatible inputs for `nested` (such as `LIST_STRING` or scalar integers), so that invalid pipeline types are flagged at build time with clear diagnostics.
11. As a Rust scraper developer, I want `ssc-gen generate rust` to accept `--http-client reqwest`, so that I can configure asynchronous HTTP client generation for schemas specifying `@request`.
12. As a Rust scraper developer, I want unsupported HTTP client options for Rust (such as `aiohttp`, `httpx`, `fetch`, or `axios`) to be rejected with actionable error messages during CLI target resolution, so that I am guided to use `reqwest`.
13. As a Rust scraper developer, I want HTML and raw parser structs with `@request` directives to generate an asynchronous associated method `pub async fn fetch(client: &reqwest::Client, ...) -> Result<Self, rt::SscError>`, so that I can fetch and parse documents in a single asynchronous call.
14. As a Rust scraper developer, I want named `@request` directives to generate corresponding named fetch methods (such as `fetch_<name>`), so that structs with multiple fetch sources can provide distinct entry points.
15. As a Rust scraper developer, I want typed placeholders in request URLs (e.g. `{{id:int}}`, `{{slug:str}}`) to map to idiomatic Rust function parameter types (`i64`, `f64`, `bool`, `&str`), so that callers benefit from compile-time type safety.
16. As a Rust scraper developer, I want optional placeholders (e.g. `{{filter:str?}}`) to map to `Option<T>` function parameters, so that optional parameters can be omitted cleanly.
17. As a Rust scraper developer, I want query parameter placeholders marked as optional to be omitted from the request URL query string when `None` is passed, so that clean URLs are generated.
18. As a Rust scraper developer, I want array query parameters to support all DSL serialization styles (`csv`, `pipe`, `space`, `repeat`, `bracket`), so that APIs with varied array conventions can be queried correctly.
19. As a Rust scraper developer, I want request headers declared in `@request` blocks to be formatted with placeholder values and added to the outgoing request builder, so that required custom headers (such as `Accept` or `User-Agent`) are sent reliably.
20. As a Rust scraper developer, I want cookie declarations in `@request` blocks to be formatted as an RFC 6265 semicolon-delimited `Cookie` header, with optional cookies omitted when `None`, so that session authentication headers are correctly assembled.
21. As a Rust scraper developer, I want JSON request bodies declared in `@request` to be serialized using `serde_json::json!(...)` with embedded placeholder expressions, so that structured JSON payloads can be sent with type safety.
22. As a Rust scraper developer, I want form-urlencoded and raw request bodies declared in `@request` to be encoded and sent with appropriate `Content-Type` headers, so that non-JSON endpoints can be targeted.
23. As a Rust scraper developer, I want `response-path` directives on `@request` to extract nested JSON string fragments using dot-notation, so that HTML payloads embedded inside JSON responses can be extracted and parsed.
24. As a Rust scraper developer, I want `response-join` directives on `@request` to concatenate array responses with a declared delimiter, so that paginated or chunked responses can be reconstituted before parsing.
25. As a Rust scraper developer, I want `MethodFetch` to verify that the HTTP response status code is `< 400`, returning an explicit `rt::SscError` on HTTP error statuses, so that server errors abort parsing immediately.
26. As a Rust scraper developer, I want `(rest)struct` schemas to generate dedicated client endpoint structs with a default constructor (`new()`), so that endpoint methods can be organized cleanly.
27. As a Rust scraper developer, I want each `(rest)struct` to generate a dedicated enum `#[derive(Debug)] pub enum {Struct}Error`, so that all failure modes of the endpoint are captured in a strongly typed error domain.
28. As a Rust scraper developer, I want each declared `@error <status>` directive to generate a corresponding typed variant in the endpoint error enum, so that API error responses can be pattern-matched exhaustively.
29. As a Rust scraper developer, I want an `@error` variant whose response schema specifies a typed `json` model to carry that deserialized model instance, so that structured error details can be inspected directly.
30. As a Rust scraper developer, I want an `@error` variant without a response schema to carry raw `serde_json::Value`, so that unmodeled error bodies remain accessible.
31. As a Rust scraper developer, I want the endpoint error enum to include a `Transport(reqwest::Error)` variant, so that network failures, timeouts, and DNS resolution errors are wrapped without loss of diagnostic detail.
32. As a Rust scraper developer, I want the endpoint error enum to include an `Unknown(u16, serde_json::Value)` variant, so that unexpected HTTP status codes outside declared `@error` rules are captured cleanly.
33. As a Rust scraper developer, I want the endpoint error enum to implement `std::fmt::Display` and `std::error::Error`, so that it integrates seamlessly with standard Rust error handling ecosystems (`anyhow`, `eyre`).
34. As a Rust scraper developer, I want the endpoint error enum to implement `From<reqwest::Error>`, so that transport errors can be propagated with the `?` operator.
35. As a Rust scraper developer, I want the endpoint error enum to provide a `pub fn status(&self) -> Option<u16>` method, so that callers can inspect HTTP status codes without matching every variant.
36. As a Rust scraper developer, I want the generator to emit canonical type aliases `pub type {Alias} = Result<{OkType}, {Struct}Error>;`, so that callers can declare return types concisely.
37. As a Rust scraper developer, I want type aliases in multi-REST schemas to be qualified with the struct name when collisions would otherwise occur, so that multi-endpoint schemas compile without ambiguous symbol errors.
38. As a Rust scraper developer, I want each endpoint method in a `(rest)struct` to be generated as an asynchronous associated function taking `&reqwest::Client` and declared placeholders, so that requests can be executed concurrently.
39. As a Rust scraper developer, I want endpoint methods to match HTTP response status codes and evaluate key condition rules against JSON error bodies, so that specific error variants are dispatched accurately.
40. As a Rust scraper developer, I want error condition matching to support string literals, numeric values, booleans, null checks, and field presence, so that complex polymorphic error envelopes can be distinguished.
41. As a Rust scraper developer, I want error matching to fall back to generic status matchers if specific key conditions are not satisfied, so that unpredicted error formats still map to the appropriate status code variant.
42. As a Rust scraper developer, I want successful HTTP responses to be deserialized into the declared `json` response model, so that API success payloads yield strongly typed Rust data structures.
43. As a Rust scraper developer, I want endpoints with void responses to return `Result<(), {Struct}Error>`, so that 204 No Content or bodyless operations are supported cleanly.
44. As a Rust scraper developer, I want endpoints specifying `response-path` to extract sub-objects or arrays before deserializing into the response model, so that enveloped API responses can be projected directly to inner entities.
45. As a Rust scraper developer, I want `serde_json::Value` and required runtime imports to be registered automatically via the module builder, so that generated REST modules compile without missing import errors.

## Implementation Decisions

- **Dynamic Traversal Targeting**: Rather than hardcoding references to `self.dom` or parser instance fields, visitor emission uses context-aware helpers (`_is_in_function`, `_dom_ref`, `_dom_clone`, `_context`) to determine whether emission occurs inside a top-level function or a parser struct method. Inside functions, DOM operations reference the locally scoped `dom` binding (`Rc<RefCell<Document>>`); inside structs, they reference `self.dom`.
- **Top-Level HTML Function Structure**: Top-level `fn` declarations emit a standalone public function `pub fn {name}(document: impl Into<String>) -> Result<{ReturnType}, rt::SscError>`. For HTML functions, the document string is parsed into `dom_query::Document`, wrapped in `Rc::new(RefCell::new(document))`, and the root node ID is extracted via `rt::root_id(&dom)`. The initial pipeline step seeds from `vec![root]`, executes all pipeline operations sequentially, and returns `Ok(result)`.
- **Prototype Snippet — Top-Level HTML Function**:
  *(Encoding the DOM root evaluation and arena lifecycle established in the prototype)*
  ```rust
  pub fn parse_title(document: impl Into<String>) -> Result<String, rt::SscError> {
      let document = Document::from(document.into());
      let dom = Rc::new(RefCell::new(document));
      let root = rt::root_id(&dom);
      let v = vec![root];
      let v1 = rt::select(&dom, &v, "h1")?;
      let v2 = rt::first_text(&dom, &v1)?;
      Ok(v2)
  }
  ```
- **Raw and String `nested` Dispatch**: When `visit_nested` is called within a raw context or when the target child parser is a raw struct, the visitor emits `let {nxt} = {Child}Parser::new(&{prv})?.parse()?;`. When called in an HTML context targeting an HTML parser, it passes the cloned DOM handle and first node: `let {nxt} = {Child}Parser::from_existing({dom}, rt::first_node(&{prv}, "{context}")?)?.parse()?;`.
- **Pipeline Type Inference Update**: In the compiler core, pipeline type checking (`check_pipeline_types`) is broadened so that `nested` accepts `STRING` inputs in addition to `DOCUMENT`. This enables valid KDL pipelines that extract text or JSON strings and immediately delegate parsing to child parsers.
- **Asynchronous Network Transport**: All generated network transport uses `reqwest` in asynchronous mode (`pub async fn ...`). Synchronous/blocking transport is intentionally not generated. Generated code depends on `reqwest` with default features disabled and `json` enabled.
- **Placeholder Typing and Escaping**: Template placeholders are mapped to idiomatic Rust parameter types via `rust_ph_type`: scalars map to `i64`, `f64`, `bool`, and `&str`; optionals map to `Option<T>`; arrays map to borrowed slices `&[T]`. URL formatting escapes literal braces (`{` -> `{{`, `}` -> `}}`) and substitutes `{}` placeholders into `format!(...)`.
- **Query Parameter Serialization**: Query parameters support scalar interpolation, omission when optional values are `None`, and array parameter serialization supporting five DSL styles: `csv` (comma-separated), `pipe` (pipe-separated), `space` (space-separated), `repeat` (repeated query keys `key=a&key=b`), and `bracket` (bracketed repeated keys `key[]=a&key[]=b`).
- **REST Error Model & Enum Synthesis**: For each `(rest)struct`, an endpoint error enum is synthesized:
  *(Encoding the error enum shape and trait implementations established in the prototype)*
  ```rust
  #[derive(Debug)]
  pub enum ApiError {
      Err400(serde_json::Value),
      Err404(ErrorDetailJson),
      Transport(reqwest::Error),
      Unknown(u16, serde_json::Value),
  }

  impl std::fmt::Display for ApiError {
      fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
          match self {
              Self::Err400(val) => write!(f, "HTTP 400: {:?}", val),
              Self::Err404(val) => write!(f, "HTTP 404: {:?}", val),
              Self::Transport(err) => write!(f, "Transport error: {}", err),
              Self::Unknown(status, val) => write!(f, "HTTP {}: {:?}", status, val),
          }
      }
  }

  impl std::error::Error for ApiError {}

  impl From<reqwest::Error> for ApiError {
      fn from(err: reqwest::Error) -> Self {
          Self::Transport(err)
      }
  }

  impl ApiError {
      pub fn status(&self) -> Option<u16> {
          match self {
              Self::Err400(_) => Some(400),
              Self::Err404(_) => Some(404),
              Self::Transport(_) => None,
              Self::Unknown(status, _) => Some(*status),
          }
      }
  }
  ```
- **Result Type Aliases**: For each endpoint, canonical type aliases are synthesized: `pub type {Alias} = Result<{OkType}, {Struct}Error>;`. In schemas with multiple REST structs, alias names are qualified with the struct name to guarantee unique, collision-free symbols.
- **REST Endpoint Dispatching**: Endpoint functions execute the request via `client.request(...)`, inspect the response status, and if `< 400`, deserialize the body into the declared response `json` model (optionally navigating `response-path` via `rt::json_opt`). If the status is `>= 400`, the body is parsed into `serde_json::Value`, matched against declared error matchers and condition predicates, and returned in the corresponding `Err` variant.
- **Runtime Dot-Path Navigation**: The runtime module `sscgen_runtime.rs` provides `pub fn json_opt<'a>(value: &'a Value, path: &str) -> Option<&'a Value>` for zero-allocation dot-path traversal over `serde_json::Value`, supporting nested field checks and fragment extractions without full deserialization overhead.
- **Two-Pass Accumulation and Import Registration**: REST artifacts and required imports (`use serde_json::Value;`) are registered through `ModuleBuilder` during AST traversal. The visitor clears emitted alias state between pass 1 and pass 2 to prevent duplicate definitions in generated files.

## Testing Decisions

- **What Makes a Good Test**: Tests verify observable external behavior through public compiler interfaces and native compilation toolchains. Rather than asserting on transient visitor strings or private generator methods, tests compile complete `.kdl` schemas into temporary Cargo packages and invoke `cargo check`, `cargo fmt --check`, and `cargo test` to prove that the generated code is syntactically valid, adheres to compiler standards, and executes correctly against real inputs.
- **Highest Testing Seam**: The primary testing seam is the end-to-end integration pipeline:
  1. Input: Valid `.kdl` schema files representing HTML functions, raw nested parsers, `@request` HTML fetchers, and `(rest)struct` endpoints.
  2. Action: Execute `ssc-gen generate rust` via Python API / CLI runner into a temporary Cargo workspace containing a properly configured `Cargo.toml`.
  3. Verification: Execute `cargo test` on the generated crate with real test cases and mock HTTP servers (using `tokio` and native loopback TCP listeners), validating:
     - Standalone HTML `fn` execution and DOM side effects.
     - Raw string `nested` parsing.
     - Async `fetch()` execution with header/cookie/query interpolation.
     - Typed REST endpoint success deserialization.
     - Typed error variant matching (status codes, key conditions, and fallback unknown statuses).
     - Transport failure handling on connection refused.
- **Secondary Testing Seams**:
  - *Compiler Type Checking Seam*: Unit tests against `check_pipeline_types` asserting that `nested` accepts `STRING` pipelines and rejects incompatible input types (`LIST_STRING`, `INT`).
  - *Target Profile Resolution Seam*: Unit tests against `resolve(TargetSpec)` verifying that `http_client="reqwest"` is accepted and incompatible clients are rejected with actionable errors.
  - *Syntax and Diagnostic Seams*: CLI tests verifying that `generate rust` emits valid code for integration schemas and reports unsupported features cleanly.
- **Prior Art**:
  - Python REST test suite (`tests/integration/test_rest_codegen.py`, `tests/test_rest_api.py`) validating `@request` templates, placeholder interpolation, and status dispatching against mocked HTTP endpoints.
  - Go target test suite (`tests/go/test_go_codegen.py`) validating Go codegen using `gofmt`, `go vet`, and `go test` with local HTTP test servers.
  - Existing Rust target test suite (`tests/rust/test_rust_codegen.py`) validating HTML struct shapes, `@init` lifecycle, and detached DOM nodes.

## Out of Scope

- Synchronous (`blocking`) HTTP client generation in Rust (decided: asynchronous only with `reqwest`).
- XPath selector support in Rust converter (`dom_query` is CSS-selector only; XPath remains unsupported).
- In-process `health` and `scout` runner execution in Rust (`lxml` / Python remains the canonical engine for `ssc-gen health` and `scout`).
- Streaming / chunked payload decoding for large HTTP/REST responses in Rust.
- Persistent cookie store / session state sharing across multiple `@request` invocations on a single client instance.
- Multipart form body handling for Rust `@request` if introduced into DSL.

## Further Notes

- Projects consuming generated Rust parsers and REST endpoints require the following dependencies in their `Cargo.toml`:
  ```toml
  [dependencies]
  dom_query = "0.28"
  regex = "1"
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  serde_urlencoded = "0.7"
  reqwest = { version = "0.12", default-features = false, features = ["json"] }
  tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
  ```
- Target compatibility: Rust 2021 edition and newer (tested against stable toolchain `1.90+`).
