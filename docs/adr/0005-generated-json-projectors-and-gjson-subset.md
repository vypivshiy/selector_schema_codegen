# Generated JSON Projectors, Strict Field Identifiers, and GJSON Path Subset

Status: accepted (supersedes ADR-0001)

Every `json` schema compiles into a dedicated **JSON projector** function (`_project_<schema>` in Python, `_project<Schema>` in JavaScript, `UnmarshalJSON` in Go, `from_value` in Rust) rather than emitting `JSON_DESCRIPTOR_*` tuple tables interpreted at runtime by `ssc_json_project` or legacy `ssc_remap_json_keys`. Generating one projector function per schema aligns all four language backends, lets the compiler distinguish `O(1)` flat key lookups from multi-segment path evaluation at compile time, and produces readable call stacks (`_project_parent` -> `_project_child`) and schema-qualified `SscJsonError` messages (`Schema.field`) instead of opaque recursive interpreter frames.

Canonical **JSON field names** in `json` blocks must be valid portable identifiers (`^[A-Za-z_][A-Za-z0-9_-]*$` and not target reserved words, enforced by `ssc-gen check` with `E403` and targeted hints for common KDL typos such as trailing colons `url: str` or unmapped `@type`). Any non-identifier JSON key or nested path must be declared explicitly via `from="..."`.

Both `from="..."` and `jsonify path="..."` accept a deterministic, filter-free **GJSON path expression** subset validated at lint time (`E040`): object keys, escaped literal dots (`\.`) and backslashes (`\\`), non-negative integer array indices (`0`, `1`, ...), terminal array length (`#`), and array element projection (`#.subpath`). Go delegates path evaluation to `github.com/tidwall/gjson`, while Python, JavaScript, and Rust evaluate the same subset through a zero-dependency runtime micro-interpreter.
