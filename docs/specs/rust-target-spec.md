# Specification: Rust Target Code Generator Backend (`dom_query` + `serde`)

## Problem Statement

Users of `ssc_codegen` who build web scrapers, data pipelines, and HTML/text extraction services in Rust currently cannot generate native, idiomatic Rust parsers from `.kdl` schema definitions. They are either forced to run external runtimes (such as Python or Node.js) through FFI/subprocesses, or maintain manual parsing logic using low-level DOM libraries. 

Furthermore, existing backend converters exhibit permissive JSON projections that conflict with Rust's strict compile-time type system, lack consistent Unicode scalar semantics across text operations, and lack uniform handling of detached DOM nodes when modifying trees via `css-remove`. Rust developers need a dedicated target backend that generates clean, strongly typed, memory-safe Rust parser crates with predictable error handling and zero overhead.

## Solution

A native Rust code generator backend for `ssc-gen` that translates HTML schemas and raw schemas into safe, idiomatic Rust 2021+ modules. The generated parsers utilize `dom_query` for pure-Rust CSS-based HTML parsing, `serde` and `serde_json` for strictly typed JSON serialization and deserialization, and `regex` for regular expression matching and substitutions.

Generated parsers use an owned instance lifecycle:
- A fallible constructor (`new`) that performs input ingestion and sequentially evaluates precomputed `@init` fields once.
- A repeatable `parse(&mut self)` method that executes `@pre-validate` assertions and extracts all declared output fields into strongly typed result structs.
- Unified fail-fast error reporting via an explicit `SscError` type.
- Fragment-first JSON extraction with strict schema validation.
- Safe DOM node tracking using stable arena identifiers (`NodeId`), enabling nested parsers and cached detached node access.
- A single consolidated runtime module (`sscgen_runtime.rs`) shared across all generated parser modules in a parent crate.

## User Stories

