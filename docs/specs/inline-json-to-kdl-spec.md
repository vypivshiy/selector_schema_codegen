# Specification: Inline JSON-to-KDL Schema Generation

## Problem Statement

When creating scraping schemas or REST API response schemas from sample JSON payloads, developers use `json_to_kdl` (and the `ssc-gen json-to-kdl` CLI command) to automatically bootstrap `.kdl` schema files. Previously, the generator flattened nested JSON hierarchies into multiple standalone top-level `json` declarations written in reverse topological order, inventing global PascalCase identifiers (`JsonResponseUser`, `JsonResponseUserProfile`, etc.) for every nested object.

This legacy approach caused several problems:
1. **Namespace Pollution**: Every ephemeral child structure was hoisted into the module's global symbol namespace.
2. **Obscured Hierarchy**: Developers could not visually see the payload hierarchy directly inside the root schema.
3. **Key Alias Inconsistency**: Key remapping used positional string arguments (`display_name str "display-name"`), which is invalid for inline blocks where positional strings denote type names.
4. **Sample Loss**: Nested dictionary samples across multiple array entries were not merged if more than one sample dictionary was present, falling back to `@skip`.

Now that the KDL Schema DSL supports inline JSON schemas, `json_to_kdl` can be streamlined to generate a single, clean, hierarchical schema.

## Solution

Refactor `json_to_kdl` to exclusively generate inline JSON schemas within a single top-level `json` root declaration (or `(array)json` root schema when the input is an array of objects).

Key elements of the solution:
- Single nested objects are emitted as anonymous inline blocks (`field_name { ... }`), allowing the compiler to synthesize hoisted model names automatically.
- Arrays of objects are emitted as inline blocks with an explicit item model name (`field_name (array)ItemModelName { ... }`), where `ItemModelName` defaults to `PascalCase(field_name) + "Item"`.
- Collision resolution: If an item model name collides with another model name in the schema, it is disambiguated by prepending ancestor path names in PascalCase.
- Key aliasing: All remapped keys consistently use the canonical `from="..."` attribute.
- Empty object safety: Empty objects (`{}`) are emitted as `field_name @skip // empty object` without child blocks to avoid compiler errors `E001` and `E002`.
- Recursive sample merging: Multiple sample objects are merged across all nesting levels, preserving all discovered fields and attaching `@omitempty` to partial fields.

## User Stories

1. As a scraper developer, I want `json_to_kdl` to generate a single root `json` declaration with nested inline blocks, so that the resulting schema mirrors the structure of my JSON payload.
2. As a scraper developer, I want nested single objects to be generated as anonymous inline blocks (`field_name { ... }`), so that I do not need to name intermediate child structures manually.
3. As a developer, I want the KDL compiler to automatically synthesize schema names for anonymous inline blocks upon compilation, so that backend code generation continues to receive properly named typed models without global naming conflicts.
4. As a developer, I want arrays of objects to be declared inline with an explicit item model name (`items (array)ItemsItem { ... }`), so that the generated KDL complies with the KDL DSL requirement that `(array)` binds to a following model name.
5. As an API client author, I want array item model names to be derived from the field name in PascalCase with an `Item` suffix (e.g., `users` -> `UsersItem`), so that generated types are descriptive and idiomatic.
6. As a developer with complex payloads containing repeated field names (e.g. `order.items` and `profile.items`), I want colliding array item model names to be automatically disambiguated with ancestor prefixes (e.g. `OrderItemsItem`), so that duplicate schema definition errors are prevented.
7. As a developer, I want source JSON keys that are not valid identifiers to be normalized into snake_case field names and accompanied by a `from="<source_key>"` property, so that generated models have idiomatic field names while mapping accurately to the wire format.
8. As a developer, I want all key aliases to uniformly use `from="..."` syntax across both scalar fields and inline blocks, so that the schema is consistent and avoids ambiguity with positional arguments.
9. As a developer, I want empty JSON objects (`{}`) to be emitted as `<field> @skip // empty object` without a block body, so that the schema does not trigger `E001` (empty inline block) or `E002` (`@skip` on inline block).
10. As a developer, I want empty JSON arrays (`[]`) to be emitted as `<field> (array)null @skip // empty array`, so that the schema validates cleanly while leaving a clear hint for manual type annotation.
11. As a developer, I want heterogeneous JSON arrays with mixed types to be emitted as `<field> (array)null @skip // <types>`, so that unsupported union arrays do not crash generation and can be manually resolved.
12. As a developer, I want null JSON values (`null`) to be emitted as `<field> nil // unknown real type`, so that I know the field was present in the payload and can replace `nil` with the real type.
13. As a developer, I want fields that do not appear in all samples of an array of objects to be annotated with `@omitempty`, so that optional fields are accurately marked.
14. As a developer, I want nested objects across multiple items in an array to be recursively merged, so that fields present in only some sample instances are discovered and marked `@omitempty`.
15. As a developer, I want a top-level JSON array of objects to generate `(array)json <Name>Item { ... }`, so that root list responses are correctly modeled as array root schemas.
16. As a CLI user running `ssc-gen json-to-kdl`, I want the output to be verified with `parse_module` before writing, so that invalid KDL schemas are never persisted to disk.

