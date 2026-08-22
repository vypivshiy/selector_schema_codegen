# ssc_codegen — Project Reference for LLMs

ssc_codegen is a code generator for web scraping parsers.
Input: .kdl schema files describing HTML extraction rules.
Output: parser code for Python (bs4, lxml, parsel, selectolax), JavaScript (DOM API), and Go (goquery).

Pipeline: .kdl schema → external `kdlquery` parser → core (AST + lint) → visitor → output code

Version: 0.37.1
Python: >=3.10
CLI entry point: `ssc-gen` (ssc_codegen.main:main)

---

## Project Structure

```
ssc_codegen/
├── __init__.py            # re-exports parse_module
├── main.py                # CLI (typer): generate, check, run, health — uses Lang/HtmlLib enums + resolve()
├── _logging.py            # ANSI color logging setup
├── exceptions.py          # ParseError, BuildTimeError
├── regex_utils.py         # Regex flag handling, unverbosify
├── naming.py              # Pure case-conversion helpers (to_pascal_case/to_snake_case/to_camel_case)
├── request_spec.py        # parse_to_http (curl/raw HTTP → RequestHttp AST node), validate_json_body
├── health.py              # Selector health check against real HTML
├── explore.py             # HTML reconnaissance (regex on text/attrs, navigation) — backs `ssc-gen scout`
├── ast/                   # AST node definitions
│   ├── __init__.py        # Re-exports all node types
│   ├── base.py            # Node abstract base class
│   ├── types.py           # VariableType, StructType enums
│   ├── module.py          # Module, Docstring (deprecated), Utilities, CodeStartHook, CodeEndHook
│   ├── struct.py          # StructBase, Struct, StructRest, Field, Init, InitFieldCall, InitField, PreValidate, SplitDoc, Key, Value, TableConfig, TableMatchKey, TableRows, CheckMethod, StartParse, MethodBase, MethodFetch, MethodRest, RequestHttp, Template (tokenized literal/placeholder parts), PlaceholderSpec, ErrorResponse
│   ├── rest.py            # ResultVariantDef, ResultAliasDef, MatcherEntry, MatcherListDef (synthesized REST result-artifact nodes)
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
│   ├── function.py        # module-level fn/(raw)fn AST node
│   └── helpers.py         # AST utilities
├── core/                  # Unified KDL → Module AST reader + integrated linting
│   ├── __init__.py        # Exports parse_module + diagnostic formatting
│   ├── reader.py          # orchestrates kdlquery parse, lint passes, AST build
│   ├── contexts.py        # ParseContext, LintContext, WalkCtx
│   ├── expressions.py     # Pipeline expression parsing, typedef_from_struct
│   ├── rest_artifacts.py  # rest_artifacts_from_struct — synthesizes ResultVariantDef/ResultAliasDef/MatcherListDef from StructRest (mirrors typedef_from_struct); owns err_subclass_name
│   ├── predicates.py      # Predicate expression parsing
│   ├── struct_parser.py   # Struct body parsing
│   ├── module_handler.py  # top-level handlers + import graph resolution
│   ├── linter.py          # structural, symbol, CSS/XPath/regex linting
│   ├── type_checking.py   # Pipeline type inference and mismatch detection
│   └── format.py          # Diagnostic formatting (text + JSON)
├── traversal/             # Shared AST traversal core (language-agnostic)
│   ├── context.py         # WalkContext — immutable context (index, depth, prv/nxt, advance/deeper/reset_index)
│   ├── walker.py          # BaseWalker — dispatch table + walk/walk_children/walk_pipeline (no codegen logic)
│   └── utils.py           # module_has_rest, module_is_rest_only, err_subclass_name, dict_needs_builder, find_predicate_container, dict_entry_placeholder, jsonify_path_to_segments
├── generation/            # Codegen data accumulator + runtime assembly
│   ├── builder.py         # ModuleBuilder — pure data accumulator (imports, std defs). No rendering.
│   └── runtime.py         # register_runtime_file, runtime_module_content, rest_runtime_lines, _BASE_UTILITY_LINES — `-R` support
├── targets/               # Backend-specific code generators
│   ├── __init__.py
│   ├── spec.py            # TargetSpec — raw user input (lang, lib, http_client, separate_runtime)
│   ├── profile.py         # TargetProfile — resolved capabilities + create_converter factory
│   ├── resolver.py        # resolve(TargetSpec) → TargetProfile. Validation + factory dispatch.
│   ├── python/            # Python backend
│   │   ├── __init__.py    # PY_BS4_CONVERTER, PY_LXML_CONVERTER, PY_PARSEL_CONVERTER, PY_SLAX_CONVERTER (pre-built instances)
│   │   ├── visitor.py     # PythonVisitor(BaseWalker) — self-contained, accepts dom_spelling_cls in ctor
│   │   ├── runtime.py     # Python-specific runtime helpers
│   │   ├── html_libs/     # DomSpelling implementations (data + behavior per HTML library)
│   │   │   ├── base.py    # DomSpelling(ABC) — expression methods return list[str], predicate methods return str
│   │   │   ├── bs4.py     # Bs4DomSpelling — BeautifulSoup4
│   │   │   ├── lxml.py    # LxmlDomSpelling — lxml.html
│   │   │   ├── parsel.py  # ParselDomSpelling — parsel (Scrapy)
│   │   │   └── slax.py    # SlaxDomSpelling — selectolax
│   │   └── http_libs/     # HTTP client strategies for REST codegen
│   │       ├── base.py    # HttpLibStrategy(ABC) — import_line, sync/async_client_type, transport_exception, rest_runtime_lines()
│   │       ├── httpx.py   # HttpxStrategy — httpx (sync + async native)
│   │       ├── aiohttp.py # AioHttpStrategy — aiohttp (async-only, sync via asyncio.run + ThreadPoolExecutor fallback)
│   │       └── requests.py# RequestsStrategy — requests (sync-only, async via run_in_executor)
│   └── javascript/        # JavaScript backend
│       ├── __init__.py    # JS_CONVERTER = JsVisitor() (pre-built instance)
│       ├── visitor.py     # JsVisitor(BaseWalker) — vanilla DOM API, self-contained
│       └── http_libs/     # HTTP client strategies for JS
│           ├── base.py    # JsHttpLibStrategy(ABC) — fn_name, rest_call_lines()
│           ├── fetch.py   # FetchStrategy — fetch API
│           └── axios.py   # AxiosStrategy — axios
│   └── golang/            # Go backend (goquery + net/http + gjson)
│       ├── visitor.py     # GoVisitor + gofmt validation + runtime accumulation
│       ├── rest.py        # REST/fetch codegen
│       ├── runtime.py     # shared Go helper definitions
│       └── http_libs/     # net/http strategy
├── parsers/               # HTTP transport parsing (consumed by visitors)
│   ├── curl.py            # parse_curl_command() — POSIX curl → kwargs
│   └── http.py            # parse_http_request() — raw HTTP/1.1|2 → kwargs
tests/
├── integration/
│   ├── test_codegen_run.py     # End-to-end: KDL → generate → execute → verify JSON
│   ├── test_rest_codegen.py    # REST API code generation tests (mocked HTTP)
│   ├── schemas/                # Test .kdl files (00_full through 22_rest_response_path)
│   └── fixtures/               # Test HTML fixtures
├── js/
│   └── test_js_codegen.py      # JS codegen tests (Node.js + jsdom)
├── go/
│   └── test_go_codegen.py      # gofmt/vet/build integration
├── test_parser.py              # KDL parser tests
├── test_imports.py             # Import/include tests
├── test_cli.py                  # CLI output planning and JSON diagnostics
└── test_rest_api.py            # REST/transport layer tests

examples/                       # Real-world .kdl schemas
docs/
├── llm.txt                     # KDL DSL v2.1 syntax reference
└── learn/                      # Tutorial chapters (01-10)
```

