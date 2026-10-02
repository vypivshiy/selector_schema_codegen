# Specification: JSON Dict Schemas — Top-Level (dict)json Declarations and Inline (dict) Field Blocks

## Problem Statement

Developers using the KDL Schema DSL to model JSON payloads from web scraping and REST APIs frequently encounter JSON objects with dynamic, arbitrary, or numeric keys and homogeneous values. Examples include episode-to-translations mappings:

```json
{
  "translations": {
    "1": ["jap", "Мега-Аниме", "СВ-Дубль"],
    "10": ["jap", "Мега-Аниме", "СВ-Дубль"],
    "11": ["jap", "Мега-Аниме", "СВ-Дубль"]
  }
}
```

as well as resource dictionaries keyed by IDs, localization lookup maps, and dynamic property tables.

Currently, the DSL provides `json Object { ... }` for objects with fixed known keys and `(array)json Item { ... }` for lists, but lacks syntax to express associative maps with dynamic keys and a stable value schema. Furthermore, KDL 2.0 grammar forbids chained annotations like `(dict)(array)str` or brackets in identifiers, preventing intuitive one-line compositions. Without native dictionary schema support, developers cannot generate strongly typed parser models in Python (`Dict[K, V]`), Go (`map[K]V`), Rust (`HashMap<K, V>`), or JavaScript (`Record<K, V>`), and schema validation (`ssc-gen check`) cannot verify map value types or enforce response contracts.

## Solution

Extend the KDL Schema DSL and the code generation pipeline to support JSON dictionary schemas via two complementary forms:

1. **Top-Level Named Schemas (`(dict)json Name { ... }`)**: Defines a reusable dictionary model that can serve as the root response schema for REST endpoints or `jsonify` operations, or as the type of fields in other schemas.
2. **Inline Field Blocks (`field (dict) { ... }`)**: Defines an anonymous dictionary schema directly inside a parent `json` declaration.

Inside a dictionary schema block, structural directives mirror the established `(dict)struct` convention:
- `@value <Type>`: Mandatory directive defining the type of dictionary values (scalar, array of scalars, or reference to another JSON schema).
- `@key <ScalarType>`: Optional directive defining the logical key type (`str`, `int`, `float`, `bool`), defaulting to `str`.

The schema compiler validates dictionary contracts at build time, and code generators emit idiomatic dictionary types across all four supported targets. In accordance with the project's projection contract (`CONTEXT.md`), runtime projection preserves wire keys without type casting, while static targets (Go, Rust) perform native unmarshaling.

## User Stories

1. As a scraper developer, I want to declare a top-level `(dict)json Translations` schema in KDL, so that I can model JSON responses that consist of dynamic key-value dictionaries.
2. As a scraper developer, I want to specify `@value (array)str` inside a `(dict)json` block, so that all values in the dictionary are typed as lists of strings.
3. As a scraper developer, I want to specify `@key int` inside a `(dict)json` block, so that numeric wire keys are typed as integers in generated target language models.
4. As a scraper developer, I want `@key` to default to `str` when omitted, so that I do not need to write boilerplate `@key str` for standard string-keyed dictionaries.
5. As a scraper developer, I want to declare an inline `translations (dict) { ... }` block inside a `json` schema, so that I can define dictionary fields without creating a separate top-level schema.
6. As a scraper developer, I want `(dict)json` schemas to accept an optional `path="..."` property, so that I can extract a dictionary sub-tree from a nested JSON payload.
7. As a scraper developer, I want fields referencing `(dict)json` schemas to support the `@omitempty` modifier, so that optional dictionary fields can be omitted when absent from the wire payload.
8. As a scraper developer, I want fields referencing `(dict)json` schemas to support nullable syntax (`Schema?`), so that `null` dictionary values in the wire payload are cleanly handled.
9. As a Python developer, I want a top-level `(dict)json Translations` to generate `TranslationsJson = Dict[KeyType, ValueType]`, so that mypy and pyright provide accurate type checking.
10. As a Python developer, I want inline dict fields to generate `field_name: Dict[KeyType, ValueType]` in parent `TypedDict` models, so that dictionary properties are strongly typed.
11. As a Python developer, I want Python runtime projection (`ssc_json_project`) to verify that the incoming payload is a dictionary, so that invalid non-dictionary payloads raise a schema error.
12. As a Python developer, I want Python runtime projection to recursively project values when `@value` references a nested `json` schema with field aliases, so that nested models are correctly remapped.
13. As a Go developer, I want a top-level `(dict)json Translations` to generate `type TranslationsJson = map[KeyType]ValueType`, so that Go code can consume typed maps.
14. As a Go developer, I want parent Go structs with dict fields to include `map[KeyType]ValueType` with standard `json:"name"` struct tags, so that standard `encoding/json` or `gjson` decodes them cleanly.
15. As a Rust developer, I want a top-level `(dict)json Translations` to generate `pub type TranslationsJson = std::collections::HashMap<KeyType, ValueType>;`, so that Rust applications have idiomatic map types.
16. As a Rust developer, I want parent Rust structs to include `pub field_name: std::collections::HashMap<KeyType, ValueType>`, deriving `serde::Deserialize` and `serde::Serialize`.
17. As a JavaScript developer, I want generated JSDoc comments to document dict models with `@typedef {Record<KeyType, ValueType>} TranslationsJson`, so that TypeScript and IDEs provide autocompletion.
18. As a schema author, I want `ssc-gen check` to emit a lint error if a `(dict)json` block is missing the mandatory `@value` directive, so that incomplete schemas are caught before code generation.
19. As a schema author, I want `ssc-gen check` to emit a lint error if an unsupported key type (such as a nested object or array) is specified for `@key`, so that key types remain valid JSON hashable keys.
20. As a schema author, I want `ssc-gen check` to emit a lint error if regular field names (e.g. `foo str`) are placed inside a `(dict)json` block, so that structural meta-directives are not confused with fixed field definitions.
21. As a REST client developer, I want to use a `(dict)json` schema as the `response=...` target of an `@request` directive, so that endpoints returning dynamic dictionaries are parsed into typed results.
22. As an HTML scraper developer, I want to pass a `(dict)json` schema to a `jsonify` pipeline operation, so that embedded JSON dictionary strings in HTML attributes or script tags can be parsed and typed.

