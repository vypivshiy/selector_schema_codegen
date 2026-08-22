# Core Architecture (core/)

Unified KDL → Module reader with integrated linting.
Entry point: `parse_module(source, source_path=...) → (Module, list[ReadDiagnostic])`

- `kdlquery.parse()` builds mutable `KdlDocument` / `KdlNode` CST objects.
- `core/reader.py` orchestrates import resolution, lint passes, and AST build.
- `ParseContext` — tracks module state (defines, imports, struct_map)
- `LintContext` — collects errors/warnings during parse
- Fatal structural diagnostics stop AST build; malformed input returns diagnostics instead of leaking index/value errors.
- Import resolution uses separate active/loaded sets, so diamond imports are deduplicated and real cycles are diagnosed.
- Type checking happens inline via `core/type_checking.py`
- Error output: `format_diagnostics(diagnostics) → str`

### kdlquery — внешняя зависимость

KDL-парсер `kdlquery>=1.3.0` (отдельный репозиторий). Даёт:
- `parse(src) → KdlDocument`, `KdlNode` — мутабельное дерево CST с parent-ссылками.
- CSS3-подобные селекторы: `doc.select("struct:root:has(nested)")`,
  `node.select_one("@request")` — основа для правил линтера в `core/linter.py`.
- `ReadDiagnostic` / `Severity` / `Span` / `Position` — типы для диагностики.

Полная справка по селекторам и паттернам —
[docs/maintainers/kdlquery.md](docs/maintainers/kdlquery.md).
В `core/linter.py` активно используются `:root`, `:has(...)`, `:not(...)`,
scoped `node.select(...)` для структурных проверок.

### Expression parsing (core/expressions.py)
Handles all pipeline expression nodes: selectors, string ops, regex, cast, control, predicates.
Uses `OP_TYPES` table for type inference.

### Struct parsing (core/struct_parser.py)
Handles struct body: fields, @init, @pre-validate, @split-doc, @request, @error, @check.
`parse_json_fields` expands block defines in json context (bare define name → recursive field expansion).

### Module body assembly (core/reader.py)
The reader loop calls `handle_json` / `handle_struct` but does **NOT** append their results to `module.body` directly. Instead:
- `handle_json` stores results in `ctx.json_defs`
- `handle_struct` stores results in local `typedefs` / `structs` lists

After the loop, a single `module.body.extend(...)` call assembles all definitions in order:
```
json_defs → typedefs → REST artifacts/structs → functions
```
**Do NOT append json/struct nodes to `module.body` inside the loop** — they are added once via the final extend. Appending inside the loop causes duplicate output in generated code.

### Module-level handlers (core/module_handler.py)
- `handle_define` — process define declarations
- `handle_json` — process json schema declarations; stores result in `ctx.json_defs` (not `module.body`)
- `handle_struct` — process struct declarations
- `resolve_imports` — resolve cross-file imports with cycle/dedup tracking
- `register_node_sources` — retain source origin for imported diagnostics
