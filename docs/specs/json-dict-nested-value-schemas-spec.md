# Specification: JSON Dict Nested Value Schemas — Inline Blocks in @value Directives and Compiler Hoisting

## Problem Statement

When modeling JSON responses from modern APIs, developers frequently encounter hierarchical structures where dynamic associative dictionaries contain complex nested objects or further nested dictionaries. A prominent example occurs in media aggregators, where localization translations are keyed by dubber/language codes, and each translation entry contains metadata alongside another nested dictionary mapping numeric episode numbers to stream URLs and player options:

```kdl
json AnimeResponse {
    translations (dict)Translation {
        @key str
        @value TranslationValue {
            episodes (dict)EpisodeMap {
                @key int
                @value EpisodeValue {
                    link str
                    screenshots @skip
                }
            }
            is_active bool
            season int
            type str
            viewers int
            watch_seconds int
        }
    }
}
```

Currently, the KDL Schema DSL supports top-level `(dict)json` declarations and inline `(dict)` fields with scalar or pre-declared schema values (`@value str`, `@value (array)str`, `@value ExistingModel`). However, the `@value` directive does not accept an inline block body (`{ ... }`). When a developer declares an inline model directly inside `@value`, the parser fails to hoist the nested schema, and the cross-reference linter raises `error[E300]: json field 'translations' references undefined json definition 'TranslationValue'`.

Developers are forced to manually dismantle natural JSON hierarchies into disjointed top-level schemas (`json EpisodeValue`, `(dict)json EpisodeMap`, `json TranslationValue`), polluting the module namespace and obscuring structural ownership.

