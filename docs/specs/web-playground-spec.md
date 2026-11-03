# Spec: Client-Side Web Playground (`/playground/`) with KDL 2.0 Grammar and Pyodide Worker

## Problem Statement

Developers and LLM agents evaluating or authoring an **HTML schema**, **Raw schema**, or **REST schema** in KDL Schema DSL (v2.1) currently must install a local Python environment (`>=3.10`) and run the `ssc-gen` CLI to perform **schema validation**, **code generation validation**, or interactive HTML selector testing (`run` and `health`).

There is no zero-backend, browser-based playground where users can:
1. Author KDL 2.0 schemas with accurate KDL 2.0 syntax highlighting (distinguishing KDL 2.0 tokens such as `#true`, `#false`, `#null`, `#"raw"#`, `"""..."""`, and `/-` from deprecated KDL 1.0 bare literals) and semantic highlighting/autocompletion for `ssc-gen` DSL constructs.
2. See live **schema validation** diagnostics (`E0xx` / `W0xx`) with exact source spans and remediation hints directly in the editor.
3. Inspect emitted code across all four target languages (`python`, `js`, `go`, `rust`) and target options (`HTML backend`, `BS4 parser engine`, `HttpLibStrategy`, `HTTP I/O mode`, and separate runtime helper modules `sscgen_runtime.*`).
4. Paste or upload a sample HTML file to execute the generated parser (`Run`) and inspect per-selector DOM match counts (`Health`) entirely in the browser without a backend server.
5. Host the tool as a static single-page application alongside the project's MkDocs site on GitHub Pages (`/playground/`) without relying on GitHub Actions or server-side runtimes.

## Solution

Build a static, client-side single-page Web Playground in `playground/` (Vite + React + TypeScript + Monaco Editor) that runs `ssc_codegen` 100% in the user's browser inside a `WebWorker` powered by **Pyodide (CPython in WebAssembly)** and deploys into `/playground/` alongside the MkDocs documentation via local deployment scripts (`gh-pages` branch):

1. **Custom KDL 2.0 + `ssc-gen` DSL Monarch Grammar & Autocompletion**:
   - Register a custom `kdl2` language in Monaco Editor with a stateful Monarch tokenizer that enforces KDL 2.0 lexical rules (`#true`, `#false`, `#null`, `#inf`, `#-inf`, `#nan`, arbitrary-hash raw strings `#"..."#` and `#"""..."""#`, multi-line strings `"""..."""`, nested `/* ... */` comments, slashdash `/-`, and flags bare KDL 1.0 `true`/`false`/`null` literals as `invalid`) while highlighting `ssc-gen` DSL v2.1 declarations (`struct`, `json`, `fn`, `define`), type annotations (`(item)`, `(list)`, `(table)`, `(dict)`, `(flat)`, `(raw)`, `(rest)`, `(array)`), directives (`@request`, `@error`, `@split-doc`, `@table`, `@init`, `@skip`, `@omitempty`), pipeline operations, predicates, and `{{placeholder}}` templates.
   - Provide a Monaco `CompletionItemProvider` offering context-aware completions and snippets for `@` directives, `(type)` struct/json annotations, pipeline operations, and predicate operators.
2. **Pyodide WebWorker Engine Bridge**:
   - Initialize Pyodide in a dedicated background `WebWorker`, preloading built-in WASM packages (`lxml`, `beautifulsoup4`, `soupsieve`, `cssselect`, `micropip`) and installing `kdlquery` and `ssc-codegen` wheels from PyPI (`deps=False`).
   - Expose two deterministic RPC actions over the public `ssc_codegen` facade:
     - `compile_and_lint`: Runs `parse_module()` for **schema validation**, extracts 1-based line/column diagnostics via `diagnostic_to_dict()`, enumerates declared structs (with their `StructType` and `REST schema` vs `HTML schema` / `Raw schema` capability), warns if multi-file `imports` are used in the single-buffer playground, and runs the **schema converter** (`resolve(TargetSpec(...)).create_converter().convert(ast)`) to return all emitted target files (`parser.*` and `sscgen_runtime.*`).
     - `test_html`: For a selected **HTML schema** or **Raw schema** struct and user-supplied HTML string, runs `check_struct_health()` to produce a selector match report and executes the generated Python parser against the HTML string to return the extracted JSON result.
