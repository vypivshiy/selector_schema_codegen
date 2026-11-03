# ssc_codegen — Internal Architecture Reference (v0.44.0)

KDL 2.0 Schema DSL v2.1 compiler and parser generator targeting Python (`bs4`, `lxml`, `parsel`, `slax`), JavaScript (DOM API), Go (`goquery` + `net/http` + `gjson`), and Rust (`dom_query` + `serde` + `reqwest`).

- **Pipeline**: `.kdl schema -> kdlquery CST -> 5-pass core (imports + structural lint + cross-ref lint + AST build & type check) -> BaseWalker visitor -> target parser & runtime code`
- **Runtime**: Python `>=3.10` | **CLI Entrypoint**: `ssc-gen` (`ssc_codegen.main:main`)

---

## 1. Repository & Module Map

Format: `path :: exported/key symbols — role`

### Top-Level Package (`ssc_codegen/`)
- `ssc_codegen/__init__.py` :: `parse_module`, `format_diagnostic`, `format_diagnostics`, `ReadDiagnostic`, `ErrorCode`, `Module`, `Struct`, `StructRest`, `Field`, `JsonDef`, `TypeDef`, `VariableType`, `StructType`, `TypeInfo`, `TargetSpec`, `TargetProfile`, `ResolutionError`, `resolve`, `check_struct_health`, `HealthResult`, `SelectorCheck`, `run_scout`, `run_discover`, `ScoutResult`, `DiscoverResult` — Public library facade.
- `ssc_codegen/main.py` :: `app`, `gen_app`, `main`, `cli`, `get_click_app`, `HtmlLib`, `FmtType`, `_run_generate`, `_plan_output_files`, `generate_python`, `generate_js`, `generate_go`, `generate_rust`, `check`, `json_to_kdl_command`, `run`, `health`, `scout`, `version` — Typer CLI (`ssc-gen`).
- `ssc_codegen/json_to_kdl.py` :: `json_to_kdl(value, *, name="JsonResponse") -> str`, `JsonToKdlError` — Bootstraps KDL v2.1 `json` / `(array)json` schemas with inline object/array blocks and `from="..."` aliases from a sample JSON value.
- `ssc_codegen/symbols.py` :: `TARGETS` (`("python", "javascript", "go", "rust")`), `SymbolKind`, `SymbolScope`, `SymbolRecord`, `SymbolFinding`, `normalize_targets`, `target_reserved_words`, `is_valid_symbol`, `target_symbol_plan`, `top_symbol_names`, `local_symbol`, `json_field_symbol` — Cross-target identifier validation (`E403`) and case-folded collision detection (`E402`).
- `ssc_codegen/request_spec.py` :: `parse_to_http(raw_payload) -> RequestHttp`, `validate_json_body(raw_payload) -> str | None`, `parse_json_template(text) -> Any` — Normalizes POSIX `curl` or raw HTTP into `RequestHttp` AST with tokenized `PlaceholderTemplate` fields.
- `ssc_codegen/health.py` :: `check_struct_health(struct, html, module=None) -> HealthResult`, `HealthResult`, `SelectorCheck` — Evaluates CSS/XPath selectors against live HTML without codegen.
- `ssc_codegen/explore.py` :: `run_scout(html, filters=None, *, text=None, attrs=(), tag=None, css=None, ignore_case=False, fixed=False, full=False) -> ScoutResult`, `run_discover(html, *, full=False) -> ScoutResult`, `compile_filters(*, text=None, attrs=(), tag=None, css=None, ignore_case=False, fixed=False) -> ScoutFilters`, `ScoutResult`, `DiscoverResult` (`= ScoutResult`), `ScoutFilters`, `AttrFilter`, `FilterError` — HTML context distillation, 3-engine structural reconnaissance (`embedded_json`, `kv_blocks`, `repeating_lists`), and auto-expanding Zoom-in mode.
- `ssc_codegen/playground_bridge.py` :: `compile_and_lint(kdl_src, target=None) -> dict[str, Any]`, `test_html(kdl_src, html_src, struct_name=None) -> dict[str, Any]` — JSON-serializable Pyodide WebWorker bridge for single-buffer playground validation, multi-target codegen, live HTML parser execution, and selector health checks.
- `ssc_codegen/naming.py` :: `to_pascal_case`, `to_snake_case`, `to_camel_case`, `to_screaming_snake_case` — Pure identifier case converters.
- `ssc_codegen/regex_utils.py` :: `unverbosify_regex`, `extract_inline_flags` — Regex normalization and inline flag extraction across targets.
- `ssc_codegen/exceptions.py` :: `ParseError`, `BuildTimeError` — Compiler exception hierarchy.
- `ssc_codegen/_logging.py` :: `logger`, `setup_debug_logging` — ANSI debug logger.

### AST Package (`ssc_codegen/ast/`)
- `ssc_codegen/ast/__init__.py` :: Re-exports all AST node classes, `VariableType`, `StructType`, `TypeInfo`, `VT`, `Span`.
- `ssc_codegen/ast/base.py` :: `Node(ret_type_info, accept_type_info, parent, body, span)` — Abstract dataclass base for all AST nodes (with deprecated `.ret`, `.accept`, `.type_info` backward-compatibility properties).
- `ssc_codegen/ast/types.py` :: `VariableType` (`VT`), `TypeInfo`, `StructType` — Unified type system and struct kind enums.
- `ssc_codegen/ast/module.py` :: `Module(doc, source_file, extensions, body)`, `Utilities`, `CodeStartHook`, `CodeEndHook`, `Docstring` (deprecated) — Root module container and hooks.
- `ssc_codegen/ast/extension.py` :: `ExtensionType`, `ExtensionImport`, `ExtensionHelper`, `ExtensionTarget`, `ExtensionDef`, `ExtensionCall` — Typed `!Namespace.op` extension definitions and call site node.
- `ssc_codegen/ast/struct.py` :: `StructBase`, `Struct`, `StructRest`, `StructDocstring`, `Field`, `Init`, `InitFieldCall`, `InitField`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `TableConfig`, `TableRows`, `TableMatchKey`, `StartParse`, `MethodBase`, `MethodFetch`, `MethodRest`, `RequestHttp`, `PlaceholderTemplate`, `PlaceholderSpec`, `ErrorResponse` — Structs, directives, and HTTP request AST nodes.
- `ssc_codegen/ast/rest.py` :: `ResultVariantDef`, `ResultAliasDef`, `MatcherEntry`, `MatcherListDef` — Synthesized REST error variant, result union alias, and runtime matcher table AST nodes.
- `ssc_codegen/ast/function.py` :: `FunctionDef(name, is_raw, doc)` — Module-level `fn` and `(raw)fn` pipeline node.
- `ssc_codegen/ast/typedef.py` :: `TypeDef`, `TypeDefField` — Synthesized typed output contract for HTML/raw structs.
- `ssc_codegen/ast/jsondef.py` :: `JsonDef`, `JsonDefField` — Top-level and hoisted `json`, `(array)json`, and `(dict)json` schema nodes.
- `ssc_codegen/ast/selectors.py` :: `CssSelect`, `CssSelectAll`, `XpathSelect`, `XpathSelectAll`, `CssRemove`, `XpathRemove` — DOM query and mutation ops.
- `ssc_codegen/ast/extract.py` :: `Text`, `Raw`, `Attr` — DOM node to string extraction ops.
- `ssc_codegen/ast/string.py` :: `Trim`, `Ltrim`, `Rtrim`, `NormalizeSpace`, `RmPrefix`, `RmSuffix`, `RmPrefixSuffix`, `Fmt`, `Repl`, `ReplMap`, `Lower`, `Upper`, `Split`, `Join`, `Unescape` — String and list-mapped string ops.
- `ssc_codegen/ast/regex.py` :: `Re`, `ReAll`, `ReSub` — Regular expression ops.
- `ssc_codegen/ast/array.py` :: `Index`, `Slice`, `Len`, `Unique` — Array indexing, slicing, length, and deduplication ops (`first`/`last` lower to `Index(0)`/`Index(-1)`).
- `ssc_codegen/ast/cast.py` :: `ToInt`, `ToFloat`, `ToBool`, `Jsonify`, `Nested` — Scalar type conversions and terminal struct/JSON projections.
- `ssc_codegen/ast/control.py` :: `Fallback`, `Self`, `Return` — Error recovery, `@init` reference (`@name`), and terminal return wrapper.
- `ssc_codegen/ast/predicate_containers.py` :: `Filter`, `Assert`, `Match` — Predicate block containers.
- `ssc_codegen/ast/predicate_ops.py` :: `PredEq`, `PredNe`, `PredStarts`, `PredEnds`, `PredContains`, `PredRe`, `PredReAny`, `PredReAll`, `PredCss`, `PredXpath`, `PredHasAttr`, `PredAttrEq`, `PredAttrNe`, `PredAttrStarts`, `PredAttrEnds`, `PredAttrContains`, `PredAttrRe`, `PredTextStarts`, `PredTextEnds`, `PredTextContains`, `PredTextRe`, `PredCountEq`, `PredCountNe`, `PredCountGt`, `PredCountLt`, `PredCountGe`, `PredCountLe`, `PredCountRange`, `LogicNot`, `LogicAnd`, `LogicOr` — Condition and boolean combinator nodes (`in` lowers to `PredEq`, `gt/lt/ge/le` lower to `PredCount*`).
- `ssc_codegen/ast/helpers.py` :: AST inspection helpers.