Additionally, schema authors who spread long `@request` declarations across multiple lines using backslash continuations (`\`) and intersperse single-line `//` comments encounter unexpected `error[E403]` errors because unescaped newlines after single-line comments terminate KDL node continuations, turning downstream payload strings into invalid standalone fields.

## Solution

Extend the KDL Schema DSL, AST hoisting pipeline, and schema validation to support **Inline JSON Schemas within `@value` Directives** of both top-level `(dict)json` declarations and inline `(dict)` fields:

1. **Explicit Model Names on `@value` Blocks**:
   Allow `@value` directives with child blocks to declare an explicit model name either as a type annotation before the keyword (`(TranslationValue)@value { ... }`) or as a positional argument (`@value TranslationValue { ... }`).
2. **Anonymous Model Synthesis on `@value` Blocks**:
   Allow bare `@value { ... }` blocks where the compiler automatically synthesizes a canonical model name:
   - For an inline dictionary field with an explicit dict name: `{EnclosingDictName}Value` (e.g. `TranslationValue`).
   - For an anonymous inline dictionary field: `{ParentSchemaName}{FieldName.to_pascal_case()}Value` (e.g. `AnimeResponseTranslationsValue`).
   - For a top-level `(dict)json` declaration: `{DictSchemaName}Value` (e.g. `TranslationsValue`).
3. **Array Value Blocks**:
   Allow `@value (array)ItemModel { ... }` and `(array)@value ItemModel { ... }` to express dictionary values that are lists of objects, enforcing a mandatory item model name in accordance with KDL 2.0 grammar.
4. **Recursive Compiler Hoisting**:
   During AST parsing, hoist inline `@value` schema blocks into standalone `JsonDef` AST nodes registered in `Module.body` and ordered topologically before their enclosing schemas. Multi-level nesting (such as a dictionary inside an object inside a dictionary) is hoisted recursively post-order.
5. **Full Modifiers and Nested Structure Support**:
   The fields within an inline `@value` block support all standard JSON field modifiers (`from="..."`, `@omitempty`, `?`, `@skip`), nested objects (`field { ... }`), and further nested dictionaries (`(dict)field { ... }`).
6. **Target-Aware Code Generation**:
   Leverage hoisted `JsonDef` references so that Python (`Dict[K, V]`), Go (`map[K]V`), Rust (`HashMap<K, V>`), and JavaScript (`Record<K, V>`) generate idiomatic, strongly-typed models without altering backend visitor architectures.
7. **Protective Diagnostic for Broken Request Continuations**:
   When a struct contains a field whose name begins with HTTP request signatures (`"curl "`, `"http://"`, `"https://"`, `"GET "`, `"POST "`), emit an informational lint hint pointing out that KDL terminates line continuations at single-line `//` comments, replacing misleading symbol errors with clear guidance.

## User Stories

1. As a scraper developer, I want to declare `@value ModelName { ... }` inside an inline `(dict)` field, so that I can define dictionary value structures directly where they occur.
2. As a scraper developer, I want to declare `(ModelName)@value { ... }` with a leading type annotation, so that my schema conforms naturally to KDL 2.0 type annotation placement.
3. As a scraper developer, I want to declare an anonymous `@value { ... }` block inside an inline dictionary, so that I do not have to invent artificial type names for one-off dictionary payloads.
4. As a scraper developer, I want to declare `@value (array)ItemModel { ... }` inside a dictionary, so that dictionary values containing lists of structured objects can be defined inline.
5. As a scraper developer, I want to declare `(array)@value ItemModel { ... }` with a leading `(array)` type annotation on `@value`, so that list-valued dictionaries adhere to KDL keyword styling.
6. As a scraper developer, I want to declare an inline `@value` block inside a top-level `(dict)json Name { ... }` declaration, so that standalone dictionary schemas can define their value objects inline.
7. As a scraper developer, I want to nest an inline `(dict)` field inside an inline `@value` block, so that multi-level dictionary-of-dictionary structures can be expressed in a single coherent hierarchy.
8. As a scraper developer, I want fields inside an inline `@value` block to support key aliases (`from="..."`), so that wire JSON property names are cleanly remapped to idiomatic field names.
9. As a scraper developer, I want fields inside an inline `@value` block to support `@omitempty`, so that optional fields in dictionary values can be omitted when absent.
10. As a scraper developer, I want fields inside an inline `@value` block to support nullable types (`field_name str?`), so that `null` JSON values in dictionary objects are parsed safely.
11. As a scraper developer, I want fields inside an inline `@value` block to support `@skip`, so that ignored wire properties are discarded during projection.
12. As a schema author, I want `ssc-gen check` to emit an `E001` error if an inline `@value` block is empty (`{}`), so that incomplete schema definitions are caught early.
13. As a schema author, I want `ssc-gen check` to emit an `E002` error if `@skip` is attached to an `@value` directive with an inline block, so that contradictory schemas are rejected.
14. As a schema author, I want `ssc-gen check` to emit an `E001` error if `@value` with an inline block specifies `(array)` but omits the item model name, so that KDL type rules are enforced.
15. As a schema author, I want `ssc-gen check` to emit an `E001` error if an explicit model name on an inline `@value` block collides with an existing JSON schema in the module.
16. As a schema author, I want `ssc-gen check` to emit a helpful diagnostic if a struct contains an unattached field named like an HTTP request (`curl ...`), so that I immediately understand when comments interrupted a `\` line continuation.
17. As a Python developer, I want inline `@value` blocks to generate typed `TypedDict` models ordered before parent schemas, so that Python type hints resolve without forward reference errors.
18. As a Python developer, I want Python runtime projection (`ssc_json_project`) to project every dictionary entry against the hoisted value descriptor, so that nested aliasing and allowlist filtering work recursively across dictionary entries.
19. As a Go developer, I want inline `@value` blocks to generate separate `struct` definitions, so that `map[KeyType]ValueModelJson` unmarshals nested JSON objects cleanly.
20. As a Rust developer, I want inline `@value` blocks to generate top-level `pub struct` models with Serde derives, so that `std::collections::HashMap<KeyType, ValueModelJson>` deserializes nested dictionary payloads idiomatic in Rust.
21. As a JavaScript developer, I want inline `@value` blocks to generate independent `@typedef {Object}` JSDoc declarations, so that IDE autocomplete and TypeScript checking function correctly for dictionary elements.
22. As a REST client developer, I want REST request methods returning dictionaries of nested objects to declare inline `@value` blocks in their response schemas, so that API clients have end-to-end typed responses without module clutter.

## Implementation Decisions

### AST Representation & Hoisting Architecture
- Extend JSON dictionary AST resolution so that `@value` directives with child blocks are hoisted into independent `JsonDef` AST nodes.
- Hoisted `JsonDef` nodes are inserted into `Module.body` immediately preceding the enclosing parent schema, ensuring topological post-order dependency ordering.
- The dictionary's `value_type_info` receives:
  - `base = VariableType.JSON`
  - `ref = <hoisted_schema_name>`
  - `is_array = True` if declared with `(array)`
  - `is_optional = True` if declared with `?`
- When `@value` contains further nested dictionaries or nested object blocks, hoisting proceeds recursively so that innermost leaf schemas appear earliest in `Module.body`.

### Syntax Normalization & Name Synthesis
- Accept model names from either node type annotation (`(Model)@value`) or argument position (`@value Model`).
- Accept array annotations from either node type annotation (`(array)@value Model`) or argument type annotation (`@value (array)Model`).
- For anonymous `@value { ... }` blocks, synthesize canonical names following the pattern:
  - Inside an inline dict with explicit model name `Translation`: `TranslationValue`
  - Inside an anonymous inline dict field `translations` under parent `AnimeResponse`: `AnimeResponseTranslationsValue`
  - Inside a top-level `(dict)json Translations`: `TranslationsValue`
- All target code generators append the canonical `Json` suffix to emitted model names (e.g. `TranslationValueJson`).

### Linter & Validation Rules
- Update dictionary schema linting to permit child nodes on `@value` directives when they declare valid JSON fields.
- Flag empty inline blocks in `@value` with error `E001` ("empty inline json block in '@value'").
- Flag `@skip` on `@value` with child blocks with error `E002` ("cannot use '@skip' on inline json block in '@value'").
- Flag anonymous array blocks on `@value` with error `E001` ("inline array block in '@value' requires an item model name").
- Flag explicit model names that collide with declared or previously hoisted schemas with error `E001` ("duplicate json definition").
- Run recursive field validation on `@value` child nodes via the standard JSON field linter to enforce field modifier validity and symbol naming.
- Add a specialized lint check for regular fields whose names match HTTP request signatures (`"curl "`, `"http://"`, `"https://"`, `"GET "`, `"POST "`), emitting a hint regarding KDL `\` line continuation behavior and `//` comments.

### Target Generators & Runtime Projection
- Target visitors (Python, Go, Rust, JavaScript) require no changes to their dictionary rendering logic, as hoisted schemas are standard `JsonDef` nodes referenced via `TypeInfo.ref`.
- Python runtime projection descriptors (`_python_json_descriptors`) already support `{"__dict__": True, "__value__": <nested_descriptor>}`, which seamlessly handles hoisted value models.

## Testing Decisions

### What Makes a Good Test
- Tests must verify external compiler and runtime behavior: schema parsing, diagnostic emission, code generation across all four supported backends, and executing generated projection logic against actual nested dictionary JSON payloads.
- Tests should assert that hoisted models appear in the generated output in correct dependency order and that invalid schemas are rejected with accurate error codes.

### Testing Seams
- **Schema & Linter Seam**: `parse_module(schema_text)` in unit tests verifying AST nodes, hoisted `JsonDef` ordering, synthesized model names, and diagnostic error codes (`E001`, `E002`, `E300`).
- **End-to-End Codegen & Execution Seam**:
  - Python: `tests/test_json_projection.py` and `tests/integration/test_codegen_run.py` verifying `TypedDict` generation and executing `ssc_json_project` against multi-level dictionary JSON data.
  - Go: `tests/go/test_go_codegen.py` compiling generated code with `go build` and unmarshaling nested dictionary data.
  - Rust: `tests/rust/test_rust_codegen.py` compiling generated code with `cargo check` and deserializing nested dictionary data.
  - JavaScript: `tests/js/test_js_codegen.py` validating generated JSDoc typedefs and property annotations.

### Prior Art
- `docs/specs/inline-json-schemas-spec.md`: Nested field blocks and compiler hoisting.
- `docs/specs/json-dict-schemas-spec.md`: Top-level `(dict)json` and inline `(dict)` specifications.
- `tests/test_json_projection.py`: Test suite for JSON key aliasing, array projection, and dictionary schemas.

## Out of Scope
- Dynamic dictionary keys other than scalar primitives (`str`, `int`, `float`, `bool`).
- Runtime type conversion or coercion of dictionary keys during Python/JavaScript projection.
- Inline schemas inside `@key` directives (keys must remain scalar types).
- Changing external KDL parser (`kdlquery`) behavior regarding line continuation across comments.

## Further Notes
- This feature completes the design of the JSON schema subsystem, providing total symmetry between scalar fields, array fields, sub-objects, and dictionary values.
