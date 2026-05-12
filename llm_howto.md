# How-to: Extending ssc_codegen

## Adding a New Pipeline Operation

1. **AST node** — define in `ast/<category>.py` (inherit `Node`), add `accept`/`ret` VariableType defaults
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/expressions.py` for the new keyword
4. **Core type rule** — add accept→return mapping in `core/type_checking.py` `_OP_TYPES` dict
5. **Converter handlers** — register on `PY_BASE_CONVERTER` and `JS_CONVERTER`

## Adding a New Struct Directive

1. **AST node** — define in `ast/struct.py` (inherit `Node`)
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/struct_parser.py` for the new @directive
4. **Converter handlers** — register on `PY_BASE_CONVERTER` and `JS_CONVERTER`

## Adding a New Converter Target

1. Create `ssc_codegen/converters/new_target.py`
2. Instantiate `BaseConverter()` or extend existing one (e.g. `PY_BASE_CONVERTER.extend()`)
3. Register handlers for all AST node types via `@converter.pre(NodeType)` / `@converter.post(NodeType)`
4. Map `VariableType` → target language types
5. Register in `main.py` Target enum and converter mapping
