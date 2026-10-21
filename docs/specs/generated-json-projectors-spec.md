# Specification: Generated JSON Projectors, Strict Field Identifiers, and GJSON Path Subset

## Problem Statement

When defining `json` schemas in KDL 2.0 and executing generated parsers or REST clients, developers face three interconnected problems:

1. **Silent KDL Field-Name Typos and Cross-Target Breakage**:
   In KDL 2.0, characters such as `:` and `@` are legal inside bare identifiers. When a schema author writes `url: str` out of TypeScript/Python habit instead of `url str`, or declares `@type str` without an explicit `from="@type"` **JSON key alias**, `ssc-gen check` reports zero errors. In Python, this silently generates a broken runtime lookup for key `'url:'`; in Go and Rust, unmapped special characters in **JSON field names** emit syntactically invalid struct field declarations that fail target compilation.

2. **Opaque Stack Traces and Redundant Descriptor Tables in Runtime Projection**:
   Python and JavaScript targets emit module-level `JSON_DESCRIPTOR_*` dictionaries of 4-tuples `(wire_path, is_optional, is_omitempty, nested_desc)` alongside legacy dead `ssc_remap_json_keys` helpers, and interpret them recursively via `ssc_json_project` / `sscJsonProject`. When a nested schema field is missing or null in a complex payload (for example, `CdnVideoHubResponse` -> `Vast` -> `Preroll`), the resulting traceback contains only repeated recursive frames inside `ssc_json_project` and an error message that omits the enclosing schema name, making it slow to locate which model failed. In addition, passing a non-object value (such as `None` from an invalid JSON response body) to an object schema projector silently returns the non-object value instead of raising a schema error.

3. **Underspecified Path Grammar Across Targets**:
   While the Go target delegates `from="..."` and `jsonify path="..."` evaluation to `gjson`, Python, JavaScript, and Rust use a naive `path.split('.')` helper that cannot escape literal dots in JSON keys (`a\.b`) and lacks `gjson` array length (`#`) and array element projection (`#.subpath`) capabilities.

## Solution

Align all four target backends and the linter around **ADR-0005**:

1. **Strict Portable JSON Field Names (`E403`)**:
   Enforce in `ssc-gen check` that every canonical **JSON field name** (after stripping `?`) matches `^[A-Za-z_][A-Za-z0-9_-]*$` and is valid across target languages (`E403`). Provide contextual hints when a field name ends with `:` (suggesting `url str` or `from="url:"`) or contains special characters like `@` (suggesting `from="@..."`).

2. **Compile-Time Validation and Runtime Micro-Interpreter for GJSON Path Expressions (`E040`)**:
   Define and validate a deterministic, filter-free **GJSON path expression** grammar in `from="..."` and `jsonify path="..."` supporting:
   - object key segments (`user`, `@id`),
   - escaped literal dots (`\.`) and backslashes (`\\`) within keys (`os\.version` -> key `"os.version"`),
   - non-negative integer array indices (`0`, `1`, ...),
   - terminal array length (`items.#`),
   - array element projection (`items.#.name`).
   Go continues to evaluate paths via `gjson`, while Python, JavaScript, and Rust evaluate the exact same grammar through a zero-dependency runtime micro-interpreter.

3. **Generated JSON Projectors Replacing `JSON_DESCRIPTOR_*` Constants**:
   Replace `JSON_DESCRIPTOR_*` tables, `DescriptorRef`, `ssc_json_project`, and dead `ssc_remap_json_keys` helpers in Python and JavaScript with generated per-schema **JSON projector** functions (`_project_<schema>` in Python, `_project<Schema>` in JavaScript), matching the function-based architecture of Go (`UnmarshalJSON`) and Rust (`from_value`). Each generated **JSON projector**:
   - validates that the input container matches the expected schema shape (`dict` or `list`), raising `SscJsonSchemaError` on `None` or primitive values,
   - uses direct `O(1)` key lookup helpers when the wire key is a flat key without unescaped dots or `#`, and calls the GJSON path micro-interpreter only for multi-segment or `#` expressions,
   - calls child **JSON projectors** directly by function name so runtime stack traces show the exact schema call chain (`_project_cdn_video_hub_response` -> `_project_vast` -> `_project_preroll`),
   - includes the `<SchemaName>.<field_name>` context in `SscJsonFieldMissingError`, `SscJsonPathError`, and `SscJsonSchemaError` messages.

## User Stories