3. **Two-Column Interactive Playground UI**:
   - **Topbar**: Displays the Pyodide runtime readiness badge (including installed `ssc-codegen` version), a curated **Examples** selector preloading paired `.kdl` + sample `.html` demos (covering item/list HTML extraction, `@table`, `(raw)struct`, and `(rest)struct` with `@request`, `@error`, and **JSON projector** schemas), a theme toggle, and a **Share URL** button that compresses the current workspace into `window.location.hash` via `CompressionStream('deflate-raw')`.
   - **Left Column (50%)**: KDL 2.0 Monaco Editor with live squiggle markers (`setModelMarkers`), hover hints, and a clickable bottom diagnostics drawer that jumps the cursor to the diagnostic's line and column.
   - **Right Column (50%) with Two Primary Tabs**:
     - **`Generated Code` Tab**: Target language selector (`Python | JS | Go | Rust`), contextual `TargetSpec` controls (`HTML backend`, `BS4 parser engine`, `HttpLibStrategy`, `HTTP I/O mode`, `separate_runtime`), file switcher (`parser.*` vs `sscgen_runtime.*`), Copy button, and read-only Monaco code viewer.
     - **`Test & Health (HTML)` Tab**: HTML input editor with local `.html` file upload (`FileReader`), target `Struct` selector dropdown (auto-selecting the primary HTML/Raw struct and disabling HTML execution with an explanatory notice when a **REST schema** struct is selected), **`Run Parser`** and **`Check Health`** actions, and tabbed results showing the extracted JSON output and the per-selector health status table (`ok` / `warn` / `fail` and match count).
4. **Local Static Build & `gh-pages` Deployment Without GitHub Actions**:
   - Provide cross-platform deployment scripts (`scripts/deploy_pages.ps1` and `scripts/deploy_pages.sh`) that build MkDocs into `site/`, build the Vite playground (`base: './'`) into `site/playground/`, link the Playground from `mkdocs.yml`, and publish `site/` to the `gh-pages` branch locally.

## User Stories