1. As a Rust scraper developer, I want to compile an HTML schema into a Rust parser using `ssc-gen generate rust <file.kdl>`, so that I can parse web documents natively in Rust without external language runtimes.
2. As a Rust scraper developer, I want the generated parser to provide a fallible constructor `new(html) -> Result<Self, SscError>`, so that initialization and `@init` precomputed fields run once and report failures early before parsing begins.
3. As a Rust scraper developer, I want precomputed fields defined in `@init` blocks to evaluate in strict declaration order, so that subsequent precomputations and field pipelines can safely reference cached values via `@name`.
4. As a Rust scraper developer, I want precomputed fields to remain private to the parser instance, so that intermediate DOM calculations do not pollute the public output data model.
5. As a Rust scraper developer, I want the generated parser to expose a repeatable `parse(&mut self) -> Result<OutputType, SscError>` method, so that I can re-parse or extract data multiple times without re-initializing the parser or re-allocating the document.
6. As a Rust scraper developer, I want `@pre-validate` assertions to run automatically at the start of each `parse()` call, so that malformed or unexpected page structures abort parsing immediately before field extraction.
7. As a Rust scraper developer, I want extracted output structures to own all their strings, collections, and nested models, so that the extracted results can outlive the parser instance and the underlying HTML document tree.
8. As a Rust scraper developer, I want `(item)struct` schemas to generate strongly typed Rust structs with `Serialize` derives, so that I can easily integrate parsed data into downstream serialization and storage pipelines.
9. As a Rust scraper developer, I want `(list)struct` schemas with `@split-doc` to return `Result<Vec<ItemType>, SscError>`, so that repeating elements on a page are mapped to strongly typed vectors.
10. As a Rust scraper developer, I want `(flat)struct` schemas to extract deduplicated `Vec<String>` results, so that flat lists of tags, URLs, or IDs can be collected into clean scalar collections.
11. As a Rust scraper developer, I want `(dict)struct` schemas with `@key` and `@value` pipelines to produce `HashMap<String, ValueType>`, so that dynamic key-value properties can be extracted flexibly.
12. As a Rust scraper developer, I want `(table)struct` schemas with `@table`, `@rows`, `@match`, and field pipelines to extract key-value row mappings, so that irregular tabular specifications can be transformed into structured data.
13. As a Rust scraper developer, I want `(raw)struct` and `(raw)fn` schemas to operate on plain text without invoking an HTML DOM engine, so that plain text strings, JSON scripts, and custom payloads can be parsed with minimal overhead.
14. As a Rust scraper developer, I want `css-remove` DOM side effects to detach nodes from the document tree while keeping cached precomputed references accessible, so that removed nodes do not match future document queries while preserving cached references.
15. As a Rust scraper developer, I want `nested` struct calls to execute child parsers on the same shared document tree, so that sub-component parsers can run without reparsing or cloning the underlying HTML markup.
16. As a Rust scraper developer, I want named `@check` pipelines to be generated as public boolean methods returning `Result<bool, SscError>`, so that I can check document state and layout variants without performing full extraction.
17. As a Rust scraper developer, I want `jsonify` operations to deserialize JSON fragments based on the cardinality of the named `json` schema, so that fragment paths select input subsets while the target schema strictly dictates whether the output is a model or a vector of models.
18. As a Rust scraper developer, I want `from="..."` key aliases in JSON schemas to support dot-path navigation over input payloads, so that deeply nested or strangely named wire JSON keys can be projected into clean, canonical field names.
19. As a Rust scraper developer, I want missing required JSON fields or type mismatches to produce explicit `SscError` errors, so that schema contract violations are identified immediately.
20. As a Rust scraper developer, I want JSON fields with `?` or `@omitempty` to map to `Option<T>` with `skip_serializing_if = "Option::is_none"`, so that optional values serialize cleanly without null clutter.
21. As a Rust scraper developer, I want string operations like `slice`, `index`, and `len` to measure Unicode scalar values rather than raw UTF-8 bytes, so that multi-byte international text and emojis are sliced and indexed accurately.
22. As a Rust scraper developer, I want `fallback` expressions to recover from failures in wrapped operations and produce fallback literals or `None` on `fallback #null`, so that non-critical field errors do not abort the entire document parse.
23. As a Rust scraper developer, I want regular expression operations to translate replacement backreferences into Rust regex syntax, so that `$1` and `\1` group substitutions work predictably across backends.
24. As a Rust scraper developer, I want regex patterns containing lookaround assertions or backreferences to be rejected with a clear generation diagnostic, so that incompatible regex syntax does not cause unexpected compile errors in generated Rust crates.
25. As a Rust scraper developer, I want user-defined `extension` operations with a `rust` target block to inject custom expressions and runtime helpers, so that project-specific parsing logic can seamlessly integrate into KDL pipelines.
26. As a Rust scraper developer, I want unsupported DSL features like XPath and HTTP `@request` to be diagnosed clearly during code generation, so that I receive immediate feedback rather than broken generated code.
27. As a project architect, I want multiple generated parser modules to share a single neighboring `sscgen_runtime.rs` module, so that common runtime types and helpers avoid duplicate symbol collisions in the parent crate.
28. As a CI engineer, I want generated Rust code to be automatically formatted with `rustfmt` when available, so that generated files pass repository style checks (`cargo fmt --check`) without manual intervention.

## Implementation Decisions

- **DOM Representation and Ownership**: The document tree is owned via reference-counted interior mutability (`Rc<RefCell<Document>>`). Nodes are stored and manipulated using stable arena identifiers (`NodeId`), avoiding self-referential structures and lifetime parameters on parser structs.
- **Lifecycle Contract**: Construction via `new(input: impl Into<String>) -> Result<Self, rt::SscError>` parses the document (or stores raw text) and evaluates `@init` fields sequentially into internal struct properties. `parse(&mut self) -> Result<OutputType, rt::SscError>` executes pre-validation assertions and extracts declared fields.
- **Prototype Snippet**:
  *(Encoding the ownership, handle, and lifecycle decisions established in the prototype)*
  ```rust
  pub struct ItemParser {
      dom: rt::Dom,
      root: dom_query::NodeId,
      cached_box: rt::Nodes,
  }
  impl ItemParser {
      pub fn new(input: impl Into<String>) -> Result<Self, rt::SscError> {
          let document = dom_query::Document::from(input.into());
          let dom = std::rc::Rc::new(std::cell::RefCell::new(document));
          let root = rt::root_id(&dom);
          let mut parser = Self { dom, root, cached_box: Default::default() };
          parser.init()?;
          Ok(parser)
      }
      pub fn parse(&mut self) -> Result<ItemType, rt::SscError> {
          self.pre_validate(self.root_nodes())?;
          Ok(ItemType { ... })
      }
  }
  ```