---

## CLI Commands

```bash
ssc-gen generate python schema.kdl -L bs4 -o out/                     # generate Python+bs4 parser
ssc-gen generate python schema.kdl -L lxml -o out/                    # Python + lxml
ssc-gen generate python schema.kdl -L parsel -o out/                  # Python + parsel
ssc-gen generate python schema.kdl -L slax -o out/                    # Python + selectolax
ssc-gen generate js schema.kdl -o out/                                # JavaScript (vanilla DOM)
ssc-gen generate go schema.kdl -o out/                                # Go (goquery + net/http)
ssc-gen generate python schema.kdl -L bs4 -o out/ --http-client httpx # with @request support
ssc-gen generate python schema.kdl -L bs4 -o out/ -R                  # separate runtime module
ssc-gen generate python schema.kdl -L bs4 -o out/ -R -rn my_runtime   # custom runtime name
ssc-gen generate python schema.kdl -L bs4 -o out/ --skip-lint         # skip linting
ssc-gen generate python schema.kdl -L bs4 -o out/ --package mymod     # package name for generated code
ssc-gen generate python schema.kdl -L bs4 -o out/ -f json             # JSON output format
ssc-gen check schema.kdl                                              # lint only (text output)
ssc-gen check schema.kdl -f json                                      # lint only (JSON for automation)
ssc-gen run schema.kdl:StructName -i page.html -L bs4                 # generate + execute + output JSON
ssc-gen health schema.kdl:StructName -i page.html -L bs4              # check selectors against HTML
ssc-gen scout -i page.html --text '\$\d+\.\d{2}' -f json              # HTML recon: regex on text/attrs
```

