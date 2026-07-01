# Core Architecture (core/)

Unified KDL → Module reader with integrated linting.
Entry point: `parse_module(source, path) → Module`

- `SscReader` extends `Reader` (from `kdl/reader.py`) — walks KDL CST, builds Module AST
- Uses `parse_into()` + `KDL2CSTParser` (custom KDL 2.0 parser, NOT tree-sitter)
- `ParseContext` — tracks module state (defines, imports, struct_map)
- `LintContext` — collects errors/warnings during parse
- Linting is integrated into parsing, not a separate pass
- Type checking happens inline via `core/type_checking.py`
- Error output: `format_diagnostics(diagnostics) → str`

### Expression parsing (core/expressions.py)
Handles all pipeline expression nodes: selectors, string ops, regex, cast, control, predicates.
Uses `_OP_TYPES` table for type inference.

### Struct parsing (core/struct_parser.py)
Handles struct body: fields, @init, @pre-validate, @split-doc, @request, @error, @check.
`parse_json_fields` expands block defines in json context (bare define name → recursive field expansion).

### SscReader pass 3 — module body assembly (core/reader.py)
The reader loop calls `handle_json` / `handle_struct` but does **NOT** append their results to `module.body` directly. Instead:
- `handle_json` stores results in `ctx.json_defs`
- `handle_struct` stores results in local `typedefs` / `structs` lists

After the loop, a single `module.body.extend(...)` call assembles all definitions in order:
```
json_defs → typedefs → structs
```
**Do NOT append json/struct nodes to `module.body` inside the loop** — they are added once via the final extend. Appending inside the loop causes duplicate output in generated code.

### Module-level handlers (core/module_handler.py)
- `handle_define` — process define declarations
- `handle_json` — process json schema declarations; stores result in `ctx.json_defs` (not `module.body`)
- `handle_struct` — process struct declarations; returns (struct, typedef) pair
- `resolve_imports` — resolve cross-file imports