1. As a schema author, I want to open `/playground/` in my browser and immediately use `ssc_codegen` without installing Python, `lxml`, or CLI tools locally, so that I can prototype and validate schemas from any device.
2. As a schema author writing KDL 2.0, I want `#true`, `#false`, `#null`, `#inf`, `#-inf`, and `#nan` highlighted as valid language constants and bare KDL 1.0 `true`, `false`, and `null` highlighted as `invalid`, so that I immediately spot KDL 1.0 vs KDL 2.0 syntax mistakes before linting.
3. As a schema author writing regex patterns in `re` or `attr-re` operations, I want KDL 2.0 raw strings (`#"..."#`, `##"..."##`, `#"""..."""#`) tokenized with exact matching opening and closing `#` counts, so that embedded quotes inside regexes do not break syntax highlighting.
4. As a schema author, I want KDL 2.0 multi-line strings (`"""..."""`), nested block comments (`/* ... /* ... */ ... */`), and slashdash comments (`/-`) highlighted accurately in the editor, so that commented-out nodes and multi-line `@request` payloads are visually clear.
5. As a schema author, I want `ssc-gen` type annotations (`(item)`, `(list)`, `(table)`, `(dict)`, `(flat)`, `(raw)`, `(rest)`, `(array)`) and nullable types (`(Type?)`) highlighted distinctly from node names, so that struct and JSON schema signatures stand out.
6. As a schema author, I want `ssc-gen` top-level declarations (`struct`, `json`, `fn`, `define`), directives (`@request`, `@error`, `@split-doc`, `@table`, `@init`, `@skip`, `@omitempty`), pipeline operations (`css`, `css-all`, `xpath`, `re`, `attr`, `text`, `jsonify`, `nested`, `fallback`), and predicates (`filter`, `assert`, `match`, `eq`, `has-attr`, `text-re`) colored by semantic role, so that complex pipelines are easy to read.
7. As a schema author writing a **REST schema**, I want `{{placeholder}}` tokens inside `@request` strings and `UPPER_CASE` `define` constants highlighted distinctly, so that request interpolation parameters are easy to verify.
8. As a schema author, I want autocomplete suggestions when typing `@`, `(`, or pressing `Ctrl+Space` in the KDL editor, so that I can insert valid directives, struct annotations, and pipeline operations without memorizing every keyword.
9. As a schema author, I want live **schema validation** to run automatically in a background `WebWorker` (debounced at ~150–200 ms) as I type, so that the editor UI never freezes during compilation.
10. As a schema author, I want **schema validation** errors and warnings rendered both as inline squiggles in the Monaco editor (with error code `E0xx`/`W0xx`, message, and `hint` on hover) and in a clickable bottom diagnostics panel that jumps the cursor to the exact line and column.
11. As a schema author, I want a clear diagnostic warning if my schema contains an `imports` declaration, so that I understand the web playground operates on a single `.kdl` buffer.
12. As a developer evaluating target code generation, I want to switch between `Python`, `JavaScript`, `Go`, and `Rust` targets and immediately see the generated parser code in a syntax-highlighted read-only editor, so that I can compare output across languages.
13. As a Python developer, I want to configure Python-specific `TargetSpec` options (`HTML backend`: `bs4`, `lxml`, `parsel`, `slax`; `BS4 parser engine`: `lxml`, `html.parser`, `html5lib`; `HttpLibStrategy`: `httpx`, `httpx2`, `aiohttp`, `requests`; `HTTP I/O mode`: `both`, `sync`, `async`; and `separate_runtime`), so that I can generate code tailored to my project's stack.
14. As a JavaScript developer, I want to switch the JavaScript `HttpLibStrategy` option between `fetch` and `axios` (while Python-only options are hidden), so that I only see valid target options for the selected language.
15. As a Go, Rust, or Python (`separate_runtime`) developer, I want a file tab bar above the code viewer allowing me to switch between the generated parser module (`parser.go`, `parser.rs`, `parser.py`) and the emitted runtime helper module (`sscgen_runtime.go`, `sscgen_runtime.rs`, `sscgen_runtime.py`), plus a one-click Copy button, so that I can inspect and copy both artifacts.
16. As a developer authoring a **REST schema** with `@request`, `@error`, and `json` / `(dict)json` declarations, I want full **schema validation** and **code generation validation** across all targets in the playground without executing live HTTP requests, so that I can design and verify typed REST clients and **JSON projectors** safely offline.
17. As an **HTML schema** or **Raw schema** author, I want to paste raw HTML/text or upload a local `.html` file from my computer into the `Test & Health (HTML)` tab without sending data to any server, so that I can test my schema privately against saved pages.
18. As an **HTML schema** author whose schema defines multiple structs (e.g., an item struct `QuoteItem` and a container struct `MainCatalogue`), I want the playground to auto-select the primary non-REST struct by default while providing a `Struct` dropdown to select any individual struct for testing, so that I can debug nested item structs in isolation.
19. As a schema author, I want the `Run Parser` and `Check Health` buttons to be disabled with a clear explanation (`REST schema: lint & codegen only`) whenever a `(rest)struct` is selected, so that I know why HTML testing does not apply to REST schemas.
20. As an **HTML schema** or **Raw schema** author, I want clicking `Run Parser` to execute the generated parser against the provided HTML/text input inside Pyodide and display the extracted JSON result (and execution time), so that I can verify the exact runtime output of my pipelines.
21. As an **HTML schema** author, I want clicking `Check Health` to run `check_struct_health()` against the provided HTML and render a table of all CSS and XPath selectors in the struct (and its nested structs) showing each selector's field path, type (`css`, `css-all`, `xpath`, etc.), query string, match count, and status (`ok`, `warn`, `fail`), so that I can immediately spot broken selectors returning `0` matches.
22. As a first-time visitor or presenter demonstrating `ssc_codegen`, I want an `Examples` dropdown in the topbar offering curated presets (HTML item/list extraction, `@table` extraction, `(raw)struct` extraction, and `(rest)struct` with **JSON projector** schemas) that populate both the `.kdl` editor and a matching sample `.html` document, so that I can demonstrate linting, codegen, `Run`, and `Health` in one click.
23. As a user experimenting in the playground, I want my current `.kdl` schema, sample `.html`, and target settings automatically saved in `localStorage` and shareable via a compressed `#hash` URL when I click `Share URL`, so that I never lose work on refresh and can share reproducible examples via a static link.
24. As a repository maintainer without access to GitHub Actions, I want local deployment scripts (`scripts/deploy_pages.ps1` and `scripts/deploy_pages.sh`) that build the MkDocs documentation (`site/`), build the playground into `site/playground/`, and publish the combined static site to the `gh-pages` branch, so that `/playground/` is hosted on GitHub Pages alongside the documentation with zero backend infrastructure.