## Implementation Decisions

### 1. Unified Inline Output Architecture
The multi-definition accumulator is replaced with a single tree traversal that renders directly into a nested KDL document with 4-space indentation per level. Only one top-level schema is emitted: `json <RootName> { ... }` or `(array)json <RootName>Item { ... }`.

### 2. Anonymous Single Object Blocks
When a field is an object, it is emitted as:
```kdl
field_name [from="<original_key>"] [@omitempty] {
    ...
}
```
No explicit type name is emitted between the field name and the opening brace. The compiler's existing recursive hoisting will synthesize the schema name (`{Parent}{FieldName}`).

### 3. Explicit Array Item Model Names
When a field is an array of objects, it is emitted as:
```kdl
field_name (array)<ItemModelName> [from="<original_key>"] [@omitempty] {
    ...
}
```
The base item model name is calculated as `to_pascal_case(field_name) + "Item"`.

### 4. Collision Disambiguation Strategy
A set of all declared model names in the current generation run is tracked. If an array field's base item model name already exists in the set or matches the root schema name:
- The generator prepends the PascalCase name of the enclosing parent object (or ancestor chain) to form `{Parent}{Field}Item`.
- If a collision still persists, an incremental numeric suffix (`2`, `3`, ...) is appended.
- The finalized name is registered in the used model names set.

### 5. Unified `from="..."` Key Remapping
Any field whose normalized identifier differs from the raw JSON key receives a `from="<raw_key>"` property. Legacy positional string aliases (`field type "alias"`) are discontinued in favor of explicit `from="..."`.

### 6. Safe Empty Object Handling
Empty dictionaries (`{}`) have no fields. Emitting an empty inline block triggers `error[E001]: empty inline json block`. Emitting `@skip` on an inline block triggers `error[E002]: cannot use '@skip' on inline json block`. Therefore, empty objects are rendered as a scalar skip field:
```kdl
field_name @skip // empty object
```

### 7. Recursive Multi-Sample Merging
When multiple samples exist for an object (e.g. from multiple array items), all unique keys across all samples are merged in insertion order. Fields appearing in fewer samples than the total sample count receive `@omitempty`. Nested dictionary samples are recursively combined rather than falling back to `@skip`.

## Testing Decisions

- **Behavioral Testing**: Tests assert against external behavior:
  - Exact KDL output string from `json_to_kdl(value)`.
  - Passing the generated KDL through `parse_module(source)` and verifying zero error diagnostics.
  - Verifying AST structure resulting from compilation of the generated KDL (including hoisted child `JsonDef` nodes).
  - CLI file generation and overwrite prompt behavior via `CliRunner`.
- **Target Modules**:
  - `ssc_codegen/json_to_kdl.py`
  - `tests/test_json_to_kdl.py`
- **Prior Art**:
  - `tests/test_json_to_kdl.py`: Existing tests for JSON to KDL translation.
  - `tests/test_json_projection.py`: Tests for inline JSON schema compilation and hoisting.

## Out of Scope

- Automatic inference of dynamic map dictionaries (`(dict)json` or inline `(dict)`). All JSON objects are generated as structured schemas.
- Retaining the legacy flat multi-definition schema format as a CLI option.
- Schema inference from non-JSON formats or multiple files simultaneously.

## Further Notes

This change makes the output of `ssc-gen json-to-kdl` substantially more compact and directly aligned with modern KDL Schema DSL conventions introduced in ADR-0004.