- **Error Handling**: All fallible operations return `Result<T, rt::SscError>`, carrying contextual structure name, field/init identifier, and descriptive error messages.
- **Fallback Semantics**: Fallback blocks evaluate child pipelines within an immediately-invoked closure returning `Result<T, rt::SscError>`. If the closure errors, the fallback value is returned. `fallback #null` produces `Option<T>` with `None` as the fallback value.
- **DOM Side Effects**: `css-remove` detaches matching elements from the document tree via `remove_from_parent()`. The pipeline passes the input selection forward unchanged. Detached nodes remain valid inside arena memory and can still be traversed by previously initialized precomputed fields.
- **Fragment-First JSON**: `jsonify Schema path="..."` navigates the input JSON using the dot-path and decodes the resulting fragment into `SchemaJson`. Cardinality is strictly determined by whether the schema is declared as `json` (single object) or `(array)json` (vector of objects).
- **Strict JSON Projection**: Models generated from `json` definitions validate types during deserialization and project aliased keys (`from="..."`) into canonical property names. Unmodeled keys are ignored, while missing required keys produce errors.
- **Unicode Semantics**: String length (`len`), indexing (`index`), and slicing (`slice`) operate over UTF-8 characters (`chars()`) rather than byte indices. Slice bounds are normalized and clamp safely without panicking on inverted ranges.
- **Regex Translation & Validation**: Patterns are inspected during code generation; lookaround assertions and backreferences trigger `BuildTimeError`. Replacement templates translate `\1` backreferences to `$1`, escaping literal `$` characters as `$$`.
- **Extension Architecture**: The compiler supports `rust` target blocks in `extension` declarations. Target imports are added to parser modules, and helper functions are accumulated into the shared runtime module.
- **Runtime Layout**: A single standalone file `sscgen_runtime.rs` is emitted into the output directory alongside generated parser modules. Parsers reference runtime types via `super::sscgen_runtime as rt`.
- **Formatting**: Generated code is formatted using `rustfmt` with the 2021 edition if the `rustfmt` binary is available in `PATH`.

## Testing Decisions

- **What Makes a Good Test**: Tests verify observable external behavior through public interfaces—namely, parsing KDL schemas, generating complete Rust modules, and verifying compilation, formatting, and execution of the resulting Rust code against real HTML/JSON inputs using Cargo. Tests do not assert on transient private generator state or line-by-line visitor strings.
- **Tested Components**:
  - Target specification resolution and CLI subcommand dispatch (`ssc-gen generate rust`).
  - AST type propagation for fragment-first JSON schemas, array cardinality, and optional metadata.
  - Rust visitor emission for all schema shapes (item, list, table, dict, flat, raw).
  - Lifecycle ordering: single evaluation of `@init` during `new`, repeatability of `parse`, and execution of `@check` and `@pre-validate`.
  - DOM mutation and detached node caching contract.
  - Serde deserialization of JSON fragments with dot-path aliases.
  - Cargo integration test suite (`tests/rust/test_rust_codegen.py`) executing `cargo check`, `cargo fmt --check`, and `cargo test` / `cargo run`.
- **Prior Art**: The Go backend test suite (`tests/go/test_go_codegen.py`), which generates Go code from integration schemas into temporary module directories and validates them using `gofmt`, `go vet`, and `go build`.

## Out of Scope

- XPath query operations (`xpath`, `xpath-all`, `xpath-remove`) and XPath predicates.
- REST HTTP client code generation (`(rest)struct`, `@error` mapping, and typed endpoint methods).
- HTML `@request` transport layer (automated `fetch()` methods on HTML structs).
- Non-CSS selector backends or bindings to C-based DOM engines (e.g., `libxml2`).
- Asynchronous runtime integration (async parsing, `tokio`, or futures).

## Further Notes

- Projects consuming generated Rust parsers require the following dependencies in their `Cargo.toml`:
  ```toml
  [dependencies]
  dom_query = "0.28"
  regex = "1"
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  ```
- Target compatibility: Rust 2021 edition and newer (tested against stable toolchain `1.90+`).
