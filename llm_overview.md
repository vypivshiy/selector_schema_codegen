# ssc_codegen — Project Reference for LLMs

ssc_codegen is a code generator for web scraping parsers.
Input: .kdl schema files describing HTML extraction rules.
Output: parser code for Python (bs4, lxml, parsel, selectolax), JavaScript (DOM API).

Pipeline: .kdl schema → KDL parser (custom KDL 2.0: KDLLexer + KDL2CSTParser) → core (AST + lint) → converter → output code

Version: 0.29.4
Python: >=3.10
CLI entry point: `ssc-gen` (ssc_codegen.main:main)

---

## Project Structure

```
ssc_codegen/
├── __init__.py            # parse_module(src, path, css_to_xpath) → Module
├── main.py                # CLI (typer): generate, check, run, health
├── _logging.py            # ANSI color logging setup
├── exceptions.py          # ParseError, UnknownNodeError, BuildTimeError
├── document_utils.py      # CSS→XPath conversion for AST nodes
├── pseudo_selectors.py    # Parse CSS pseudo-selectors (::text, ::raw, ::attr)
├── regex_utils.py         # Regex flag handling, unverbosify
├── selector_utils.py      # css_to_xpath (cssselect wrapper)
├── health.py              # Selector health check against real HTML
├── ast/                   # AST node definitions
│   ├── __init__.py        # Re-exports all node types
│   ├── base.py            # Node abstract base class
│   ├── types.py           # VariableType, StructType enums
│   ├── module.py          # Module, Docstring (deprecated), Imports, Utilities, CodeStartHook, CodeEndHook
│   ├── struct.py          # StructBase (+ doc field), Field, Init, InitField, PreValidate, SplitDoc, Key, Value, TableConfig, TableRow, TableMatchKey, CheckMethod, StructDocstring (deprecated), StartParse, RequestConfig, PlaceholderSpec, ErrorResponse
│   ├── selectors.py       # CssSelect, CssSelectAll, XpathSelect, XpathSelectAll, CssRemove, XpathRemove
│   ├── extract.py         # Text, Raw, Attr
│   ├── string.py          # Trim, Ltrim, Rtrim, NormalizeSpace, RmPrefix, RmSuffix, RmPrefixSuffix, Fmt, Repl, ReplMap, Lower, Upper, Split, Join, Unescape
│   ├── regex.py           # Re, ReAll, ReSub
│   ├── array.py           # Index, Slice, Len, Unique
│   ├── cast.py            # ToInt, ToFloat, ToBool, Jsonify, Nested
│   ├── control.py         # Fallback, FallbackStart, FallbackEnd, Self, Return
│   ├── predicate_containers.py  # Filter, Assert, Match
│   ├── predicate_ops.py   # PredEq/Ne/Gt/Lt/Ge/Le/Range, PredStarts/Ends/Contains/In/Re/ReAny/ReAll, PredCss/Xpath/HasAttr, PredAttr*, PredText*, PredCount*, LogicNot/And/Or
│   ├── typedef.py         # TypeDef, TypeDefField
│   ├── jsondef.py         # JsonDef, JsonDefField
│   ├── transform.py       # TransformDef, TransformTarget, TransformCall
│   └── helpers.py         # AST utilities
├── core/                  # Unified KDL → Module AST reader + integrated linting
│   ├── __init__.py        # Exports: parse_module, SscReader, ReadDiagnostic
│   ├── reader.py          # SscReader — walks KDL CST, builds Module AST
│   ├── adapter.py         # NodeAdapter — KdlNode → handler protocol
│   ├── contexts.py        # ParseContext, LintContext, ErrorCode, WalkCtx
│   ├── expressions.py     # Pipeline expression parsing, typedef_from_struct
│   ├── predicates.py      # Predicate expression parsing
│   ├── struct_parser.py   # Struct body parsing
│   ├── module_handler.py  # handle_define, handle_json, handle_struct, handle_transform, resolve_imports
│   ├── linting.py         # Argument validation, CSS/XPath/regex linting
│   ├── type_checking.py   # Pipeline type inference and mismatch detection
│   └── format.py          # Diagnostic formatting (text + JSON)
├── parsers/               # HTTP transport parsing (consumed by converters)
│   ├── curl.py            # parse_curl_command() — POSIX curl → kwargs
│   └── http.py            # parse_http_request() — raw HTTP/1.1|2 → kwargs
├── converters/            # Code generators per target language
│   ├── base.py            # BaseConverter, ConverterContext, callback registration
│   ├── helpers.py         # Naming helpers (to_snake_case, to_pascal_case, to_camel_case, jsonify_path_to_segments)
│   ├── request_spec.py    # RequestSpec, parse_to_spec, normalize_placeholder_names
│   ├── py_render.py       # Python code rendering helpers for RequestSpec (render_value, render_dict, render_body)
│   ├── py_bs4.py          # Python BeautifulSoup4 (PY_BASE_CONVERTER)
│   ├── py_lxml.py         # Python lxml
│   ├── py_parsel.py       # Python parsel (Scrapy)
│   ├── py_slax.py         # Python selectolax
│   ├── js_pure.py         # JavaScript vanilla DOM
│   └── runtime/           # Runtime template constants (shared across converters)
│       ├── __init__.py    # Re-exports public API
│       ├── _helpers.py    # _module_has_rest, module_is_rest_only, http_client_import
│       ├── py_base.py     # NOT_REQUIRED_IMPORT, _BASE_UTILITY_LINES, base_utility_lines()
│       ├── py_rest.py     # rest_imports, rest_utilities, runtime_module_content, register_runtime_file
│       ├── py_lxml.py     # _FALLBACK_HTML_LINES, _FALLBACK_HTML_EXPORT
│       └── js_base.py     # JS_BASE_UTILITY_LINES, js_base_utility_lines()
├── kdl/                   # Custom KDL 2.0 parser (NOT tree-sitter)
│   ├── __init__.py        # Re-exports all CST, Reader, and DictReader types
│   ├── parser.py          # KDLLexer, KDL2CSTParser, Token/TokenType, CST node types
│   ├── reader.py          # Reader ABC, Walker, WalkContext, ReadDiagnostic, DiagnosticCollector, parse_into()
│   └── dict_reader.py     # DictReader — KDL → Python dict (Node TypedDict)

tests/
├── integration/
│   ├── test_codegen_run.py     # End-to-end: KDL → generate → execute → verify JSON
│   ├── test_rest_codegen.py    # REST API code generation tests (mocked HTTP)
│   ├── schemas/                # Test .kdl files (00_full through 22_rest_response_path)
│   └── fixtures/               # Test HTML fixtures
├── js/
│   └── test_js_codegen.py      # JS codegen tests (Node.js + jsdom)
├── test_parser.py              # KDL parser tests
├── test_kdl_parser.py          # KDL parser edge cases
├── test_imports.py             # Import/include tests
├── test_css_to_xpath.py        # CSS→XPath conversion tests
└── test_rest_api.py            # REST/transport layer tests

examples/                       # Real-world .kdl schemas
docs/
├── llm.txt                     # KDL DSL v2.1 syntax reference
└── learn/                      # Tutorial chapters (01-09)
```