### Compiler Core (`ssc_codegen/core/`)
- `ssc_codegen/core/__init__.py` :: `parse_module`, `format_diagnostic`, `format_diagnostics`, `ReadDiagnostic`, `Severity`, `Span`, `Position`, `ErrorCode` — Core package exports.
- `ssc_codegen/core/reader.py` :: `parse_module(src, source_path=None, *, targets=None, skip_lint=False) -> tuple[Module, list[ReadDiagnostic]]` — 5-pass compiler orchestrator and `Module.body` assembler.
- `ssc_codegen/core/contexts.py` :: `WalkCtx`, `ErrorCode`, `DefineKind`, `DefineInfo`, `ParseContext`, `LintContext` — Compiler state, scope tracking, and diagnostic emission.
- `ssc_codegen/core/imports.py` :: `SymbolId(path, kind, name)`, `SourceUnit`, `resolve_imports` — Mandatory typed imports, private per-file scopes, cycle detection, and topological dependency closure.
- `ssc_codegen/core/linter.py` :: `lint_module`, `lint_cross_refs`, `lint_pipeline_op`, `lint_predicate_op`, `lint_validate_regex`, `lint_validate_css`, `lint_validate_xpath` — CST structural, semantic, selector, regex, and cross-ref linter rules.
- `ssc_codegen/core/type_checking.py` :: `OpSig`, `OP_TYPES`, `check_pipeline_types`, `infer_pipeline_type` — Pipeline type inference and compatibility validator.
- `ssc_codegen/core/expressions.py` :: `parse_expression_body`, `typedef_from_struct` — Pipeline operation parser (with central `E001`/`E100` guards) and `TypeDef` synthesizer.
- `ssc_codegen/core/predicates.py` :: `parse_predicate_body` — Predicate container and combinator parser.
- `ssc_codegen/core/struct_parser.py` :: `parse_struct_body`, `parse_json_fields` — Struct directives, fields, inline JSON schema hoisting, and block `define` expansion.
- `ssc_codegen/core/module_handler.py` :: `handle_define`, `handle_json`, `handle_struct`, `handle_function`, `register_node_sources` — Top-level KDL node handlers.
- `ssc_codegen/core/extensions.py` :: `handle_extension`, `lint_extension_node`, `resolve_extension_sig` — `extension` block parser and generic `T` type binder.
- `ssc_codegen/core/rest_artifacts.py` :: `rest_artifacts_from_struct`, `err_subclass_name` — Synthesizes `ResultVariantDef`, `ResultAliasDef`, and `MatcherListDef` from `StructRest`.
- `ssc_codegen/core/format.py` :: `format_diagnostic`, `format_diagnostics` — Rust-style text and JSON diagnostic formatter.

### Traversal, Generation, Parsers & Targets (`ssc_codegen/`)
- `ssc_codegen/traversal/context.py` :: `WalkContext` — Immutable traversal state (`index`, `depth`, `var_name`, `indent_char`, `meta`, `.prv`, `.nxt`, `.indent`).
- `ssc_codegen/traversal/walker.py` :: `BaseWalker` — Dispatch table (`_DISPATCH`) and 3-mode body traversal (`walk`, `walk_children`, `walk_pipeline`, `walk_predicates`).
- `ssc_codegen/traversal/utils.py` :: `module_has_rest`, `module_has_fetch`, `module_uses_http`, `module_has_html_struct`, `module_is_extension_only`, `err_subclass_name`, `find_predicate_container`, `find_enclosing_module`, `resolve_json_def`, `parse_gjson_path`, `is_malformed_gjson_path`, `classify_gjson_path` — Shared cross-backend helpers and GJSON path parser.
- `ssc_codegen/generation/builder.py` :: `ModuleBuilder` — Idempotent accumulator for `require_import`, `require_std`, `require_runtime`.
- `ssc_codegen/generation/runtime.py` :: `register_runtime_file`, `runtime_module_content`, `_BASE_UTILITY_LINES` — Standalone Python runtime module (`-R`) assembler.
- `ssc_codegen/parsers/curl.py` :: `parse_curl_command` — Low-level POSIX `curl` command parser.
- `ssc_codegen/parsers/http.py` :: `parse_http_request` — Low-level raw HTTP/1.1|2 request parser.
- `ssc_codegen/targets/spec.py` :: `TargetSpec(lang, lib, http_client, separate_runtime, bs4_parser, http_io)` — Raw user target configuration.
- `ssc_codegen/targets/profile.py` :: `TargetProfile(language, file_extension, create_converter, http_clients, supports_separate_runtime, runtime_include_fallback)` — Validated capability descriptor and converter factory.
- `ssc_codegen/targets/resolver.py` :: `resolve(spec) -> TargetProfile`, `ResolutionError` — Target capability validation and converter factory resolution.
- `ssc_codegen/targets/python/` :: `PythonVisitor` (`visitor.py`), `rest.py`, `html_libs/` (`DomSpelling`, `Bs4DomSpelling`, `LxmlDomSpelling`, `ParselDomSpelling`, `SlaxDomSpelling`), `http_libs/` (`HttpLibStrategy`, `HttpxStrategy`, `Httpx2Strategy`, `AioHttpStrategy`, `RequestsStrategy`), pre-built `PY_BS4_CONVERTER`, `PY_LXML_CONVERTER`, `PY_PARSEL_CONVERTER`, `PY_SLAX_CONVERTER` (`__init__.py`).
- `ssc_codegen/targets/javascript/` :: `JsVisitor` (`visitor.py`), `rest.py`, `http_libs/` (`JsHttpLibStrategy`, `FetchStrategy`, `AxiosStrategy`), pre-built `JS_CONVERTER` (`__init__.py`).
- `ssc_codegen/targets/golang/` :: `GoVisitor`, `validate_go_package_name` (`visitor.py`), `rest.py`, `runtime.py`, `literals.py` (`go_str`, `go_literal`, `go_str_array`, `go_str_map`), `regex.py` (`py_re_to_go_raw`), `http_libs/` (`NetHttpStrategy`), pre-built `GO_CONVERTER` (`__init__.py`).
- `ssc_codegen/targets/rust/` :: `RustVisitor` (`visitor.py`), `rest.py`, `runtime.py` (`sscgen_runtime.rs` emitter), `regex.py` (Rust regex compatibility checker), `http_libs/` (`ReqwestStrategy`), pre-built `RUST_CONVERTER` (`__init__.py`).

