# Specification: JSON Descriptor Codegen — Canonical Constants and Symbolic References

## Problem Statement

Current code generators for JSON schemas (`JsonDef`) inline deeply nested dictionary structures directly at each site of use:
1. `json_def_descriptors` recursively expands child schemas inline, creating deeply nested, redundant data structures.
2. In large real-world schemas (such as AniLiberty and complex REST APIs), child schema dictionaries are repeatedly duplicated within parent schema descriptors, `@request` client methods, and `@error` matchers, causing generated code size to explode (e.g. 100k+ lines).
3. Generated descriptor constants use non-standard, private names (e.g. `_{snake_name}_JSON_DESCRIPTORS` or `_{camel_name}JsonDescriptors`), obscuring them from IDE discovery and LSP tooling.
4. Python and JavaScript REST client methods (`emit_method_rest`) and error matchers (`emit_matcher_list_def`) re-render full descriptor dictionaries as literals in lambda expressions instead of referencing pre-generated module-level descriptor constants by identifier.

## Solution

1. **Core Canonical Naming & Symbolic References**:
   - Provide a shared canonical naming helper `json_descriptor_var_name(name: str) -> str` that produces `JSON_DESCRIPTOR_{to_snake_case(name).upper()}` without leading underscores.
   - Introduce a symbolic schema reference type `DescriptorRef(schema_name: str)` representing a reference to another schema descriptor.
   - Update `json_def_descriptors` to emit `DescriptorRef` for nested schema references (single nested objects, arrays of objects, and schema-valued dictionaries) instead of expanding child schema dictionaries inline.

2. **Python Target Alignment**:
   - Emit module-level descriptor constants named `JSON_DESCRIPTOR_{SCHEMA_NAME.upper()}`.
   - Render `DescriptorRef` as unquoted constant identifiers (e.g. `JSON_DESCRIPTOR_IMAGE`, `[JSON_DESCRIPTOR_GENRE]`, `{"__dict__": True, "__value__": JSON_DESCRIPTOR_EPISODE}`).
   - Update `visit_jsonify` to pass `JSON_DESCRIPTOR_{SCHEMA_NAME.upper()}` to `ssc_json_project`.
   - Update `emit_method_rest` and `emit_matcher_list_def` in `python/rest.py` to reference `JSON_DESCRIPTOR_{SCHEMA_NAME.upper()}` by name instead of inlining dictionary literals. Support `response_path` accessors alongside descriptor constants.
   - Remove dead descriptor rendering helpers from `python/rest.py`.

3. **JavaScript Target Alignment**:
   - Emit top-level constants named `const JSON_DESCRIPTOR_{SCHEMA_NAME.upper()} = ...;`.
   - Render `DescriptorRef` as unquoted constant identifiers (e.g. `JSON_DESCRIPTOR_CHILD`, `[JSON_DESCRIPTOR_CHILD]`, `{"__dict__": true, "__value__": JSON_DESCRIPTOR_CHILD}`).
   - Update `visit_jsonify` to pass `JSON_DESCRIPTOR_{SCHEMA_NAME.upper()}` to `sscJsonProject`.
   - Update `emit_method_rest` and `emit_matcher_list_def` in `javascript/rest.py` to reference `JSON_DESCRIPTOR_{SCHEMA_NAME.upper()}` instead of inlining object literals.
   - Support `response_path` accessors alongside descriptor constants.

4. **Verification & Benchmarking**:
   - Ensure all unit and integration tests pass (1600+ tests).
   - Verify generated code with ruff format and mypy.
   - Benchmark against `aniliberty_parser.kdl` to verify dramatic reduction in code size and duplicate dictionary literals.

## User Stories

1. As a developer writing schemas with nested JSON models, I want generated descriptor dictionaries to reference child schemas by constant name rather than duplicating them inline, keeping generated files compact and readable.
2. As a developer reading generated Python or JavaScript code, I want schema descriptors to have clear, public constant names like `JSON_DESCRIPTOR_USER` that autocomplete in IDEs.
3. As a developer inspecting REST client methods, I want `value_fn` and `@error` matcher lambdas to refer to descriptor constants rather than multi-thousand-character inlined dictionary literals.
4. As a scraper developer using `jsonify`, I want the runtime projection calls to reference standardized descriptor constants seamlessly.