## Implementation Decisions

### AST Representation
- Extend the JSON schema AST node representation to distinguish between object schemas, array schemas, and dictionary schemas.
- Introduce explicit AST fields or node attributes representing `@key` and `@value` type specifications, including base variable type, array modifier, optionality, and schema reference.
- Support both standalone top-level dictionary definitions and inline dictionary field representations within enclosing parent schemas.

### Schema Parsing (`ssc_codegen/core`)
- Update `handle_json` to recognize the `(dict)` type annotation on top-level `json` nodes (e.g. `(dict)json Name`).
- Extend `parse_json_def_body` and field parsing routines to inspect children of `(dict)json` declarations:
  - Parse `@key` directive to extract scalar key type (`str`, `int`, `float`, `bool`), defaulting to `str` if omitted.
  - Parse `@value` directive to extract value type, supporting scalar primitives, `(array)` modifiers, and references to other `json` schemas.
- Update `parse_json_fields` to recognize inline `field_name (dict) { ... }` child blocks, extracting key and value specifications for anonymous dictionary fields.

### Linter & Validation (`ssc_codegen/core/linter.py`)
- In `(dict)json` and inline `(dict)` blocks:
  - Enforce that only `@key` and `@value` directives are permitted as child nodes. Flag any other node name as a structural error.
  - Require `@value` to be present. Flag missing `@value` as an error.
  - Restrict `@key` to scalar types (`str`, `int`, `float`, `bool`). Flag array or object key types as an error.
  - Prevent duplicate `@key` or `@value` declarations within the same block.

### Code Generation Targets (`ssc_codegen/targets/`)
- **Python (`targets/python/visitor.py`)**:
  - Emit `NameJson = Dict[KeyType, ValueType]` for top-level dictionary schemas.
  - Resolve field types as `Dict[KeyType, ValueType]` for dict fields in `TypedDict`.
  - Register typing imports (`Dict`) in `ModuleBuilder`.
  - Update `_python_json_descriptors` and `ssc_json_project` helper to recognize dict descriptors, verifying input is a dict and mapping nested descriptors over dictionary values.
- **Go (`targets/golang/visitor.py`)**:
  - Emit `type NameJson = map[KeyType]ValueType` for top-level dictionary schemas.
  - Render struct fields as `FieldName map[KeyType]ValueType \`json:"wire_name"\``.
  - Map `@key` types to `string`, `int64`, `float64`, `bool`.
- **Rust (`targets/rust/visitor.py`)**:
  - Emit `pub type NameJson = std::collections::HashMap<KeyType, ValueType>;`.
  - Render struct fields as `pub field_name: std::collections::HashMap<KeyType, ValueType>`.
  - Map `@key` types to `String`, `i64`, `f64`, `bool`.
- **JavaScript (`targets/javascript/visitor.py`)**:
  - Emit `/** @typedef {Record<KeyType, ValueType>} NameJson */`.
  - Render JSDoc property annotations as `@property {Record<KeyType, ValueType>} field_name`.

## Testing Decisions

### What Makes a Good Test
- Tests should verify external behavior end-to-end: parse valid KDL schemas, run schema validation (`ssc-gen check`), generate target code, and execute the generated code on real JSON payloads.
- Tests must not assert on internal AST traversal states or intermediate helper names.

### Modules to be Tested
- `tests/test_parser.py`: Schema parsing and linter rules (valid `@key`/`@value`, missing `@value`, invalid key types, duplicate directives).
- `tests/integration/test_codegen_run.py`: End-to-end Python generation and execution with dictionary payloads (both top-level and inline).
- `tests/js/test_js_codegen.py`: End-to-end JavaScript generation and execution via Node.js + jsdom.
- `tests/go/test_go_codegen.py`: Go compilation and execution verifying `map[K]V` unmarshaling.
- `tests/rust/test_rust_codegen.py`: Rust compilation verifying `HashMap<K, V>` serde deserialization.

### Prior Art
- `tests/integration/schemas/06_dict.kdl`: Existing tests for `(dict)struct` key-value extraction in HTML.
- `tests/integration/schemas/32_json_aliased_remapping.kdl`: Existing tests for JSON schema projection and key remapping.
- `tests/integration/test_rest_codegen.py`: Existing tests for REST endpoint JSON response schemas.

## Out of Scope

- Runtime key casting/coercion in Python and JavaScript (preserving wire keys without runtime mutation).
- Non-scalar dictionary key types (e.g. nested objects or array keys in JSON).
- Arbitrary named fields alongside `@key` and `@value` in dictionary schema declarations.
- Custom key remapping or key alias transformations inside dynamic dictionaries.

## Further Notes

- Decision recorded in ADR-0003 (`docs/adr/0003-json-dict-schemas.md`).
- Domain terms updated in `CONTEXT.md` (`JSON dict schema`, `JSON dict key type`).