### Tests, Playground & Documentation (`tests/`, `playground/`, `docs/`)
- `tests/` :: `test_parser.py`, `test_imports.py`, `test_symbols.py`, `test_extensions.py`, `test_fn.py`, `test_raw_struct.py`, `test_json_projection.py`, `test_json_to_kdl.py`, `test_rest_api.py`, `test_http_io.py`, `test_bs4_parser.py`, `test_assert.py`, `test_re_search.py`, `test_explore.py`, `test_playground_bridge.py`, `test_cli.py`, `test_resolver.py`, `test_builder.py`, `test_codegen_safety.py`, `test_fuzz_expressions.py`, `test_llm_docs.py`, `integration/` (`test_codegen_run.py`, `test_rest_codegen.py`, `schemas/`, `fixtures/`), `js/` (`test_js_codegen.py`), `go/` (`test_go_codegen.py`), `rust/` (Rust cargo/codegen tests) — Unit, property, and cross-target integration test suite.
- `playground/` :: `src/` (`App.tsx`, `types.ts`, `presets.ts`, `presets.json`, `urlState.ts`, `hooks/useCopyFeedback.ts`, `editor/`, `worker/`, `components/`, `__tests__/`) — Vite + React + TypeScript + Monaco + Pyodide single-page Web Playground.
- `docs/` :: `llm.txt` (external KDL Schema DSL v2.1 reference), `README.md`, `guide.md`, `syntax.md`, `types.md`, `operations.md`, `predicates.md`, `json.md`, `extensions.md`, `learn/` (user tutorials), `adr/` (Architecture Decision Records), `api/` (Griffe API reference), `agents/` (`issue-tracker.md`, `triage-labels.md`, `domain.md`), `wayfinder/` (`map.md`) — Documentation site, ADRs, and agent workflow guides.

---

## 2. CLI Command & Flag Matrix

### Subcommands (`ssc-gen`)

| Command | Signature | Purpose |
|---|---|---|
| `generate python` | `ssc-gen generate python <files...> [-o DIR] [-L bs4\|lxml\|parsel\|slax] [--bs4-parser lxml\|html.parser\|html5lib] [--http-client httpx\|httpx2\|aiohttp\|requests] [--http-io both\|sync\|async] [-R] [-rn NAME] [--package NAME] [--skip-lint] [-f text\|json] [-v]` | Compile `.kdl` schemas to Python parsers |
| `generate js` | `ssc-gen generate js <files...> [-o DIR] [--http-client fetch\|axios] [--package NAME] [--skip-lint] [-f text\|json] [-v]` | Compile `.kdl` schemas to JavaScript (ESM + JSDoc) parsers |
| `generate go` | `ssc-gen generate go <files...> [-o DIR] [--package NAME] [--skip-lint] [-f text\|json] [-v]` | Compile `.kdl` schemas to Go (`goquery` + `net/http` + `gjson`) + `sscgen_runtime.go` |
| `generate rust` | `ssc-gen generate rust <files...> [-o DIR] [--http-client reqwest] [--skip-lint] [-f text\|json] [-v]` | Compile `.kdl` schemas to Rust (`dom_query` + `serde` + `reqwest`) + `sscgen_runtime.rs` |
| `check` | `ssc-gen check <files...> [-t/--target python\|javascript\|go\|rust] [-f text\|json] [-v]` | Lint & type-check schemas (plus cross-target or single-target symbol validation) |
| `run` | `ssc-gen run <path.kdl:StructName> [-i FILE] [-L bs4\|lxml\|parsel\|slax] [--bs4-parser lxml\|html.parser\|html5lib] [-f text\|json] [-v]` | Generate Python parser in-memory, run against HTML file/stdin, print JSON |
| `health` | `ssc-gen health <path.kdl:StructName> [-i FILE] [-f text\|json] [-v]` | Check selector match counts against real HTML without codegen |
| `scout` | `ssc-gen scout [-i FILE] [--text REGEX] [--attr SPEC...] [--tag TAG] [--css SEL] [-I/--ignore-case] [-F/--fixed] [--full] [--discover] [-f text\|json]` | HTML reconnaissance: full-page 3-engine structural overview by default, or auto-expanding Zoom-in mode with `<-- MATCH` highlights when filters are set |
| `json-to-kdl` | `ssc-gen json-to-kdl <input.json> -o <output.kdl> [--name JsonResponse] [--force]` | Bootstrap inline KDL `json` schema from sample JSON payload |
| `version` | `ssc-gen version` | Print `ssc_codegen` package version |

### Key Options

| Flag | Scope | Values / Default | Behavior |
|---|---|---|---|
| `-L, --lib` | `generate python`, `run` | `bs4` (default), `lxml`, `parsel`, `slax` | Selects Python `DomSpelling` implementation |
| `--bs4-parser` | `generate python` (`-L bs4`), `run` | `lxml` (default), `html.parser`, `html5lib` | Sets `BS4_FEATURES` parser engine passed to `BeautifulSoup(doc, BS4_FEATURES)` |
| `--http-client` | `generate python\|js\|rust` | Python: `httpx` (default), `httpx2`, `aiohttp`, `requests`; JS: `fetch` (default), `axios`; Rust: `reqwest` (default) | Selects HTTP transport strategy (`Go` uses `net/http` exclusively) |
| `--http-io` | `generate python` | `both` (default), `sync`, `async` | Emits sync, async, or both HTTP method pairs (`aiohttp` rejects `sync`) |
| `-R, --separate-runtime` | `generate python` | `bool` (`False`) | Extracts runtime helpers into `<runtime_name>.py` (`Go` and `Rust` always emit `sscgen_runtime.go` / `sscgen_runtime.rs`) |
| `-rn, --runtime-name` | `generate python -R` | `sscgen_runtime` (default) | Module name for standalone Python runtime file |
| `--package` | `generate python\|js\|go` | `None` (`main` for Go) | Package/namespace identifier for generated files |
| `-t, --target` | `check` | `python`, `javascript` (`js`), `go`, `rust` (repeatable; default: all 4) | Restricts `E402`/`E403` symbol validation to selected target languages |
| `--full` | `scout` | `bool` (`False`) | Disables default compression caps on discovered repeating lists, fields, KV blocks, and JSON collections |
| `--discover` | `scout` | `bool` (`False`) | Deprecated hidden no-op alias (overview mode runs by default when no filter flags are set) |
| `-f, --format` | All commands | `text` (default), `json` | Selects human-readable text or structured JSON output |

