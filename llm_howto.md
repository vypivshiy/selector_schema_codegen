# How-to: Extending ssc_codegen

## Adding a New Pipeline Operation

1. **AST node** — define in `ast/<category>.py` (inherit `Node`), set `accept`/`ret` VariableType defaults
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/expressions.py` for the new keyword
4. **Core type rule** — add accept→return mapping in `core/type_checking.py` `_OP_TYPES` dict
5. **BaseWalker dispatch** — add entry in `_DISPATCH` dict (`traversal/walker.py`): `NodeClass: "visit_node_name"`
6. **Visitor methods** — implement `visit_<node_name>(self, node, ctx) -> list[str]` in:
   - `targets/python/visitor.py` (PythonVisitor)
   - `targets/javascript/visitor.py` (JsVisitor)
   - If HTML-specific: add to DomSpelling ABC (`targets/python/html_libs/base.py`) + implement in each spelling subclass

## Adding a New Struct Directive

1. **AST node** — define in `ast/struct.py` (inherit `Node`)
2. **Export** — re-export from `ast/__init__.py`
3. **Core parser** — add handler in `core/struct_parser.py` for the new @directive
4. **BaseWalker dispatch** — add entry in `_DISPATCH` dict
5. **Visitor methods** — implement `visit_<node_name>` in PythonVisitor and/or JsVisitor

## Adding a New Python HTML Library (DomSpelling)

1. Create `targets/python/html_libs/new_lib.py`
2. Subclass `DomSpelling` (from `targets/python/html_libs/base.py`)
3. Set data attrs: `parser_imports`, `document_type`, `document_array_type`, `init_arg_type`, `init_from_str_expr`, `extra_utilities`, `supports_xpath`
4. Implement all expression methods (return `list[str]`): `css_select`, `css_select_all`, `css_remove`, `xpath_select`, `xpath_select_all`, `xpath_remove`, `text`, `raw`, `attr`, `to_bool`
5. Implement all predicate methods (return `str`): `pred_css`, `pred_xpath`, `pred_has_attr`, `pred_attr_*`, `pred_text_*`
6. Export from `targets/python/html_libs/__init__.py`
7. Add to `targets/python/__init__.py`: `NEW_LIB_CONVERTER = PythonVisitor(dom_spelling_cls=NewLibDomSpelling)`
8. Register in `targets/resolver.py` `_resolve_python()` spellings dict

## Adding a New HTTP Client Strategy (Python)

1. Create `targets/python/http_libs/new_client.py`
2. Subclass `HttpLibStrategy` (from `targets/python/http_libs/base.py`)
3. Set class attrs: `import_line`, `sync_client_type`, `async_client_type`, `transport_exception`
4. Implement `rest_runtime_lines() -> list[str]` — REST runtime source with library-specific `except` clause
5. Add to `_HTTP_STRATEGIES` dict in `targets/python/visitor.py`
6. Add to valid clients in `targets/resolver.py` `_resolve_python()`

## Adding a New Target Language

1. Create `targets/new_lang/` directory with `__init__.py` and `visitor.py`
2. Subclass `BaseWalker` (from `traversal/walker.py`) — implement ALL `visit_*` methods that appear in `_DISPATCH`
3. Set class attrs for type mapping: `TYPES`, `ARRAY_TYPE_FMT`, `OPTIONAL_TYPE_FMT`, `AND_OP`, `DEFAULT_TYPE`, `OPTIONAL_ON_OMITEMPTY`
4. Use `self._builder.require_import(line)` and `self._builder.require_std(name, code=, imports=)` for helpers
5. Create pre-built instance: `NEW_CONVERTER = NewLangVisitor()` in `__init__.py`
6. Add `_resolve_new_lang(spec)` function in `targets/resolver.py`
7. Add dispatch case in `resolve()` function
