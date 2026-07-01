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
│   ├── module.py          # Module, Docstring (deprecated), Utilities, CodeStartHook, CodeEndHook
│   ├── struct.py          # StructBase, Struct, StructRest, Field, Init, InitFieldCall, InitField, PreValidate, SplitDoc, Key, Value, TableConfig, TableMatchKey, TableRows, CheckMethod, StartParse, MethodBase, MethodFetch, MethodRest, RequestHttp, PlaceholderSpec, ErrorResponse
│   ├── selectors.py       # CssSelect, CssSelectAll, XpathSelect, XpathSelectAll, CssRemove, XpathRemove
│   ├── extract.py         # Text, Raw, Attr
│   ├── string.py          # Trim, Ltrim, Rtrim, NormalizeSpace, RmPrefix, RmSuffix, RmPrefixSuffix, Fmt, Repl, ReplMap, Lower, Upper, Split, Join, Unescape
│   ├── regex.py           # Re, ReAll, ReSub
│   ├── array.py           # Index, Slice, Len, Unique
│   ├── cast.py            # ToInt, ToFloat, ToBool, Jsonify, Nested
│   ├── control.py         # Fallback, Self, Return
│   ├── predicate_containers.py  # Filter, Assert, Match
│   ├── predicate_ops.py   # PredEq/Ne/Gt/Lt/Ge/Le/Range, PredStarts/Ends/Contains/In/Re/ReAny/ReAll, PredCss/Xpath/HasAttr, PredAttr*, PredText*, PredCount*, LogicNot/And/Or
│   ├── typedef.py         # TypeDef, TypeDefField
│   ├── jsondef.py         # JsonDef, JsonDefField
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
│   ├── base.py            # ConverterContext (frozen dataclass: index, depth, prv/nxt, advance/deeper)
│   ├── visitor.py         # Visitor ABC: AST walker, two-pass signals, shared concrete methods (_resolve_type, _pred_line, etc.)
│   ├── helpers.py         # Naming helpers (to_snake_case, to_pascal_case, to_camel_case, jsonify_path_to_segments)
│   ├── request_spec.py    # RequestSpec, parse_to_spec, normalize_placeholder_names
│   ├── py_base.py         # PyHtmlBase(Visitor) — shared Python HTML codegen + REST rendering helpers
│   ├── py_bs4.py          # PyBs4(PyHtmlBase) — BeautifulSoup4
│   ├── py_lxml.py         # PyLxml(PyHtmlBase) — lxml.html
│   ├── py_parsel.py       # PyParsel(PyHtmlBase) — parsel (Scrapy)
│   ├── py_slax.py         # PySlax(PyHtmlBase) — selectolax
│   ├── js_pure.py         # JsPure(Visitor) — JavaScript vanilla DOM
│   └── runtime_file.py    # register_runtime_file, runtime_module_content — `-R` support
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

1. **Visitor pattern**: `Visitor` ABC (converters/visitor.py) — each AST node type maps to a `visit_*` generator method via a dispatch table. Subclasses override methods for target-language spelling.
2. **Two-pass codegen**: `convert_all` runs every `visit_*` twice — pass 1 collects `STD()` / `IMPORT()` signals, pass 2 emits output. visit_* methods must be deterministic.
3. **Pipeline variable chain**: ConverterContext maintains v0→v1→v2... for each field pipeline.
4. **Class-attr dialect config**: Type resolution, predicate formatting, and document types are controlled by plain class attributes (TYPES, ARRAY_TYPE_FMT, AND_OP, etc.) — no spelling hooks or abstract methods for formatting.
5. **Shared concrete methods**: `_resolve_type`, `_resolve_start_parse_t_ret`, `_pred_line` live in Visitor and are inherited by all dialects. Language-agnostic functions (`module_has_rest`, `err_subclass_name`, etc.) are module-level in visitor.py.
6. **Integrated linting**: parsing and linting happen in one pass via `core/`.
7. **Type-tagged containers**: VariableType/StructType enums enforce strict typing at AST level.
8. **Recursive nesting**: `Nested` node resolves via struct_map with cycle detection.
9. **Transport layer**: `@request` stores raw payload in `RequestHttp`; `converters/request_spec.py` normalises curl/HTTP into `RequestSpec`; converters emit fetch methods per target HTTP client.
10. **Runtime separation**: `--separate-runtime` extracts helper functions into a standalone module; generated parsers import from it instead of inlining.

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
