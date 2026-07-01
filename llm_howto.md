# How-to: Extending ssc_codegen

## Adding a New Pipeline Operation

1. **AST node** — define in `ast/<category>.py` (inherit `Node`), set `accept`/`ret` VariableType defaults
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/expressions.py` for the new keyword
4. **Core type rule** — add accept→return mapping in `core/type_checking.py` `_OP_TYPES` dict
5. **Visitor methods** — add `visit_<node_name>` generator method in `Visitor` (visitor.py) for shared logic, override in `PyHtmlBase` and/or `JsPure` for language-specific spelling

## Adding a New Struct Directive

1. **AST node** — define in `ast/struct.py` (inherit `Node`)
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/struct_parser.py` for the new @directive
4. **Visitor methods** — add `visit_<node_name>` in `Visitor` and/or dialect subclasses

## Adding a New Converter Target

1. Create `ssc_codegen/converters/new_target.py`
2. Subclass `Visitor` (or `PyHtmlBase` if Python-based) — override `visit_*` methods for target-language spelling
3. Set class attrs for type mapping: `TYPES`, `ARRAY_TYPE_FMT`, `OPTIONAL_TYPE_FMT`, `DOCUMENT_TYPE`, `DOCUMENT_ARRAY_TYPE`, `AND_OP`, `DEFAULT_TYPE`, `OPTIONAL_ON_OMITEMPTY`
4. Create module-level instance (e.g. `NEW_CONVERTER = NewTarget()`)
5. Register in `main.py` Target enum and converter mapping
