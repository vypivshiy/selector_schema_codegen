# project overview

Это python 3.10+ CLI когоденератор kdl2.0 based DSL в модули-парсеры

# LLM workflow

Всегда начинай с `llm_overview.md` — структура проекта, CLI, ключевые паттерны.
Дальше читай только нужные по задаче файлы:

| Файл | Когда читать |
|------|-------------|
| `llm_types_ast.md` | работа с AST-нодами, VariableType, StructType, добавление новых операций |
| `llm_core.md` | парсер KDL→AST, линтинг, type checking, добавление нового синтаксиса |
| `llm_converters.md` | кодогенерация, BaseWalker, DomSpelling, HttpLibStrategy, новый target language, @request транспорт |
| `llm_howto.md` | пошаговые инструкции: новая операция / директива / конвертер |

Не запускай Explore агентов и не осматривай файлы самостоятельно — действуй по чеклистам из нужных файлов.

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

see `llm_overview.md` file

# docs
see `docs/llm.txt` file