## Implementation Decisions

- **Static SPA Architecture & Two-Column Layout**:
  - Build the frontend as a standalone Vite + React + TypeScript application inside `playground/` configured with relative asset paths (`base: './'`) so it can be served from `/playground/` under any GitHub Pages repository path prefix.
  - Use a responsive 2-column split layout:
    - Left column (50%): Monaco Editor for the KDL 2.0 schema and a collapsible bottom diagnostics drawer.
    - Right column (50%): Tabbed workspace switching between `Generated Code` and `Test & Health (HTML)`.
- **Custom KDL 2.0 + `ssc-gen` Monarch Tokenizer & Completion Provider**:
  - Implement a custom Monarch language definition (`kdl2`) rather than relying on external Oniguruma WASM / TextMate grammars, avoiding broken `(type)` node highlighting in third-party TextMate bundles and enabling first-class semantic token classes for `ssc-gen` DSL v2.1.
  - The Monarch state machine must track `#` delimiter counts on raw strings (`#"..."#`, `#"""..."""#` via state parameter `$S2`), support nested `/* ... */` block comments via `@push`/`@pop`, highlight `{{...}}` placeholders inside strings, mark bare KDL 1.0 literals (`true`, `false`, `null`, `inf`, `nan` without `#`) as `invalid`, and classify identifiers against canonical `ssc-gen` declaration, directive, pipeline operation, predicate, and primitive type vocabularies.
  - Register a Monaco `CompletionItemProvider` for `kdl2` supplying completion items and snippets for directives (`@request`, `@error`, `@split-doc`, `@table`, `@init`, `@skip`, `@omitempty`), type annotations (`(item)struct`, `(list)struct`, `(table)struct`, `(dict)struct`, `(flat)struct`, `(raw)struct`, `(rest)struct`, `(dict)json`, `(array)json`), pipeline operations, and predicates.
- **Pyodide WebWorker & PyPI Wheel Installation Contract**:
  - Run CPython in WebAssembly inside a dedicated module `WebWorker`.
  - During worker initialization:
    1. Load Pyodide from the official CDN and load built-in WASM packages: `micropip`, `lxml`, `beautifulsoup4`, `soupsieve`, and `cssselect`.
    2. Install pure-Python wheels from PyPI via `micropip.install(["kdlquery>=1.7.0", "ssc-codegen>=0.45.0"], deps=False)` so CLI/network-only dependencies (`typer`, `httpx`, `colorama`) are not downloaded in the browser.
    3. Report the loaded `ssc_codegen` version to the main thread once ready.
  - Extract the Python-side worker handler logic into a clean, testable Python module/script executed by the worker that communicates via JSON-serializable request/response dictionaries:
    ```python
    # Decision-rich contract for worker responses:
    # compile_and_lint(kdl_src: str, target: dict) -> dict
    {
        "ok": bool,
        "diagnostics": [
            {
                "code": str,
                "severity": "error" | "warning",
                "message": str,
                "hint": str,
                "span": {
                    "start": {"offset": int, "line": int, "column": int},
                    "end": {"offset": int, "line": int, "column": int},
                },
            }
        ],
        "structs": [
            {"name": str, "type": str, "is_rest": bool}
        ],
        "files": dict[str, str],  # e.g. {"parser.py": "...", "sscgen_runtime.py": "..."}
        "target_error": str | None,
    }

    # test_html(kdl_src: str, html_src: str, struct_name: str | None) -> dict
    {
        "ok": bool,
        "struct_name": str | None,
        "run_result": Any,        # JSON-serializable parsed output
        "run_error": str | None,
        "elapsed_ms": float,
        "health": {
            "struct_name": str,
            "passed": bool,
            "checks": [
                {
                    "path": str,
                    "selector_type": str,
                    "query": str,
                    "matches": int,
                    "status": "ok" | "warn" | "fail",
                    "message": str,
                }
            ],
        } | None,
    }
    ```
  - If the AST or CST contains an `imports` declaration, append a non-fatal warning diagnostic explaining that `imports` resolution across external files is not supported in the single-file browser playground.
