# Specification: Python Target Enhancements — httpx2 Backport, Configurable BS4 Parser, and HTTP I/O Mode

## Problem Statement

Developers targeting Python parsers face three limitations when generating scraping code:
1. The upstream `httpx` package is in maintenance mode, and projects migrating to the active `httpx2` fork cannot use generated parsers without manual monkey-patching or linting errors.
2. BeautifulSoup4 parsers are hardcoded to `BS4_FEATURES = 'lxml'`, which fails or requires edits in environments where `lxml` is unavailable (e.g. pure-Python setups using `html.parser`) or when handling malformed HTML requiring `html5lib`.
3. The generator always emits both synchronous (`fetch`, `endpoint`) and asynchronous (`async_fetch`, `async_endpoint`) client methods, cluttering generated client interfaces and creating unnecessary dependencies on async client types when consumers only require synchronous execution (or vice versa).

## Solution

Extend the Python code generation target with three modular capabilities:
1. Introduce an HTTP fallback import for `httpx` (`try: import httpx2 as httpx except ImportError: import httpx`) alongside a dedicated `--http-client httpx2` option for strict modern environments.
2. Add a `--bs4-parser` option accepting `lxml`, `html.parser`, or `html5lib`, annotating `BS4_FEATURES: Literal["html.parser", "lxml", "html5lib"]` and allowing dynamic override in `__init__(document, *, features=BS4_FEATURES)`.
3. Add an `--http-io` option (`both`, `sync`, `async`) to prune unneeded methods, client signatures, and runtime helper calls according to consumer needs.

## User Stories

1. As a Python developer in a modern codebase using httpx2, I want `ssc-gen generate python --http-client httpx` to gracefully import `httpx2` if present, so that my generated parser works without modifications.
2. As a Python developer enforcing strict dependencies, I want to pass `--http-client httpx2` to generate strict `import httpx2` and `httpx2.Client` signatures.
3. As a developer deploying to lightweight environments without C-extensions, I want `ssc-gen generate python -L bs4 --bs4-parser html.parser`, so that the generated parser does not depend on `lxml`.
4. As a developer scraping messy HTML, I want `ssc-gen generate python -L bs4 --bs4-parser html5lib`, so that the parser handles broken DOM trees gracefully.
5. As a library consumer, I want the generated BS4 parser class to accept `features: Literal["html.parser", "lxml", "html5lib"] = BS4_FEATURES` in `__init__`, so that I can override the parser engine on an instance-by-instance basis if needed.
6. As a developer building a synchronous CLI scraper, I want `--http-io sync`, so that only `fetch` and synchronous REST methods are emitted without `async def` wrappers.
7. As a developer building an asynchronous service with FastAPI or AsyncIO, I want `--http-io async`, so that only `async_fetch` and `async_<name>` methods are emitted.
8. As a developer using aiohttp with `--http-io sync`, I want the CLI/resolver to fail early with a descriptive `ResolutionError`, so that I do not generate invalid or broken code.
9. As a developer using requests with `--http-io async`, I want the generator to succeed using the existing `asyncio.to_thread` worker pool delegate.
10. As a developer generating separate runtime modules (`-R`), I want the runtime file to preserve both `ssc_rest_call` and `ssc_rest_call_async`, so that a single shared runtime file can serve multiple modules regardless of their individual I/O modes.
11. As a Go, Rust, or JavaScript developer, I want passing `--http-io` or `--bs4-parser` to fail with a clear `ResolutionError`, so that target-specific options are not silently accepted for unsupported languages.

## Implementation Decisions

