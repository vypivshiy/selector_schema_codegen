# Core Architecture (core/)

Unified KDL → Module reader with integrated linting.
Entry point: `parse_module(source, path) → Module`

- `SscReader` extends `Reader` — walks KDL CST, builds Module AST
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

### Module-level handlers (core/module_handler.py)
- `handle_define` — process define declarations
- `handle_json` — process json schema declarations
- `handle_struct` — process struct declarations
- `handle_transform` — process transform declarations
- `resolve_imports` — resolve cross-file imports