---

## 3. Compiler Core, Linter & `kdlquery` Selector Reference

### 3.1 5-Pass Execution Model (`core/reader.py:parse_module`)

`parse_module(src: str, source_path: Path | str | None = None, *, targets: Sequence[str] | None = None, skip_lint: bool = False) -> tuple[Module, list[ReadDiagnostic]]`

1. **Pass 1 — KDL Parse**: `kdlquery.parse(src)` -> mutable `KdlDocument` / `KdlNode` CST with `Span`. Syntax errors return immediately as `ErrorCode.SYNTAX_ERROR` (`E000`).
2. **Pass 2 — Import Resolution (`core/imports.py:resolve_imports`)**: Parses mandatory typed `import "./x.kdl" { (kind)Name }` blocks (`kind` in `define | extension | fn | json | struct`). Tracks symbols via `SymbolId(path, kind, name)` in private per-file scopes, diagnoses cycles/missing symbols (`E003`/`E300`), and prepends the topologically sorted private dependency closure ahead of local declarations.
3. **Pass 3 — Structural Lint (`core/linter.py:lint_module`)**: Validates top-level nodes, struct bodies, required directives (`E401`), disallowed directives (`E203`), argument counts/values (`E001`/`E002`), CSS/XPath/regex syntax, JSON dot-paths (`E040`/`E041`/`W011`/`W040`/`W041`), `@request` placeholders, and **Top-Down Local Declaration Order** (`E302`).
4. **Pass 4 — Cross-Reference & Target Symbol Lint (`core/linter.py:lint_cross_refs` + `symbols.py`)**: Validates references to `define`, `json`, `struct`, `extension`, and `@init` fields (`E300`/`E301`), detects recursive struct/json cycles, and checks target identifier validity (`E403`) and case-folded collisions (`E402`) across `targets` (defaults to all 4 targets: Python, JavaScript, Go, Rust). Fatal structural diagnostics halt before Pass 5.
5. **Pass 5 — AST Build & Pipeline Type Checking**: Executes `handle_define` / `handle_extension` -> `handle_json` (with recursive compiler hoisting of inline JSON and `@value` schemas in post-order into `ctx.json_defs`) -> `handle_struct` (synthesizing `TypeDef` via `typedef_from_struct` and REST artifacts `ResultVariantDef` / `ResultAliasDef` / `MatcherListDef` via `rest_artifacts_from_struct`) -> `handle_function`. Runs `check_pipeline_types` (`E100`) per pipeline.

**`Module.body` Assembly Invariant**: Handlers never append `json` or `struct` nodes directly to `module.body` during iteration; `parse_module` performs a single final extend in strict order:
`json_defs -> typedefs -> REST artifacts & structs -> functions`

```kdl
define TRIM-TEXT { text; trim }

json PriceTag {
    amount float
    currency str from="curr_code"
}

struct ProductCard {
    title { css "h2.title"; TRIM-TEXT }
    pricing { css "script.price-json"; text; jsonify PriceTag }
}

fn extract_heading { css "h1"; TRIM-TEXT }
```

### 3.2 Dual Type-Resolution Invariant

- **Top-Down Declaration Order (Intra-file)**: Within a single `.kdl` file, referenced `struct` and `json` declarations must appear strictly **above** any `struct`, `json`, or `fn` that references them (`E302` `INVALID_DECLARATION_ORDER`).
- **Topological Dependency Closure (Inter-file)**: Across `import` boundaries, `core/imports.py` builds a directed symbol dependency graph keyed by `SymbolId(path, kind, name)` and topologically sorts imported symbols plus their transitive private dependencies before AST construction. Diamond imports deduplicate by `SymbolId`.

### 3.3 `kdlquery` CST API & CSS3 Selector Cheat-Sheet

- **CST API**: `from kdlquery import parse, KdlDocument, KdlNode, ReadDiagnostic, Severity` and `from kdlquery.types import Span, Position`.
- **Navigation & Query Methods**: `doc.select(q)`, `doc.select_one(q)`, `node.select(q)` (descendants only), `node.select_one(q)`, `node.matches(q)`, `node.closest(q)`, `node.parent`, `node.root`, `node.depth()`, `node.index()`, `node.siblings()`, `node.parents()`.

| Category | Selector Syntax | Semantics |
|---|---|---|
| **Node & Tag** | `name`, `*`, `(type)`, `(type)name` | Match by node name, wildcard, KDL type annotation, or both |
| **Properties** | `[key]`, `[key=val]`, `[key^=val]`, `[key$=val]`, `[key~=val]`, `[(type)key=val]` | Property presence, exact, prefix, suffix, substring, or typed property match |
| **Positional Args** | `[N]`, `[N=val]`, `[N^=val]`, `[N$=val]`, `[N~=val]`, `[(type)N]`, `[*=val]` | Argument at 0-based index `N` (or any positional arg `*`) match |
| **Combinators** | `A B`, `A > B`, `A + B`, `A ~ B`, `A, B` | Descendant, direct child, adjacent sibling, general sibling, deduplicated union |
| **Pseudo-classes** | `:root`, `:first-child`, `:last-child`, `:nth-child(an+b)`, `:only-child`, `:empty`, `:not(compound)`, `:has(complex)`, `:has(> complex)` | `:root` matches top-level `KdlDocument` nodes only (never matches on `KdlNode.select()`) |

### 3.4 `ErrorCode` Summary Table (`core/contexts.py` & `core/linter.py`)