- **Target Options Resolution & Multi-File Output**:
  - Map UI target controls directly to `TargetSpec(lang, lib, bs4_parser, http_client, http_io, separate_runtime, emit_runtime=True)` and validate via `resolve(spec)`.
  - Display all key-value pairs returned by `converter.convert(ast)` as selectable file tabs (`parser.*` and, when present, `sscgen_runtime.*`) with the matching Monaco syntax language (`python`, `javascript`, `go`, `rust`).
- **URL Hash Compression & Local Persistence**:
  - Persist workspace edits (`kdl`, `html`, `target`) to `localStorage`.
  - Encode shareable links into `#state=<base64url>` using the browser's native `CompressionStream("deflate-raw")` / `DecompressionStream("deflate-raw")` APIs (with uncompressed base64url fallback) so shared URLs require zero backend storage.
- **Documentation & Local `gh-pages` Deployment Scripts**:
  - Add a navigation link to the Playground in `mkdocs.yml`.
  - Provide `scripts/deploy_pages.ps1` and `scripts/deploy_pages.sh` to build MkDocs (`site/`), build the Vite app into `site/playground/`, and push `site/` to the `gh-pages` branch locally without GitHub Actions.

## Testing Decisions

- **What Makes a Good Test**:
  - Tests must verify observable external behavior and serialized contracts at module boundaries rather than internal React state hooks or private regex helpers.
- **Seams to Test**:
  1. **Primary Seam — Worker Engine Bridge (`compile_and_lint` and `test_html` Python handler over `ssc_codegen` public facade)**:
     - Verify `compile_and_lint` on valid and invalid **HTML schemas**, **Raw schemas**, and **REST schemas**:
       - Emits structured diagnostics with 1-based `line` and `column` spans matching `diagnostic_to_dict()`.
       - Enumerates all declared structs with accurate `type` (`item`, `list`, `table`, `dict`, `flat`, `raw`, `rest`) and `is_rest` flags.
       - Emits a clear warning when an `imports` node is present in the schema.
       - Produces valid generated code files (`parser.*` and `sscgen_runtime.*` where applicable) across `python` (`bs4`, `lxml`, `parsel`, `slax`), `js` (`fetch`, `axios`), `go`, and `rust`.
     - Verify `test_html`:
       - Executes generated parser code against sample HTML/text for a chosen struct (or auto-selected default non-REST struct) and returns the expected JSON extraction result.
       - Returns the structured `check_struct_health` report with accurate per-selector match counts and `ok` / `warn` / `fail` statuses.
       - Rejects `REST schema` structs gracefully when passed to `test_html`.
  2. **Secondary Seam — KDL 2.0 + `ssc-gen` Grammar Tokenizer & URL State Codec (`Vitest` + `vite build`)**:
     - Verify the KDL 2.0 Monarch grammar rules classify KDL 2.0 literals (`#true`, `#false`, `#null`, `#inf`, `#-inf`, `#nan`), raw strings (`#"..."#`, `##"..."##`, `#"""..."""#`), multi-line strings (`"""..."""`), slashdash (`/-`), bare KDL 1.0 literals (`invalid`), type annotations (`(item)`, `(dict)`), directives (`@request`, `@error`), and `{{placeholder}}` templates into their expected token classes.
     - Verify round-trip encoding and decoding of playground workspace state (`kdl`, `html`, `target`) through the URL `#hash` codec.
     - Verify `vite build` succeeds cleanly with zero TypeScript or bundler errors.
- **Prior Art in the Codebase**:
  - Existing `pytest` tests for `parse_module`, `diagnostic_to_dict`, `resolve(TargetSpec(...))`, and `check_struct_health` in `tests/`.

## Out of Scope

- Rewriting the `ssc_codegen` compiler or `kdlquery` parser in JavaScript, TypeScript, or Rust.
- Executing live HTTP requests for **REST schemas** or fetching remote third-party URLs from the browser (avoiding CORS and proxy requirements).
- Multi-file virtual filesystem tabs for resolving external `.kdl` `imports` in the browser.
- Executing generated `JavaScript`, `Go`, or `Rust` parsers inside the browser (`Run` uses the generated Python parser inside Pyodide; other languages are for code generation and inspection).
- GitHub Actions CI/CD workflows (deployment uses local scripts targeting the `gh-pages` branch).

## Further Notes

- The Pyodide worker depends on `kdlquery>=1.7.0` publishing a pure-Python wheel (`py3-none-any.whl`) on PyPI so `micropip.install()` can install it directly in WebAssembly without building from an `sdist` tarball.
