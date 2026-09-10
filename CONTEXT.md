# ssc_codegen Domain Context

Canonical vocabulary for KDL schemas, source boundaries, and validation levels.

## Schema Types

**HTML schema**:
A KDL schema using regular, item, list, table, dict, or flat structs to extract values from an HTML DOM.
_Avoid_: REST schema, raw schema

**Raw schema**:
A KDL `(raw)struct` or `(raw)fn` that extracts values from plain text without an HTML parser.
_Avoid_: HTML schema

**REST schema**:
A KDL `(rest)struct` that describes JSON HTTP requests, response schemas, and typed error variants.
_Avoid_: HTML client, OpenAPI converter

**Pipeline**:
An ordered sequence of KDL operations that changes an input value into a field result.
_Avoid_: transform (unless referring to a confirmed project operation)

## API Terms

**Request**:
An `@request` declaration describing how a source is obtained, including method, URL, headers, body, and placeholders.
_Avoid_: endpoint schema

**Response schema**:
A `json` declaration describing JSON data returned by a REST request.
_Avoid_: response parser, OpenAPI schema

**JSON field name**:
The canonical field name declared before the type in a `json` field and used
by generated code and its result annotations.
_Avoid_: source key, wire key

**JSON key alias**:
The source JSON key specified via `from="..."` property (or legacy positional string argument)
when it differs from the canonical field name. For `context str from="@context"`,
`context` is the canonical field name and `@context` is the JSON key alias.
_Avoid_: output alias, field rename

**Remapped JSON result**:
A plain mapping containing only declared canonical JSON field names, produced
from source JSON keys by applying JSON key aliases; absent source keys are
omitted and values are not type-validated or cast.
_Avoid_: validated model, deserialized object

## Validation And Access

**Schema validation**:
Successful `ssc-gen check` validation of KDL syntax, structure, symbols, and pipeline types; it does not prove source access or runtime correctness.
_Avoid_: integration test

**Code generation validation**:
Successful `ssc-gen generate` for a user-selected target and backend; it checks code generation but does not prove runtime correctness against a source.
_Avoid_: source validation

**Authenticated source**:
A source requiring cookies, credentials, tokens, or a session established by prior actions.
_Avoid_: public source

**Request preparation**:
Actions required before the target request, such as login, token exchange, cookie setup, special headers, or pagination state.
_Avoid_: request body

## Codegen Architecture

**AST Node**:
A strongly-typed dataclass (`ssc_codegen.ast.Node`) representing a syntax element or synthesized artifact in the intermediate representation tree.
_Avoid_: AST token, grammar symbol

**WalkContext**:
 The traversal-only context carrying variable naming counters (`ctx.prv`, `ctx.nxt`) and indentation depth (`ctx.indent`) across AST visits. Target/build customizations belong to a separate options or extension context.
 _Avoid_: variable scope, traversal state dict, backend options bag

**AST no-op node**:
 A registered technical or insertion-point node whose handler intentionally emits no target code. This is different from an unknown AST node, which is a generation error.
 _Avoid_: silently ignored node

**Legacy array flag**:
 The removed `Node.is_array` representation that was replaced by `TypeInfo.is_array` as the canonical array modifier.
 _Avoid_: second type source of truth

**BaseWalker**:
 The language-agnostic AST traversal engine that dispatches nodes to `visit_*` handlers across three traversal modes: Container, Pipeline, and Predicate.
 _Avoid_: tree visitor, code emitter base

**Visitor handler**:
 An explicit target-specific `visit_*` dispatch endpoint. Its visibility is part of the backend contract and should not be hidden behind components that only forward the same methods.
 _Avoid_: incidental delegation method

**ModuleBuilder**:
A pure data accumulator that registers imports, standard helper functions, and user extension runtime definitions idempotently without rendering target syntax.
_Avoid_: signal pool, import emitter

**DomSpelling**:
An abstract interface defining HTML library-specific DOM query expressions and predicate conditions for a target language.
_Avoid_: DOM adapter, HTML dialect wrapper

**HttpLibStrategy**:
A strategy defining client library-specific transport code generation, client types, and runtime exception handling for REST requests.
_Avoid_: transport driver, HTTP handler

**Two-pass codegen**:
A code generation approach where pass 1 traverses the AST to accumulate required imports and standard helper definitions in `ModuleBuilder`, and pass 2 emits the complete target source file.
_Avoid_: single-pass emission, forward-declaring generator

## Documentation Standards

**API Reference**:
The generated technical reference derived from code signatures, type annotations, and docstrings via `mkdocstrings` (Griffe AST parser) and CLI command introspection via `mkdocs-click`.
_Avoid_: user guide, tutorial

**Google-style docstring**:
The mandatory docstring format (Args, Returns, Raises, Yields) for all public and architectural functions, classes, and methods across the codebase.
_Avoid_: Sphinx reST docstring, NumPy docstring

**Architectural Reference Scope**:
The full coverage boundary of the API reference spanning the public facade, AST intermediate representation, core reader/linter passes, traversal engine, and backend target converters.
_Avoid_: public-only facade