| Code | `ErrorCode` Member | Severity | Summary |
|---|---|---|---|
| `E000` | `SYNTAX_ERROR` | ERROR | KDL 2.0 syntax parse error or unhandled build exception |
| `E001` | `INVALID_ARGUMENT_COUNT` | ERROR | Wrong number of positional arguments, empty block, or inline schema name collision |
| `E002` | `INVALID_ARGUMENT_VALUE` | ERROR | Invalid argument value/type, malformed regex/CSS/XPath, invalid HTTP status, or invalid `@error:<suffix>` |
| `E003` | `INVALID_IMPORT` | ERROR | Missing import block/kind annotation, missing file, cyclic import, or duplicate import |
| `E040` | `MALFORMED_DOTPATH` | ERROR | Malformed GJSON dot-path in `from=`/`path=`/`jsonify` (leading/trailing dot, `..`, invalid filter) |
| `E041` | `DUPLICATE_JSON_KEY` | ERROR | Duplicate JSON field name or duplicate source key in `json` schema |
| `E100` | `TYPE_MISMATCH` | ERROR | Pipeline input/output type mismatch, missing preceding op, or incompatible `fallback` type |
| `E200` | `UNKNOWN_NODE` | ERROR | Unknown top-level declaration, pipeline operation, or predicate |
| `E203` | `DISALLOWED_DIRECTIVE` | ERROR | Directive or HTML op used in forbidden context (e.g., HTML op in `(raw)struct`, `@init` in `fn`, field in `(rest)struct`) |
| `E300` | `UNDEFINED_SYMBOL` | ERROR | Reference to undeclared `struct`, `json`, `define`, or `extension` |
| `E301` | `UNDEFINED_INIT_FIELD` | ERROR | `@name` (`Self`) references an undeclared `@init` field |
| `E302` | `INVALID_DECLARATION_ORDER` | ERROR | Local `struct` or `json` referenced before its declaration in the same file |
| `E400` | `INVALID_TYPE_DECLARATION` | ERROR | Invalid struct/json type, invalid `extension` signature, duplicate `@error` variant name, or duplicate key in `@error` args+props |
| `E401` | `MISSING_REQUIRED_FIELD` | ERROR | Struct missing required directives (`@split-doc`, `@key`, `@value`, `@table`, `@rows`, `@match`, `@request`) |
| `E402` | `DUPLICATE_DECLARATION` | ERROR | Duplicate symbol declaration or case-folded target identifier collision |
| `E403` | `INVALID_IDENTIFIER` | ERROR | Symbol name cannot form a valid identifier or collides with a reserved keyword in target language |
| `W011` | `DEPRECATED_JSON_ALIAS` | WARNING | Deprecated positional JSON key alias (`field str "wire_key"`); use `from="wire_key"` |
| `W040` | `WHITESPACE_IN_PATH` | WARNING | Leading or trailing whitespace in `from="..."` path |
| `W041` | *(literal `"W041"` in `linter.py`)* | WARNING | `path="..."` used on a `json` field instead of canonical `from="..."` |

---

## 4. Type System & AST Node Catalog

### 4.1 `VariableType`, `TypeInfo` & `StructType` (`ast/types.py`)

- **`VariableType(IntEnum)` (`VT`)**: `AUTO` (internal inference), `DOCUMENT`, `STRING`, `INT` (64-bit signed), `FLOAT` (64-bit IEEE 754), `BOOL`, `NULL`, `NESTED` (terminal), `JSON` (terminal).
- **`TypeInfo` (frozen dataclass)**:

| Field / Property | Type | Meaning |
|---|---|---|
| `base` | `VariableType` | Scalar base type (`DOCUMENT`, `STRING`, `INT`, `FLOAT`, `BOOL`, `NULL`, `NESTED`, `JSON`, `AUTO`) |
| `is_array` / `.is_list` | `bool` | List/array modifier (`False` default) |
| `is_optional` | `bool` | Nullable/optional modifier (set by `?` suffix or `fallback #null`) |
| `ref` / `.is_ref` | `str \| None` / `bool` | Target `Struct` or `JsonDef` name (`is_ref` is `True` when `base in (NESTED, JSON)` and `ref is not None`) |
| `omitempty` | `bool` | `@omitempty` — key may be absent from JSON wire object |
| `skip` | `bool` | `@skip` — field is parsed/ignored and excluded from projected output |
| `is_dict` | `bool` | Dictionary container modifier (`(dict)json` or inline `(dict)` JSON field) |
| `key_type_info` | `TypeInfo \| None` | Dictionary key type (defaults to `STRING`) |
| `value_type_info` | `TypeInfo \| None` | Dictionary value type (`TypeInfo` for scalar, array, or referenced `JsonDef`) |

- **`StructType(IntEnum)`**:
  - `ITEM`: single object extraction -> struct/dict (`parse() -> <Name>Type`).
  - `LIST`: repeating elements -> `list[<Name>Item]`; requires `@split-doc`.
  - `DICT`: key-value map -> `dict[str, V]`; requires `@split-doc`, `@key`, `@value`.
  - `TABLE`: HTML table -> `dict`; requires `@table`, `@rows`, `@match`, `@value`.
  - `FLAT`: deduplicated string list -> `list[str]`.
  - `REST`: HTTP/JSON API client (`StructRest`); requires `@request`, optional `@error[:<suffix>]`.
  - `RAW`: plain-text (`STRING`-input) struct (`(raw)struct`, `Struct.type == StructType.RAW`); forbids DOM operations.

### 4.2 Complete AST Node Catalog (`ssc_codegen/ast/`)

All AST nodes inherit `Node(ret_type_info: TypeInfo, accept_type_info: TypeInfo, parent: Node | None, body: list[Any], span: Span | None)` (note `.accept`, `.ret`, and `.type_info` are deprecated backward-compatibility properties; `description` does not exist on `Node`).