1. As a schema author who accidentally writes `url: str` with a colon in a `json` block, I want `ssc-gen check` to reject the field with `E403` and a hint explaining that KDL separates field names and types with a space, so that I catch the typo before generating code.
2. As a schema author modeling JSON-LD keys like `@context` or `@type`, I want `ssc-gen check` to require a portable **JSON field name** paired with `from="@context"`, so that the schema compiles cleanly across Python, JavaScript, Go, and Rust.
3. As a schema author naming a `json` field after a target-language reserved word (or invalid identifier), I want `ssc-gen check` to report `E403` during schema validation, so that generated Go, Rust, Python, and JavaScript code never fails with syntax errors.
4. As a developer debugging a `SscJsonFieldMissingError` in a deeply nested REST response, I want the Python and JavaScript call stacks to show each nested **JSON projector** function (`_project_parent` -> `_project_child`), so that I can immediately identify the failing sub-schema in the traceback.
5. As a developer reading a `SscJsonFieldMissingError`, `SscJsonPathError`, or `SscJsonSchemaError` message, I want the error message to include the qualified `SchemaName.field_name` alongside the wire key/path, so that I can locate the broken field without inspecting the payload manually.
6. As a developer calling a generated REST client when an upstream server returns `null`, a primitive, or an unparseable body on a 2xx response expecting a `json` schema, I want the **JSON projector** to raise `SscJsonSchemaError` instead of silently returning `None` inside `Ok(value=None)`.
7. As a schema author extracting a flat JSON key that contains a literal dot (e.g. `{"os.version": "1.0"}`), I want to write `from="os\\.version"`, so that Python, JavaScript, Go, and Rust all read the literal key `"os.version"` instead of traversing `os` -> `version`.
8. As a schema author extracting a single property from an array of objects (e.g. `{"tags": [{"name": "action"}, {"name": "sci-fi"}]}`), I want to write `tags (array)str from="tags.#.name"`, so that I can project the array into `["action", "sci-fi"]` without declaring a throwaway intermediate `json` schema.
9. As a schema author extracting the count of an array in JSON (e.g. `{"items": [1, 2, 3]}`), I want to write `count int from="items.#"`, so that the **JSON projector** returns the array length `3`.
10. As a schema author who writes a malformed **GJSON path expression** (such as leading/trailing dots `.a`, empty segments `a..b`, negative array indices `a.-1`, unescaped dangling backslashes, or unsupported filter expressions `a.#[x==1]`), I want `ssc-gen check` to reject the path with `E040`, so that unsupported path syntax is caught at lint time.
11. As a developer inspecting generated Python and JavaScript parser modules, I want dead `ssc_remap_json_keys` / `sscRemapJsonKeys` helpers and `JSON_DESCRIPTOR_*` tuple tables removed, so that generated files and `sscgen_runtime` contain only active **JSON projector** code.
12. As a developer using `(dict)json` top-level schemas and inline `(dict)` fields with scalar or nested schema `@value` types, I want generated **JSON projectors** to validate that the input is a dictionary and project each value through the child **JSON projector**, so that dictionary schemas behave consistently with object schemas.
13. As a developer using `jsonify Schema path="..."` in HTML or raw structs, I want the `path` argument to use the same **GJSON path expression** micro-interpreter and pass the selected fragment into the target schema's **JSON projector**, so that `jsonify` and REST `@request` share identical semantics.

## Implementation Decisions

1. **Linter Validation for JSON Field Names (`E403`)**:
   - Extend `json` field linting and symbol collection so every **JSON field name** (with trailing `?` stripped) is validated against `^[A-Za-z_][A-Za-z0-9_-]*$` and target identifier/reserved-word rules (`SymbolKind.FIELD` / `json` field check).
   - Emit `E403` when validation fails:
     - If the raw field name ends with `:`, attach hint: `in KDL field name and type are separated by space ('<name_without_colon> <type>'); if the JSON key ends with ':', use '<name_without_colon> <type> from="<raw_name>"'`.
     - If the raw field name starts with `@` or contains other non-identifier characters, attach hint: `use a portable identifier with 'from', e.g. '<sanitized_name> <type> from="<raw_name>"'`.

2. **GJSON Path Expression Parser and Validator (`E040`)**:
   - Replace `_is_malformed_dotpath` with a dedicated **GJSON path expression** parser/validator supporting:
     - Key segments with `\ overall` escape handling for `\.`, `\\`, and `\#`.
     - Non-negative integer index segments (`0`, `1`, ...).
     - `#` segment: valid either as the final segment (array length) or followed by a subpath `#.subpath` (array projection).
     - Reject empty paths, leading/trailing unescaped dots, consecutive unescaped dots (`..`), trailing unescaped `\`, and filter brackets (`#[...]`, `#(...)`) with diagnostic code `E040`.
   - Provide a compile-time helper that classifies a parsed **GJSON path expression** into either:
     - **Direct key**: a single key segment (after unescaping `\.` / `\\`) with no array index and no `#` operator, or
     - **Path query**: a multi-segment path, array index, or `#` expression requiring the runtime GJSON micro-interpreter.