**Commands:**
- `generate python <files>`: Generate Python parser code
- `generate js <files>`: Generate JavaScript parser code
- `generate go <files>`: Generate Go parser code (goquery + net/http)

**Flags:**
- `--lib / -L`: HTML library (Python only) — `bs4` (default) | `lxml` | `parsel` | `slax`
- `--http-client`: HTTP client for `@request` codegen — Python: `httpx` (default) | `aiohttp` | `requests`; JS: `fetch` (default) | `axios`
- `--separate-runtime / -R`: Extract helpers into separate module (default: `sscgen_runtime`)
- `--runtime-name / -rn`: Custom runtime module name
- `--skip-lint`: Skip linting pass
- `--package`: Package/module name; Go defaults to `main`
- `--format / -f`: Output format — `text` | `json`

---

## Key Architectural Patterns

1. **BaseWalker + composition**: `BaseWalker` (traversal/walker.py) — dispatch table maps AST node types to `visit_*` methods via `walk()`. Body traversal split into three modes (container/pipeline/predicate). No codegen logic in BaseWalker.
2. **DomSpelling composition**: `PythonVisitor` accepts `dom_spelling_cls` in constructor. Each DomSpelling subclass (bs4/lxml/parsel/slax) provides HTML-specific expression codegen (returns `list[str]`) and predicate formatting (returns `str`). No subclassing of the visitor needed.
3. **ModuleBuilder**: Pure data accumulator (generation/builder.py) — replaces old hidden signal pools. Stores imports + std-helper definitions. Registration is idempotent. Target-specific code decides rendering format.
4. **Two-pass codegen**: `convert_all` runs `_walk_module` twice — pass 1 collects std/import registrations, pass 2 emits output.
5. **HttpLibStrategy**: REST transport is pluggable per HTTP library. Python: httpx/aiohttp/requests. JS: fetch/axios. Each owns its import line, client types, transport exception, and REST runtime source.
6. **Dynamic resolver**: `resolve(TargetSpec)` → `TargetProfile`. Validates user input, returns capabilities + `create_converter` factory for Python, JavaScript, or Go.
7. **Integrated linting**: parsing and linting happen in one pass via `core/`.
8. **Type-tagged containers**: VariableType/StructType enums enforce strict typing at AST level.
9. **Recursive nesting**: `Nested` node resolves via struct_map with cycle detection.
10. **Transport layer**: `request_spec.parse_to_http` normalises curl/HTTP into `RequestHttp`. String fields are tokenized `PlaceholderTemplate` values; request content lives in `RequestHttp.payload` while inherited `Node.body` remains the AST-child list. JSON templates are parsed structurally before target rendering. Visitors call `with_renamed_placeholders(transform)` for target naming.
11. **Runtime separation**: `--separate-runtime` extracts helper functions into a standalone module; generated parsers import from it instead of inlining.

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

---

## Scout (explore.py)

```python
run_scout(html, filters, nav, fields, *, invert, limit, offset, snippet) → ScoutResult
run_discover(html) → DiscoverResult
```

HTML reconnaissance — regex on text/attribute values (CSS cannot express
this) plus optional CSS intersect and relative navigation (parent/child/
sibling). Auxiliary tool for picking selectors before writing `.kdl`,
or for one-off data extraction. Pure functions, no AST/codegen coupling.

- **Filters** (AND-combine): `--text REGEX`, `--attr NAME[=VAL|=~REGEX]`, `--tag NAME`, `--css SEL`
- **Modifiers**: `-I` ignore-case, `-F` fixed (escape regex), `-v` invert
- **Navigation**: `--up/down/next/prev N` (post-filter, pre-output, deduped by `id(tag)`)
- **Output fields**: `path,tag,text,html,attrs,classes,index,line,attr.NAME` (default `path,tag,text`)
- **Exit codes**: 0 on match, 1 on no match, 2 on error

Reuses bs4+lxml from health.py. `path` field returns copy-pasteable CSS
selector for direct use in `.kdl` schemas.

`run_discover` (v2) — single-call page overview for LLM selector design.
Returns `DiscoverResult` with: `tag_stats`, `class_stats`, `id_stats`,
`data_attrs`, `repeat_containers` (each with `item_selector` anchored
on rare `#id`/class ≤5 occurrences, ≤3 hops; 3 boolean flags
`single_link_item`/`has_th_row`/`single_label_child`; `common_descendants`
with `sample`/`sample_tail` lists), `table_candidates` (`<table>` +
row keys from `<th>` or first `<td>`), `json_signals` (with
`top_level_keys` when body parses as JSON), `page_summary`
(`has_table`, `has_embedded_json`, `container_count_estimate`),
`sample_normalized` global flag (always `true` — samples are
whitespace-collapsed). `selector_stability: "fragile"` emitted only
when item_selector path is unreliable.