| Layer | AST Node Class | Key Fields & Contract |
|---|---|---|
| **Module** | `Module` | `doc: str = ""`, `source_file: str = ""`, `extensions: dict[str, ExtensionDef]` (inherits `body: list[Node]`; properties `.utilities`, `.code_start`, deprecated `.docstring`) |
| | `Utilities`, `CodeStartHook`, `CodeEndHook`, `Docstring` | Hook/marker nodes in `Module.body` (`Docstring(value: str = "")` is deprecated; module docstring lives in `Module.doc`) |
| **Extension** | `ExtensionDef` | `namespace: str`, `name: str`, `accept: ExtensionType`, `ret: ExtensionType`, `targets: dict[str, ExtensionTarget]` (property `.qualified_name -> str`, method `resolve_return(input_type)`) |
| | `ExtensionType` | `base: VariableType \| None = None`, `generic: str \| None = None`, `is_array: bool = False`, `is_optional: bool = False` (`generic="T"` binds full input `TypeInfo`) |
| | `ExtensionTarget` | `language: Literal["py", "js", "go"] \| str`, `emit: str`, `imports: tuple[ExtensionImport, ...] = ()`, `helpers: tuple[ExtensionHelper, ...] = ()` |
| | `ExtensionImport`, `ExtensionHelper` | `ExtensionImport(value: str, alias: str = "")` / `ExtensionHelper(name: str, source: str, imports: tuple[ExtensionImport, ...] = ())` |
| | `ExtensionCall` | `qualified_name: str = ""` (`Namespace.op`), `definition: ExtensionDef \| None = None` (inherits `accept_type_info`, `ret_type_info` from `Node`) |
| **Struct & Function** | `StructBase` | `type: StructType = StructType.ITEM`, `name: str = ""`, `keep_order: bool = False`, `doc: str = ""` (properties `.request_config`, `.request_configs`, `.use_request`, `.errors`, deprecated `.docstring`) |
| | `Struct(StructBase)` | `type: StructType = StructType.ITEM` (`StructType.RAW` for `(raw)struct`; property `.init -> Init`) |
| | `StructRest(StructBase)` | `type: StructType = StructType.REST` — `(rest)struct` HTTP/JSON API client container (inherits `.errors -> list[ErrorResponse]`) |
| | `FunctionDef` | `name: str = ""`, `is_raw: bool = False`, `doc: str = ""` — module-level `fn` (`DOCUMENT` input) or `(raw)fn` (`STRING` input) |
| | `Field` | `name: str = ""` (inherits `ret_type_info: TypeInfo`, `accept_type_info: TypeInfo`, `body: list[Node]` from `Node`; property `.struct -> Struct`) |
| | `Init`, `InitFieldCall`, `InitField` | `Init()` (`@init` container), `InitFieldCall(name: str = "")` (constructor call marker), `InitField(name: str = "")` (cached method pipeline, inherits `accept_type_info`, `ret_type_info`, `body`) |
| | `PreValidate`, `CheckMethod` | `PreValidate()` (`@pre-validate` assert block) and `CheckMethod(name: str = "")` (`@check <name>` boolean method ending in `to-bool`) |
| | `SplitDoc`, `Key`, `Value` | `@split-doc`, `@key`, `@value` directive pipelines (inherit `accept_type_info`, `ret_type_info`, `body`) |
| | `TableConfig`, `TableRows`, `TableMatchKey` | `@table`, `@rows`, `@match` directive pipelines for `StructType.TABLE` (inherit `accept_type_info`, `ret_type_info`, `body`) |
| | `StartParse`, `StructDocstring` | `StartParse()` (entrypoint dispatch marker; properties `.struct`, `.use_split_doc`, `.use_pre_validate`, `.fields`) and `StructDocstring(value: str = "")` (deprecated) |
| **REST & Transport** | `MethodBase` | `name: str = ""`, `doc: str = ""`, `response_path: str = ""`, `response_join: str = ""` (properties `.http_request -> RequestHttp`, `.placeholders -> list[PlaceholderSpec]`) |
| | `MethodFetch(MethodBase)` | HTML/raw `@request` fetch method (inherits `name`, `doc`, `response_path`, `response_join`, `.http_request`, `.placeholders`) |
| | `MethodRest(MethodBase)` | `doc: str = ""`, `response_schema: str = ""`, `result_alias_name: str = ""` (plus inherited `name`, `response_path`, `response_join`) — REST endpoint method |
| | `RequestHttp` | `method: str = "GET"`, `url: PlaceholderTemplate`, `headers: dict[str, PlaceholderTemplate]`, `cookies: dict[str, PlaceholderTemplate]`, `params: dict[str, PlaceholderTemplate]`, `body_kind: str = "empty"`, `payload: PlaceholderTemplate \| dict[str, PlaceholderTemplate] \| None = None` (property `.placeholders -> list[PlaceholderSpec]`) |
| | `PlaceholderTemplate`, `PlaceholderSpec` | `PlaceholderTemplate(parts: list[str \| PlaceholderSpec])` / `PlaceholderSpec(name: str = "", type_name: Literal["str", "int", "float", "bool"] = "str", is_array: bool = False, is_optional: bool = False, style: Literal["repeat", "csv", "bracket", "pipe", "space"] \| None = None)` |
| | `ErrorResponse` | `status: int = 0`, `schema_name: str = ""`, `required_keys: list[str]`, `conditions: dict[str, Any]`, `suffix: str = ""` (`@error:<suffix>`) |
| | `ResultVariantDef` | `name: str = ""`, `status: int = 0`, `schema_name: str = ""`, `schema_is_array: bool = False` |
| | `ResultAliasDef` | `name: str = ""`, `response_schema: str = ""`, `response_is_array: bool = False`, `err_variants: list[str]` |
| | `MatcherEntry`, `MatcherListDef` | `MatcherEntry(status: int, required_keys: list[str], conditions: dict[str, Any], factory_name: str, error_schema: str = "")` / `MatcherListDef(struct_name: str = "", entries: list[MatcherEntry])` |
| **Pipeline Ops** | `CssSelect`, `CssSelectAll`, `XpathSelect`, `XpathSelectAll`, `CssRemove`, `XpathRemove` | `queries: list[str]` (plus deprecated `.query -> str` property) on `*Select*` (fallback block when `len(queries) >= 2`); `query: str = ""` on `*Remove` |
| | `Text`, `Raw`, `Attr` | `Text()`, `Raw(mode: str = "outer")` (`"outer" \| "inner"`), `Attr(keys: tuple[str, ...])` |
| | `Trim`, `Ltrim`, `Rtrim`, `NormalizeSpace`, `RmPrefix`, `RmSuffix`, `RmPrefixSuffix`, `Fmt`, `Repl`, `ReplMap`, `Lower`, `Upper`, `Split`, `Join`, `Unescape` | `substr: str = ""` (`Trim`/`Ltrim`/`Rtrim`/`Rm*`), `template: str = ""` (`Fmt`), `old: str = ""`, `new: str = ""` (`Repl`), `replacements: dict[str, str]` (`ReplMap`), `sep: str = ""` (`Split`/`Join`) |
| | `Re`, `ReAll`, `ReSub` | `Re(pattern: str = "")`, `ReAll(pattern: str = "")`, `ReSub(pattern: str = "", repl: str = "")` |
| | `Index`, `Slice`, `Len`, `Unique` | `Index(i: int = 0)`, `Slice(start: int = 0, end: int = 0)`, `Len()`, `Unique(keep_order: bool = False)` |
| | `ToInt`, `ToFloat`, `ToBool`, `Jsonify`, `Nested` | `ToInt()`, `ToFloat()`, `ToBool()`, `Jsonify(schema_name: str = "", path: str \| None = None)`, `Nested(struct_name: str = "")` |
| | `Fallback`, `Self`, `Return` | `Fallback(value: Any = None)`, `Self(name: str = "")` (`@name`), `Return()` (inherits `accept_type_info`, `ret_type_info` from `Node`) |
| **Predicates** | `Filter`, `Assert`, `Match` | Containers (`Assert(message: str = "")`, `Filter()`, `Match()`; `body: list[Node]`) |
| | `PredEq`, `PredNe`, `PredStarts`, `PredEnds`, `PredContains`, `PredRe`, `PredReAny`, `PredReAll`, `PredCss`, `PredXpath`, `PredHasAttr`, `PredAttrEq`, `PredAttrNe`, `PredAttrStarts`, `PredAttrEnds`, `PredAttrContains`, `PredAttrRe`, `PredTextStarts`, `PredTextEnds`, `PredTextContains`, `PredTextRe`, `PredCountEq`, `PredCountNe`, `PredCountGt`, `PredCountLt`, `PredCountGe`, `PredCountLe`, `PredCountRange`, `LogicNot`, `LogicAnd`, `LogicOr` | `values: tuple[str \| int, ...]` (`PredEq`/`PredNe`), `values: tuple[str, ...]`, `pattern: str = ""`, `attrs: tuple[str, ...]` (`PredHasAttr`), `name: str = ""` (`PredAttr*`), `query: str = ""` (`PredCss`/`PredXpath`), `value: int = 0` (`PredCount*`), `start: int = 0`, `end: int = 0` (`PredCountRange`) |
| **Type & JSON Defs** | `TypeDef`, `TypeDefField` | `TypeDef(name: str = "", struct_type: StructType = StructType.ITEM)` (property `.fields -> list[TypeDefField]` wrapping `body`; `ret_type_info` from `Node`) / `TypeDefField(name: str = "")` (inherits `ret_type_info: TypeInfo`; property `.typedef -> TypeDef`) |
| | `JsonDef`, `JsonDefField` | `JsonDef(name: str = "", is_array: bool = False, is_dict: bool = False, path: str = "", key_type_info: TypeInfo \| None = None, value_type_info: TypeInfo \| None = None)` (`body` holds `JsonDefField` children) / `JsonDefField(name: str = "", type_name: str = "", alias: str = "", doc: str = "", is_dict: bool = False, key_type_info: TypeInfo \| None = None, value_type_info: TypeInfo \| None = None)` (inherits `ret_type_info: TypeInfo`) |