3. **Python and JavaScript JSON Projector Codegen**:
   - Remove `JSON_DESCRIPTOR_*` constant emission, `DescriptorRef`, `json_def_descriptors`, `json_def_mapping`, ` json_def_needs_remap`, and `ssc_remap_json_keys` / `sscRemapJsonKeys`.
   - For each `JsonDef` (including hoisted inline schemas and `(dict)json` schemas), emit a dedicated **JSON projector** function:
     - Python: `def _project_<snake_name>(data: Any) -> <PascalName>Json:`
     - JavaScript: `function _project<PascalName>(data)`
   - Inside each generated **JSON projector**:
     - If `JsonDef.is_array` is true (or when projecting an array field), validate `isinstance(data, list)` / `Array.isArray(data)` (raising `SscJsonSchemaError`) and map elements through the item projector.
     - If `JsonDef.is_dict` is true, validate `isinstance(data, dict)` and project dictionary values through the value projector (if `@value` references a `JsonDef`).
     - For object schemas, call a compact runtime helper to verify `data` is a `dict` / plain object (raising `SscJsonSchemaError(f"<SchemaName>: expected dict, got {type(data).__name__}")` on `None`, lists, or primitives).
     - Extract each non-`@skip` field using compact runtime helpers for direct keys vs **GJSON path expressions**, enforcing `?` (nullable) and `@omitempty` rules, and invoking child `_project_<child>` functions for nested schema references.
   - Update `visit_jsonify`, `emit_method_rest`, and `emit_matcher_list_def` in Python and JavaScript to call `_project_<schema>` / `_project<Schema>` directly instead of `ssc_json_project(..., JSON_DESCRIPTOR_*)`.

4. **Runtime Micro-Interpreter Across Python, JavaScript, and Rust**:
   - Implement the filter-free **GJSON path expression** evaluator in Python (`ssc_resolve_dotpath` / `ssc_gjson`), JavaScript (`sscResolveDotpath` / `sscGjson`), and Rust (`rt::json_path` / `rt::json_opt`):
     - Tokenize path segments respecting `\.` and `\\` escapes.
     - Support non-negative integer indices on arrays.
     - Support terminal `#` returning `len(current)` when `current` is a list/array.
     - Support `#.subpath` by iterating over array elements and recursively evaluating `subpath` on each element, collecting non-missing results into a list.
   - Include `<SchemaName>.<field_name>` context in raised `SscJsonFieldMissingError`, `SscJsonPathError`, and `SscJsonSchemaError` exceptions.

## Testing Decisions

- **Single High-Level Seam (`parse_module` -> `converter.convert` -> runtime execution)**:
  - All tests exercise external behavior starting from KDL schema source text through `parse_module` (for linter diagnostics `E403` and `E040`) and `converter.convert(module)` followed by executing the generated Python (`exec`), JavaScript (`node`), Go (`go test`), and Rust (`cargo test`) code on real JSON payloads.
  - Error tests assert on the raised exception type (`SscJsonFieldMissingError`, `SscJsonPathError`, `SscJsonSchemaError`), the presence of `SchemaName.field_name` in the error message, and the presence of the generated `_project_<schema>` function name in the traceback frames.
  - Delete obsolete unit tests that coupled directly to internal `JSON_DESCRIPTOR_*` tuple shapes and `DescriptorRef` dataclasses (`tests/test_descriptor_refs.py`).
- **Prior Art**:
  - `tests/test_json_projection.py`
  - `tests/integration/test_codegen_run.py`
  - `tests/integration/test_rest_codegen.py`
  - `tests/js/test_js_codegen.py`
  - `tests/go/test_go_codegen.py`
  - `tests/rust/test_rust_codegen.py`

## Out of Scope

- Predicate filter queries in GJSON paths (such as `items.#[studio=="Jam Club"].id` or `#(...)` multipaths).
- Modifying the Go target to remove `github.com/tidwall/gjson` (Go already supports the target GJSON path subset natively via `gjson`).
- Runtime type coercion of primitive JSON values (e.g. casting `"123"` to `123`).

## Further Notes

- Documented in `ADR-0005` (`docs/adr/0005-generated-json-projectors-and-gjson-subset.md`), which supersedes `ADR-0001`.
- Canonical domain terms (**JSON field name**, **JSON key alias**, **GJSON path expression**, **JSON projector**) are defined in `CONTEXT.md`.
