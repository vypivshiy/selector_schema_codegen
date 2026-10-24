# ssc_codegen Agent Guide

`ssc_codegen` (`v0.44.0`, Python `>=3.10`) is a KDL 2.0 Schema DSL (v2.1) compiler and parser generator for HTML scraping, plain-text extraction, and typed REST/JSON HTTP clients. It compiles `.kdl` schemas into standalone modules for **Python** (`bs4`, `lxml`, `parsel`, `slax`), **JavaScript** (ESM + JSDoc, DOM API), **Go** (`goquery` + `net/http` + `gjson`), and **Rust** (`dom_query` + `serde` + `reqwest`). CLI entrypoint: `ssc-gen` (`ssc_codegen.main:main`).

## Context Routing Table

Start with the reference matching your task instead of scanning the repository blind:

| Task / Branch | Reference |
|---|---|
| Compiler architecture, module & symbol map, CLI flags, 5-pass core (`parse_module`), `kdlquery` CST selectors, `ErrorCode` table, `VariableType`/`TypeInfo`/`StructType`, AST node catalog, `BaseWalker`/`WalkContext`/`ModuleBuilder`, target backends (`PythonVisitor`, `JsVisitor`, `GoVisitor`, `RustVisitor`), and step-by-step extension checklists | `llm_overview.md` |
| Ubiquitous language, canonical domain terms (`HTML schema`, `Raw schema`, `REST schema`, `JSON projector`, `GJSON path expression`, `Runtime HTTP delegation`, etc.), and terms to avoid | `CONTEXT.md` |
| Architectural Decision Records (ADR-0001 through ADR-0006: JSON key aliases, Griffe API reference, JSON dict schemas, inline JSON schema hoisting, generated JSON projectors & GJSON subset, runtime HTTP delegation) | `docs/adr/` |
| Authoring or validating `.kdl` schemas: KDL Schema DSL v2.1 syntax, struct types & directives, pipeline operations, predicates, `json` / `(dict)json` / `@request` / `@error` rules, CLI commands, and linter diagnostics | `docs/llm.txt` |
| GitHub Issues and PR operations via `gh` CLI, wayfinder map/ticket conventions | `docs/agents/issue-tracker.md` |
| Canonical issue triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) | `docs/agents/triage-labels.md` |
| Consuming and updating `CONTEXT.md` and `docs/adr/` during domain modeling or architecture reviews | `docs/agents/domain.md` |

## Development Workflow

Always run Python, linter, test, type-check, and documentation commands through `uv`:

```bash
# 1. Sync environment & dependencies
uv sync

# 2. Format & lint code
uv run ruff format ssc_codegen/ tests/
uv run ruff check ssc_codegen/ tests/ --fix

# 3. Run test suite
uv run pytest

# 4. Run static type checker
uv run mypy ssc_codegen/

# 5. Build documentation site (strict mode)
uv run --group docs mkdocs build --strict
```
