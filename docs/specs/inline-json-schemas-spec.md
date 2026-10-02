# Specification: Inline JSON Schemas — Nested Field Blocks, Hoisting, and Name Synthesis

## Problem Statement

When modeling JSON responses from web APIs and scrapers, developers frequently encounter deeply nested payload hierarchies. In complex domains (such as media aggregators, e-commerce catalogs, and social graphs), a single endpoint response often contains multiple layers of sub-objects and arrays of objects:

```kdl
// ANIME RESPONSE (Current Flat Style)
json Links {
    id int
    source_id int
    target_id int
    relation str
}

json Node {
    id int
    name str
    poster_url str
    score float
}

json Franchise {
    id str
    links (array)Links
    nodes (array)Node
}

json MaterialData {
    anime_title str
    year int
}

json AnimeResponse {
    id str
    franchise Franchise
    material_data MaterialData
}
```

In the current KDL Schema DSL, all `json` declarations must exist as flat, top-level definitions in the module. This design has severe drawbacks:

1. **Lost Ownership and Hierarchy Context**: In a schema file with dozens of models, developers cannot visually determine which sub-model belongs to which parent without conducting full-text searches. It is impossible to see at a glance whether `Node` or `Links` are response roots or deep child structures.
2. **Namespace Pollution**: Ephemeral models that exist solely to type a single sub-field within one parent schema are exposed as global symbols in the module namespace.
3. **Name Collisions**: Common sub-model names (e.g. `Node`, `Item`, `Meta`, `Data`, `Links`, `Author`) collision risk is high when multiple distinct responses or endpoints define their own variant of these structures in the same schema file.

## Solution

Extend the KDL Schema DSL and the code generation pipeline to support **Inline JSON Schemas** directly within parent `json` declarations:

1. **Anonymous Single Object Blocks (`field_name { ... }`)**:
   Defines an inline sub-object where the model name is automatically synthesized by the compiler:
   `{ParentTypeName}{FieldName.to_pascal_case()}` (e.g. `AnimeResponse` + `material_data` → `AnimeResponseMaterialDataJson`).
2. **Explicitly Named Single Object Blocks (`field_name ModelName { ... }`)**:
   Defines an inline sub-object with an explicit model name for generated target code (e.g. `franchise Franchise { ... }` → `FranchiseJson`).
3. **Explicitly Named Array Object Blocks (`field_name (array)ItemModelName { ... }`)**:
   Defines an inline list of objects with an explicit item model name (e.g. `nodes (array)Node { ... }` → `NodeJson`). Because KDL 2.0 grammar binds type annotations like `(array)` to the subsequent value token, the item model name is mandatory for arrays.
4. **Compiler Hoisting Architecture**:
   During AST parsing, inline schema blocks are lifted (*hoisted*) into first-class `JsonDef` AST nodes registered in `Module.body` and ordered topologically (dependencies before consumers). The enclosing field is represented as a standard `JsonDefField` referencing the hoisted schema by name (`ret_type_info.base = VariableType.JSON`, `ref = ...`). Consequently, backend code generators (Python, Go, Rust, JavaScript) require zero core architectural changes to render the generated models.
5. **Field Modifiers and Key Aliasing**:
   Inline fields support full modifier symmetry with scalar fields: `from="..."` (JSON key alias), `@omitempty` (optional field), and `?` (nullable type). For developer ergonomics, `path="..."` is accepted on inline fields as a synonym for `from="..."`, with a diagnostic warning recommending `from="..."`.

```kdl
json AnimeResponse {
    id str
    anime_poster str

    // Explicitly named inline object
    franchise Franchise {
        id str
        shikimori_id str

        // Explicitly named inline array of objects
        links (array)Links {
            id int
            relation str
        }

        nodes (array)Node {
            id int
            name str
            score float
        }
    }

    // Anonymous inline object (synthesizes AnimeResponseMaterialDataJson)
    material_data {
        anime_title str
        year int
        next_episode_at str?
    }

    // Inline object with key alias and nullable modifier
    self_hosted SelfHosted? from="self_hosted_data" @omitempty {
        available bool
        episodes (array)str
        translations (dict) {
            @key str
            @value (array)str
        }
    }
}
```

## User Stories

