# AGENTS.md

## Project overview

**ssc_codegen** — code generator for web scraping parsers. Takes `.kdl` schema files (KDL 2.0 DSL) describing HTML structure and CSS selectors, parses them into an AST via tree-sitter, validates with a linter, and generates ready-to-use parser code for multiple targets.

## Architecture

```
.kdl schema → [tree-sitter parser] → AST → [linter] → [converter] → output code
```

### Key modules (`ssc_codegen/`)

- `parser.py` — KDL → AST. Uses tree-sitter with a custom KDL 2.0 grammar (`linter/_kdl_lang.py` loads `kdl.so`/`.dll`/`.dylib` via ctypes)
- `ast/` — AST node types and type system
- `linter/` — static analysis: type checking, rule validation, structural checks. `base.py` is the main linter entry point
- `converters/` — code generators per target:
  - `py_bs4.py` — Python + BeautifulSoup4
  - `py_lxml.py` — Python + lxml
  - `py_parsel.py` — Python + Parsel (Scrapy)
  - `py_slax.py` — Python + Selectolax
  - `js_pure.py` — JavaScript (DOM API)
- `main.py` — CLI (typer). Commands: `generate`, `check`, `run`, `health`

### Native dependency

The project vendors a fork of tree-sitter-kdl (KDL 2.0 grammar) as a git submodule at `vendor/tree-sitter-kdl`. The C sources (`parser.c`, `scanner.c`) are compiled into a platform-specific shared library during wheel build via a custom hatch build hook (`hatch_build.py`).

The compiled library is loaded at runtime through `ssc_codegen/linter/_kdl_lang.py` using `ctypes.CDLL`.

### DSL reference

`SYSTEM_PROMPT.md` contains the complete KDL Schema DSL v2.1 specification — struct types, pipeline operations, type tracing rules, predicates, and examples. This is the authoritative reference for the DSL syntax.

## Build & development

```bash
# install dev dependencies
uv sync

# build wheel (compiles tree-sitter-kdl automatically via hatch hook)
uv build --wheel

# run tests
uv run pytest

# run linter
uv run ruff check ssc_codegen/

# type checking
uv run mypy ssc_codegen/
```

### Build system

- Build backend: hatchling
- Custom build hook: `hatch_build.py` — compiles `vendor/tree-sitter-kdl/src/{parser,scanner}.c` into a shared library and sets the platform-specific wheel tag (`py3-none-{platform}`)
- CI: `cibuildwheel` + `uv` (`.github/workflows/publish.yml`)

## Testing

```bash
uv run pytest                    # all tests
uv run pytest tests/linter/      # linter tests
uv run pytest tests/integration/ # integration tests
uv run coverage run -m pytest && uv run coverage report
```

## Conventions

- Python >=3.10, target ruff version `py310`
- Line length: 80 chars
- No type annotations required in `converters/` and `tests/`
- Use `typing_extensions` for backports below 3.11

## Docs

`docs/` contains draft documentation (may be outdated). For the actual DSL spec, refer to `SYSTEM_PROMPT.md`.