---

## 5. Codegen Architecture & Target Backends

### 5.1 `BaseWalker`, `WalkContext` & `ModuleBuilder` Two-Pass Codegen

- **`BaseWalker` (`traversal/walker.py`)**: Dispatches AST node classes via `_DISPATCH` to `visit_<node>(self, node, ctx) -> list[str] | str | None` (`""` emits a blank line). Three body traversal modes:
  1. **Container (`walk_children`)**: `depth + 1`, `index = 0`, no index advance between children (`JsonDef`, `TypeDef`, `StructBase`, `Init`).
  2. **Pipeline (`walk_pipeline`)**: `ctx.advance()` (`index + 1`) after each operation (`Field`, `FunctionDef`, `InitField`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `Table*`). Special-cases trailing `Fallback` by wrapping preceding steps in a target try/catch/recovery block.
  3. **Predicate (`walk_predicates`)**: `depth + 1`, `index = 0`, `ctx.advance()` between sibling conditions (`Filter`, `Assert`, `Match`, `LogicNot`, `LogicAnd`, `LogicOr`).
- **`WalkContext` (`traversal/context.py`)**: Frozen dataclass with `index: int = 0`, `depth: int = 0`, `var_name: str = "v"`, `indent_char: str = "    "`, `meta: dict[str, Any]`.
  - Properties: `.prv -> str` (`v` when `index == 0` else `v{index - 1}`), `.nxt -> str` (`v{index}`), `.indent -> str` (`indent_char * depth`).
  - State transitions: `.advance() -> WalkContext` (`index + 1`), `.advance_n(n) -> WalkContext`, `.deeper() -> WalkContext` (`depth + 1`), `.reset_index() -> WalkContext` (`index = 0`).
- **`ModuleBuilder` (`generation/builder.py`)**: Idempotent accumulator with `require_import(line)`, `require_std(name, *, code, imports=())`, `require_runtime(name, *, code, imports=())`, and `reset()`.
- **Two-Pass Codegen**: Visitors execute `_walk_module` twice — Pass 1 populates `ModuleBuilder` (`imports`, `std_defs`, `runtime_defs`); Pass 2 emits the final source with exact imports and helper definitions.

### 5.2 Python `DomSpelling` & `HttpLibStrategy`

- **`DomSpelling` (`targets/python/html_libs/base.py`)**: Passed to `PythonVisitor(dom_spelling_cls=..., bs4_parser=..., http_io=...)`.
  - Subclasses: `Bs4DomSpelling` (emits `BS4_FEATURES = "lxml" | "html.parser" | "html5lib"` from `--bs4-parser`), `LxmlDomSpelling` (uses `FALLBACK_HTML_STR`), `ParselDomSpelling`, `SlaxDomSpelling`.
  - Contract: 10 expression methods (`css_select`, `css_select_all`, `css_remove`, `xpath_select`, `xpath_select_all`, `xpath_remove`, `text`, `raw`, `attr`, `to_bool`) return `list[str]`; 14 predicate methods (`pred_css`, `pred_xpath`, `pred_has_attr`, `pred_attr_*`, `pred_text_*`) return `str`.
- **`HttpLibStrategy` (`targets/python/http_libs/base.py`)**:
  - `HttpxStrategy` (`httpx`): native sync (`httpx.Client`) and async (`httpx.AsyncClient`).
  - `Httpx2Strategy` (`httpx2`): emits **HTTP fallback import** (`try:\n    import httpx2 as httpx\nexcept ImportError:\n    import httpx`) and reuses `httpx.Client` / `httpx.AsyncClient` types.
  - `AioHttpStrategy` (`aiohttp`): async-native (`aiohttp.ClientSession`); sync wrapper via `asyncio.run` + `ThreadPoolExecutor` fallback (rejects `--http-io sync`).
  - `RequestsStrategy` (`requests`): sync-native (`requests.Session`); async wrapper via `loop.run_in_executor`.
  - **HTTP I/O Mode (`--http-io both|sync|async`)**: Controls whether sync (`fetch` / `<endpoint>`), async (`async_fetch` / `async_<endpoint>`), or both method pairs and client imports are emitted.

### 5.3 4-Target Backend Capability Matrix

| Feature | Python (`PythonVisitor`) | JavaScript (`JsVisitor`) | Go (`GoVisitor`) | Rust (`RustVisitor`) |
|---|---|---|---|---|
| **HTML Backend** | `bs4` (`lxml`/`html.parser`/`html5lib`), `lxml`, `parsel`, `slax` | Vanilla DOM (`DOMParser` / `document`) | `PuerkitoBio/goquery` | `dom_query` (`Document`, `Selection`) |
| **HTTP Clients** | `httpx` (default), `httpx2`, `aiohttp`, `requests` | `fetch` (default), `axios` | `net/http` (`*http.Client`) | `reqwest` (`reqwest::Client`, async) |
| **JSON Projection** | `_project_<schema>(data)` allowlist projector + `TypedDict` | `_project<Schema>(data)` allowlist projector + JSDoc `@typedef` | `UnmarshalJSON` on `<Schema>Json` (using `gjson.GetBytes`) / `json.Unmarshal` | `<Schema>Json::from_value(value: Value) -> Result<Self, rt::SscError>` + `#[derive(Deserialize)]` |
| **REST Result Type** | `Union[Ok[T], <Struct>Err<Status>..., UnknownErr, TransportErr]` | `{ok: true, value} \| {ok: false, kind, status, error}` | `<Method>Result` struct (`IsOk()`, `As<Err>()`) | `Result<T, <Struct>Error>` enum (`Err<Status><Suffix>`, `Unknown`, `Transport`) |
| **Per-Call Request Opts** | `**kwargs: Any` (`ssc_merge_kwargs`) | `opts = {}` (`_sscMergeOpts`) | `opts ...sscReqOpt` (`WithHeader`, `WithCookie`, `WithTimeout`) | `opts: Option<&SscRequestOpts>` |
| **Runtime Output** | Inlined by default; `-R` emits `<runtime_name>.py` | Inlined per `.js` file | Always emits shared `sscgen_runtime.go` | Always emits shared `sscgen_runtime.rs` |

### 5.4 JSON Projectors, Runtime HTTP Delegation & Separate Runtime (`-R`)