1. As a scraper developer, I want to declare inline sub-object blocks directly inside a `json` schema, so that the schema structure visually mirrors the nested shape of the JSON payload.
2. As a scraper developer, I want to declare anonymous inline fields like `material_data { ... }`, so that I do not have to invent artificial type names for single-use sub-objects.
3. As a scraper developer, I want to declare explicitly named inline fields like `franchise Franchise { ... }`, so that the generated target models have clean, concise names like `FranchiseJson`.
4. As a scraper developer, I want to declare inline array blocks with explicit item types like `nodes (array)Node { ... }`, so that lists of nested objects can be defined inline while adhering to KDL 2.0 syntax.
5. As a scraper developer, I want inline fields to support `from="..."`, `@omitempty`, and nullable (`?`), so that wire key aliases and optionality work identically to scalar fields.
6. As a scraper developer, I want `path="..."` on an inline field to be treated as a synonym for `from="..."`, so that intuitive usage does not cause unexpected compile errors.
7. As a schema author, I want `ssc-gen check` to emit a lint error if an explicit inline schema name collides with another schema name in the module, so that naming collisions are caught at build time.
8. As a schema author, I want `ssc-gen check` to emit a lint error if an inline block is empty (`{}`), so that incomplete schemas are detected immediately.
9. As a schema author, I want `ssc-gen check` to emit a lint error if `@skip` is attached to a field with an inline block body, so that contradictory schema declarations are prevented.
10. As a Python developer, I want nested inline schemas to generate separate `TypedDict` classes ordered before their parents, so that Python type annotations resolve without circular or unresolved references.
11. As a Python developer, I want Python runtime projection (`ssc_json_project`) to recursively remap aliases and validate allowlists for inline schemas, so that nested data is cleanly filtered.
12. As a Go developer, I want nested inline schemas to generate independent `type ModelJson struct` definitions with standard `json:"..."` struct tags, so that `encoding/json` and `gjson` unmarshal nested payloads properly.
13. As a Rust developer, I want nested inline schemas to generate top-level `pub struct ModelJson` with `#[derive(Deserialize, Serialize)]`, so that Serde can deserialize nested payloads idiomatic in Rust.
14. As a JavaScript developer, I want nested inline schemas to generate separate `@typedef {Object} ModelJson` JSDoc annotations, so that IDE autocompletion and TypeScript type checking work seamlessly.
15. As a REST client developer, I want endpoints returning nested JSON payloads to use inline schemas in their response definitions, so that response typing does not clutter the root schema namespace.
16. As an HTML scraper developer, I want `jsonify` operations to target schemas with inline nested blocks, so that embedded JSON blobs with nested structures can be parsed directly.

## Implementation Decisions

### AST Representation & Hoisting
- Inline schema definitions are parsed into standard `JsonDef` AST nodes.
- Hoisting mechanism: When `parse_json_fields` encounters a child node with a non-empty block body, it creates a new `JsonDef` instance for the sub-schema, parses its fields recursively, and registers it in `ctx.json_defs` and `Module.body`.
- Hoisted `JsonDef` nodes are inserted into `Module.body` immediately preceding the enclosing parent `JsonDef` (post-order topological dependency order).
- The parent field is created as a `JsonDefField` whose `ret_type_info` has:
  - `base = VariableType.JSON`
  - `ref = <hoisted_schema_name>`
  - `is_array = True` if declared with `(array)`
  - `is_optional = True` if declared with `?`
  - `omitempty = True` if declared with `@omitempty`
  - `alias = from_prop` (or `path_prop` if `path` was specified)
- Because hoisted schemas are standard `JsonDef` nodes, target code visitors (`PythonVisitor`, `GoVisitor`, `RustVisitor`, `JsVisitor`) require zero modifications to their core type generation logic.

### Name Synthesis Algorithm
- If an explicit name is supplied:
  - For single object: `field_name ModelName { ... }` → schema name is `ModelName`.
  - For array of objects: `field_name (array)ItemModelName { ... }` → schema name is `ItemModelName`.
- If no explicit name is supplied:
  - Single object: `field_name { ... }` → schema name is `{ParentTypeName}{FieldName.to_pascal_case()}`.
  - Multi-level nesting: Chain continues from the immediate parent schema's canonical name. For example, parent `AnimeResponse` + field `material_data` → `AnimeResponseMaterialData`. If `material_data` contains an anonymous `geo_info` block → `AnimeResponseMaterialDataGeoInfo`.
  - If an ancestor had an explicit name (e.g. `franchise Franchise { ... }`), child synthesis anchors to that explicit name (e.g. field `meta { ... }` inside `Franchise` becomes `FranchiseMeta`).