---

## CLI Commands

```bash
ssc-gen generate schema.kdl -t py-bs4 -o out/                     # generate parser code
ssc-gen generate schema.kdl -t py-bs4 -o out/ --http-client httpx # with @request support
ssc-gen generate schema.kdl -t py-bs4 -o out/ -R                  # separate runtime module
ssc-gen generate schema.kdl -t py-bs4 -o out/ -R -rn my_runtime   # custom runtime name
ssc-gen generate schema.kdl -t py-bs4 -o out/ --css-to-xpath      # CSS→XPath preprocessing
ssc-gen generate schema.kdl -t py-bs4 -o out/ --skip-lint         # skip linting
ssc-gen generate schema.kdl -t py-bs4 -o out/ --package mymod     # package name for generated code
ssc-gen generate schema.kdl -t py-bs4 -o out/ -f json             # JSON output format
ssc-gen check schema.kdl                                            # lint only (text output)
ssc-gen check schema.kdl -f json                                    # lint only (JSON for automation)
ssc-gen run schema.kdl:StructName -i page.html                     # generate + execute + output JSON
ssc-gen run schema.kdl:StructName -i page.html --css-to-xpath      # with CSS→XPath
ssc-gen health schema.kdl:StructName -i page.html                  # check selectors against HTML
ssc-gen health schema.kdl:StructName -i page.html --css-to-xpath   # with CSS→XPath
```

Targets: py-bs4, py-lxml, py-parsel, py-slax, js-pure

`--http-client` option (only for targets that support `@request`):
- Python targets: `httpx` (emits both `fetch()` and `async_fetch()`)
- JS target: `fetch` (default) | `axios`

`--separate-runtime / -R` option: extract helper functions into a separate runtime module (default: `sscgen_runtime`). Use `--runtime-name / -rn` to customize the module name.

---

## Key Architectural Patterns

1. **Visitor pattern**: converters register handlers per AST node type via decorators
2. **Pipeline variable chain**: ConverterContext maintains v0→v1→v2... for each field
3. **Integrated linting**: parsing and linting happen in one pass via `core/`
4. **Extensible converters**: `.extend()` creates child converter inheriting all handlers
5. **Type-tagged containers**: VariableType/StructType enums enforce strict typing at AST level
6. **Recursive nesting**: `Nested` node resolves via struct_map with cycle detection
7. **Transport layer**: `@request` stores raw payload in `RequestConfig`; `converters/request_spec.py` normalises curl/HTTP into `RequestSpec`; converters emit fetch methods per target HTTP client
8. **Runtime separation**: `--separate-runtime` extracts helper functions into a standalone module; generated parsers import from it instead of inlining

---

## Health Check (health.py)

```python
check_struct_health(struct, html, module=None) → HealthResult
```

Verifies selectors match elements in real HTML without code generation.
- Single selectors (css, xpath): fail if 0 matches
- Multi selectors (css-all, xpath-all): fail if 0 matches
- Remove selectors: warn if 0 matches
- Fallback downgrades fail → warn
- Recurses into nested structs (with cycle detection)
