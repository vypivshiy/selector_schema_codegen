# project overview

Это python 3.10+ CLI когоденератор kdl2.0 based DSL в модули-парсеры

# Dev workflow

**Always use `uv`, not `python` or `python3`*** 

# Build & development

```bash
# 1. install dev dependencies
uv sync

# 2. format, fix code
uv run ruff format ssc_codegen/
uv run ruff check ssc_codegen/ --fix
uv run ruff format tests/
uv run ruff check tests/ --fix

# 3. run tests
uv run pytest

# 4. run linter
uv run ruff check ssc_codegen/

# 5. type checking
uv run mypy ssc_codegen/
```

# project structure

see `llm.txt` file

# docs
see `docs/llm.txt` file