- Target code generators append `Json` suffix as usual (e.g. `AnimeResponseMaterialDataJson`).

### Schema Parsing (`ssc_codegen/core/struct_parser.py`)
- In `parse_json_fields`:
  - Inspect `node.children`. If `node.children` is non-empty and the field is not a `(dict)` block:
    - Check if type argument is provided. If `(array)` annotation is present, extract item type name.
    - If no type argument is provided, synthesize the schema name using the parent's `name` and `node.name`.
    - Recursively invoke `parse_json_fields` on `node.children` to populate the new `JsonDef`.
    - Register the new `JsonDef` in `ParseContext.json_defs` and insert it into `module.body` ahead of the parent.
    - Resolve `alias` from `from` property, falling back to `path` property if `from` is absent.

### Linter & Validation (`ssc_codegen/core/linter.py`)
- **Duplicate Names (`E001`)**: Validate that explicit inline schema names are unique within the module and do not collide with other `json` declarations.
- **Empty Blocks (`E001`)**: Emit an error if `node.children` is present but contains no field declarations or directives.
- **Forbidden `@skip` on Blocks (`E002`)**: Emit an error if `@skip` modifier is used on a field that declares a non-empty child block.
- **Path Synonym Hint (`W041`)**: When `path="..."` is used on an inline field, emit an informational warning/hint: `"use 'from' instead of 'path' to specify JSON key alias on fields"`.
- **Invalid Array Syntax**: Emit an error if `(array)` is attached to a field with a block but missing an item type name (e.g. `items (array) { ... }`).

### Code Generation Targets (`ssc_codegen/targets/`)
- **Python (`targets/python/visitor.py`)**:
  - Automatically generates `class SynthesizedJson(TypedDict)` for each hoisted schema.
  - Runtime projection descriptor generator (`_python_json_descriptors`) resolves nested schema references recursively without changes.
- **Go (`targets/golang/visitor.py`)**:
  - Emits `type SynthesizedJson struct { ... }` with proper `json:"alias"` tags.
- **Rust (`targets/rust/visitor.py`)**:
  - Emits `pub struct SynthesizedJson { ... }` with `#[serde(rename = "alias")]`.
- **JavaScript (`targets/javascript/visitor.py`)**:
  - Emits `@typedef {Object} SynthesizedJson` JSDoc blocks and references them in the parent type.

## Testing Decisions

### What Makes a Good Test
- Tests should verify the full workflow end-to-end: parsing schemas with deeply nested anonymous and named inline blocks, linting validation and error reporting, code generation in all 4 targets, and running generated code against real nested JSON payloads.

### Modules to be Tested
- `tests/test_parser.py`: Unit tests for parsing anonymous inline fields, explicitly named inline fields, inline array blocks, name synthesis, empty block rejection, and `@skip` rejection.
- `tests/integration/test_codegen_run.py`: End-to-end Python parser generation and execution validating that nested JSON objects and arrays are correctly parsed, projected, and remapped.
- `tests/go/test_go_codegen.py`: Go build and unmarshal execution verifying nested structs and field tags.
- `tests/rust/test_rust_codegen.py`: Rust compilation verifying nested Serde structs.
- `tests/js/test_js_codegen.py`: JavaScript execution verifying JSDoc typedefs and nested object access.

### Prior Art
- `docs/specs/json-dict-schemas-spec.md`: Inline dictionary fields (`field (dict) { ... }`).
- `tests/integration/schemas/32_json_aliased_remapping.kdl`: JSON key alias remapping and projection.
- `tests/integration/schemas/22_rest_response_path.kdl`: REST response schemas with paths.

## Out of Scope

- Anonymous inline arrays (`items (array) { ... }`) due to KDL 2.0 grammar constraints.
- Referencing an inline schema from outside its parent declaration (inline schemas have local scope).
- Runtime type coercion or mutation of nested values during Python/JS projection.
- Anonymous inline dictionaries without `@value` directives (already governed by `(dict)json` spec).

## Further Notes

- Architecture decision recorded in ADR-0004 (`docs/adr/0004-inline-json-schemas.md`).
- Domain terms updated in `CONTEXT.md` (`Inline JSON schema`, `Synthesized schema name`, `Hoisted JSON schema`).