- **JSON Projectors (ADR-0005)**: Every `json` schema compiles into a strict allowlist projector — `_project_<schema>(data)` in Python, `_project<Schema>(data)` in JavaScript, `UnmarshalJSON` on `<Schema>Json` (using `gjson.GetBytes` / `json.Unmarshal`) in Go, and `<Schema>Json::from_value(value: Value) -> Result<Self, rt::SscError>` (plus `#[derive(Deserialize)]`) in Rust (replacing legacy `JSON_DESCRIPTOR_<SCHEMA>` tables) — that extracts declared fields (and GJSON paths via `from="..."`), enforces required/nullable/`@omitempty` contracts, drops unmodeled wire keys, and raises schema-qualified errors on contract mismatch (enabling safe runtime matcher fallthrough in `@error` evaluation).
- **Runtime HTTP Delegation**: Generated `MethodFetch` and `MethodRest` emit only a typed method signature and a single call to `ssc_rest_call` / `ssc_fetch_html` (or target equivalent), keeping option merging, `response_path` extraction, and `@error` matcher dispatch inside the runtime helper.
- **Separate Runtime (`-R`, Python)**: `generation/runtime.py:register_runtime_file` writes helpers (`_BASE_UTILITY_LINES`, `PY_JSON_PROJECT_HELPER`, `rest_runtime_lines`, user extension `runtime_defs`) to `<runtime_name>.py`. The parser file keeps `TypedDict`, `@dataclass` error variant subclasses, and client type annotations, while `targets/python/rest.py:runtime_export_names(module, *, need_fallback)` imports only the runtime symbols required by that module.

---

## 6. Extension Checklists & Health/Scout APIs

### 6.1 Step-by-Step Extension Checklists

#### 1. Add a New Pipeline Operation
1. Define the AST dataclass in `ssc_codegen/ast/<category>.py` (inherit `Node`, set `accept_type_info`/`ret_type_info` defaults) and re-export in `ssc_codegen/ast/__init__.py`.
2. Add argument and context lint validation in `ssc_codegen/core/linter.py` (`lint_pipeline_op`).
3. Register the operation type signature `OpSig` in `ssc_codegen/core/type_checking.py` (`OP_TYPES`).
4. Add the KDL node parser in `ssc_codegen/core/expressions.py` (update central `E001`/`E100` guard sets if applicable).
5. Register `NodeClass: "visit_<op>"` in `ssc_codegen/traversal/walker.py` (`_DISPATCH`).
6. Implement `visit_<op>(self, node, ctx)` in `PythonVisitor`, `JsVisitor`, `GoVisitor`, and `RustVisitor` (plus `DomSpelling` ABC and `bs4`/`lxml`/`parsel`/`slax` subclasses if DOM-specific).

*(Note: For project-specific operations, prefer DSL `extension Namespace { op { sig ...; py/js/go/rust { ... } } }`, which lowers to `ExtensionCall` without compiler changes.)*

#### 2. Add a New Struct Directive
1. Define the AST node in `ssc_codegen/ast/struct.py` (inherit `Node`) and re-export in `ssc_codegen/ast/__init__.py`.
2. Add structural validation in `ssc_codegen/core/linter.py` (`_lint_single_struct` and allowed directive sets).
3. Parse the directive in `ssc_codegen/core/struct_parser.py` (`parse_struct_body`).
4. Register in `ssc_codegen/traversal/walker.py` (`_DISPATCH`) and implement `visit_<directive>` across `PythonVisitor`, `JsVisitor`, `GoVisitor`, and `RustVisitor`.

#### 3. Add a New Python `DomSpelling` Backend
1. Subclass `DomSpelling` in `ssc_codegen/targets/python/html_libs/<lib>.py`: set `parser_imports`, `document_type`, `document_array_type`, `init_arg_type`, `init_from_str_expr`, `extra_utilities`, `supports_xpath`; implement all 10 expression methods (`-> list[str]`) and 14 predicate methods (`-> str`).
2. Re-export in `ssc_codegen/targets/python/html_libs/__init__.py` and instantiate `PY_<LIB>_CONVERTER` in `ssc_codegen/targets/python/__init__.py`.
3. Register the spelling class in `ssc_codegen/targets/resolver.py` (`_resolve_python`) and `ssc_codegen/main.py` (`HtmlLib` enum).

#### 4. Add a New Python `HttpLibStrategy`
1. Subclass `HttpLibStrategy` in `ssc_codegen/targets/python/http_libs/<client>.py`: set `import_line`, `sync_client_type`, `async_client_type`, `transport_exception`, and implement `rest_runtime_lines() -> list[str]`.
2. Export in `ssc_codegen/targets/python/http_libs/__init__.py` and register in `PythonVisitor._HTTP_STRATEGIES` (`ssc_codegen/targets/python/visitor.py`).
3. Add the client name to valid Python HTTP clients in `ssc_codegen/targets/resolver.py` (`_resolve_python`).

#### 5. Add a New Target Language Backend (`Schema converter`)
1. Create `ssc_codegen/targets/<lang>/` with `visitor.py` (`<Lang>Visitor(BaseWalker)` implementing all `_DISPATCH` handlers), `rest.py`, and `runtime.py`.
2. Register target identifier rules and reserved keywords in `ssc_codegen/symbols.py` (`TARGETS`, case transforms, keyword sets).
3. Add the target block key to `extension` validation in `ssc_codegen/core/extensions.py`.
4. Add `_resolve_<lang>(spec)` in `ssc_codegen/targets/resolver.py` and wire the CLI subcommand in `ssc_codegen/main.py`.

### 6.2 Health & Scout Programmatic APIs

| Function | Signature (`In -> Out`) | Behavior Summary |
|---|---|---|
| `check_struct_health` (`ssc_codegen/health.py`) | `(struct: StructBase, html: str, module: Module \| None = None) -> HealthResult` | Evaluates CSS/XPath selectors against `html` (`bs4` + `lxml`) without codegen. Single/multi selectors fail on `0` matches; remove selectors warn on `0` matches; trailing `fallback` downgrades fail to warn; recurses into `nested` structs with cycle detection. |
| `compile_filters` (`ssc_codegen/explore.py`) | `(*, text: str \| None = None, attrs: Iterable[str] = (), tag: str \| None = None, css: str \| None = None, ignore_case: bool = False, fixed: bool = False) -> ScoutFilters` | Compiles regex/literal text, attribute (`NAME`, `NAME=VAL`, `NAME=~REGEX`), tag, and CSS filters into a `ScoutFilters` instance (`FilterError` on invalid syntax). |
| `run_scout` (`ssc_codegen/explore.py`) | `(html: str, filters: ScoutFilters \| None = None, *, text: str \| None = None, attrs: Iterable[str] = (), tag: str \| None = None, css: str \| None = None, ignore_case: bool = False, fixed: bool = False, full: bool = False) -> ScoutResult` | Unified HTML reconnaissance engine: runs full-page structural distillation (`mode="overview"`: `page_summary`, `embedded_json`, `kv_blocks`, `repeating_lists`, `navigation_lists`) by default, or switches to `mode="zoom"` when filters are active (matching deepest minimal DOM nodes across inline tags and auto-expanding enclosing containers into `repeating_lists`, `kv_blocks`, or `zoom_matches` with `<-- MATCH` / `"matched": True` annotations). |
| `run_discover` (`ssc_codegen/explore.py`) | `(html: str, *, full: bool = False) -> ScoutResult` | Backward-compatible alias forwarding to `run_scout(html, full=full)` (`DiscoverResult = ScoutResult`). |
