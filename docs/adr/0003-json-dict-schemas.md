# JSON Dict Schemas

Accepted: Support dynamic key-value JSON objects with homogeneous values through
`(dict)json` top-level declarations and inline `(dict)` field blocks in KDL schemas.
`(dict)json Name` and `field (dict) { ... }` declare `@value` (mandatory, supporting
primitives, arrays, and nested JSON schemas) and `@key` (optional scalar type: `str`, `int`,
`float`, `bool`, defaulting to `str`). KDL grammar forbids multiple annotations like
`(dict)(array)str`, so `@key` and `@value` sub-nodes mirror the proven `(dict)struct`
convention.

Code generation emits native dictionary types for all four targets: Python `Dict[K, V]`,
Go `map[K]V`, Rust `HashMap<K, V>`, and JavaScript JSDoc `Record<K, V>`. In accordance with
the project's projection contract, runtime projection in Python/JS preserves keys without
type casting, whereas static target compilers (Go, Rust) handle unmarshaling. In the linter,
`(dict)json` rejects arbitrary field names, requiring `@value` and allowing only scalar
types for `@key`.
