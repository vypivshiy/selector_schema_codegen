# API Reference Documentation Generation

Accepted: The project uses **Material for MkDocs** with **mkdocstrings (Griffe)** and **mkdocs-click** to automatically generate comprehensive code and CLI API reference documentation directly from Python type annotations, Google-style docstrings, and Typer commands.

## Context
`selector_schema_codegen` is a compiler and code generator with an intermediate AST representation, extensive typing, and pluggable backends. Developers extending compiler passes, writing new target backends, or using `ssc_codegen` as a library require an accurate, up-to-date API reference without manual documentation maintenance.

## Decision
1. **Toolchain**:
   - `mkdocs-material` for documentation structure, search, and theming.
   - `mkdocstrings[python]` with Griffe static AST parser to extract signatures, type hints (PEP 484/604), and docstrings without executing arbitrary module code at build time.
   - `mkdocs-click` to automatically introspect the `ssc-gen` CLI application (`ssc_codegen.main:get_click_app`).
2. **Docstring Standard**:
   - All documented functions, classes, and methods must follow **Google-style docstrings** (`Args`, `Returns`, `Raises`, `Yields`).
3. **Scope**:
   - The API reference (`docs/api/`) spans the full architectural surface: public facade, CLI commands, AST nodes, compiler core/linter/expression parsers, traversal engine, and target converters.
   - All public members are rendered (`members: true`), with source code display (`show_source: true`) and type cross-linking enabled.

## Consequences
- Documentation dependencies are isolated in `[dependency-groups] docs`.
- Docstrings are parsed statically by Griffe, eliminating side-effects during doc builds.
- CLI argument and flag documentation automatically updates when Typer commands change in `ssc_codegen/main.py`.