- **Target Configuration Model (`TargetSpec` & `resolver.py`)**:
  - Add `bs4_parser: str | None = None` and `http_io: str = "both"` to `TargetSpec`.
  - Validate in `resolve()`:
    - `--bs4-parser` is only valid when `lang == "python"` and `lib == "bs4"`. Permitted values: `"lxml"`, `"html.parser"`, `"html5lib"`. Defaults to `"lxml"`.
    - `--http-io` is only valid when `lang == "python"`. Permitted values: `"both"`, `"sync"`, `"async"`. Defaults to `"both"`.
    - If `http_client == "aiohttp"` and `http_io == "sync"`, raise `ResolutionError`.
    - Allow `http_client == "httpx2"` as a first-class Python HTTP client alongside `"httpx"`, `"aiohttp"`, `"requests"`.

- **HTTP Strategies (`HttpxStrategy` and `Httpx2Strategy`)**:
  - `HttpxStrategy` (`--http-client httpx`) emits the HTTP fallback import:
    ```python
    try:
        import httpx2 as httpx
    except ImportError:
        import httpx
    ```
    Its signatures remain `httpx.Client`, `httpx.AsyncClient`, and `httpx.HTTPError`.
  - Introduce `Httpx2Strategy(HttpxStrategy)` (`--http-client httpx2`), which emits strict `import httpx2` with `httpx2.Client`, `httpx2.AsyncClient`, and `httpx2.HTTPError`.
  - Ensure `ModuleBuilder.require_import` handles multi-line fallback imports correctly and preserves deduplication.

- **BeautifulSoup4 DOM Spelling (`Bs4DomSpelling`)**:
  - Parameterize `Bs4DomSpelling` with the chosen `bs4_parser` (default `"lxml"`).
  - Emit typed module constant:
    ```python
    BS4_FEATURES: Literal["html.parser", "lxml", "html5lib"] = '{bs4_parser}'
    ```
  - In `visit_module`, ensure `from typing import Literal` is required when generating BS4 code.
  - In `visit_init`, generate:
    ```python
    def __init__(self, document: Union[str, BeautifulSoup, Tag], *, features: Literal["html.parser", "lxml", "html5lib"] = BS4_FEATURES) -> None:
        if isinstance(document, str):
            self._doc = BeautifulSoup(document, features=features)
        else:
            self._doc = document
    ```

- **HTTP I/O Mode Filtering (`rest.py` & `visitor.py`)**:
  - In `emit_method_fetch`:
    - When `http_io in ("both", "sync")`: emit synchronous `fetch` (if supported by strategy).
    - When `http_io in ("both", "async")`: emit `async_fetch`.
  - In `emit_method_rest`:
    - When `http_io in ("both", "sync")`: emit `def {method_name}`.
    - When `http_io in ("both", "async")`: emit `async def async_{method_name}`.
  - In `PythonVisitor.visit_module`:
    - Only register sync/async client type annotations needed by the active `http_io` mode.
  - In shared runtime (`-R`), keep both `ssc_rest_call` and `ssc_rest_call_async` for cross-module compatibility. In inline mode without `-R`, emit only the relevant helper if desired.

## Testing Decisions

- Test external behavior exclusively through existing seams:
  1. CLI parameter parsing and options validation via `CliRunner` invoking `main:app`.
  2. Capability resolution and error messages via `resolve(TargetSpec(...))`.
  3. Code validity and runtime execution via `_exec_with_runtime` and `exec(compile(code, ...))`.
- Prior art:
  - `tests/test_cli.py` for CLI validation and error reporting.
  - `tests/test_rest_api.py` (`TestSeparateRuntime`, `TestRequestsTransport`, `TestAioHttpTransport`) for end-to-end Python code generation and execution.

## Out of Scope

- Changes to non-Python backends (JavaScript, Go, Rust).
- DSL syntax additions to `.kdl` schema files.
- Forwarding `features` through network `fetch(...)` calls (runtime features override is achieved via the `BS4_FEATURES` module constant or direct class instantiation).
- Dropping support for legacy `httpx`.

## Further Notes

- The project domain glossary in `CONTEXT.md` has been updated with: `HTTP I/O mode`, `BS4 parser engine`, and `HTTP fallback import`.
