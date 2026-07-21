# Линтер: как добавлять правила

**Аудитория:** мейнтейнеры
**Последнее обновление:** 2026-07-21

Линтер интегрирован в парсер `core/` — отдельного модуля `linter/` больше нет.
Валидация происходит в одну проход вместе с построением AST.

## Где находится код

Каталог: `ssc_codegen/core/`

Ключевые файлы:
- `reader.py` — публичный API: `parse_module(src, source_path)` возвращает `(Module, list[ReadDiagnostic])`. Оркестрирует проходы.
- `contexts.py` — `ParseContext`, `LintContext`, `ErrorCode` (`E000`–`E400`, `W001`/`W002`), `WalkCtx`, `DefineInfo`, `RawArg`.
- `linter.py` — структурная валидация KDL-узлов: `lint_module`, `lint_cross_refs`, plus per-op checks (`lint_pipeline_op`, `lint_predicate_op`, `lint_validate_regex`, `lint_validate_css`, `lint_validate_xpath`, …).
- `type_checking.py` — `OpSig`, `check_pipeline_types`, вывод и совместимость типов.
- `expressions.py` — парсинг pipeline-операций в AST + `typedef_from_struct` (генерация `TypeDef` из struct).
- `predicates.py` — парсинг предикатов (`filter`/`assert`/`match` + `not/and/or`).
- `struct_parser.py` — разбор тела struct.
- `module_handler.py` — `handle_define`, `handle_json`, `handle_struct`, `resolve_imports`.
- `rest_artifacts.py` — синтез REST-result узлов (`ResultVariantDef`, `ResultAliasDef`, `MatcherListDef`) из `StructRest`.
- `format.py` — `format_diagnostics(...)` (text + JSON).

KDL-парсер — внешний: `kdlquery` (`KDLParseError`, `KdlNode`, `ReadDiagnostic`, `Severity`, `Span`).
Селекторы kdlquery — отдельный документ: [kdlquery.md](kdlquery.md).

## Модель выполнения (5 проходов в `parse_module`)

1. **KDL parse** — `kdlquery.parse(src)`. Синтаксические ошибки оборачиваются в `ReadDiagnostic` с `code="E000"`.
2. **resolve_imports** — flattened список top-level узлов с inline'ом импортированных define/json/struct.
3. **lint_module** — структурная валидация текущего файла (top-level decls, struct bodies, json children, @request placeholders, field names).
4. **lint_cross_refs** — cross-file проверки: ссылки на define/json/struct, циклы, unknown ops.
5. **build Module AST** — `handle_define` → `handle_json` / `handle_struct` → `typedef_from_struct` / `rest_artifacts_from_struct` → diagnostics merged.

Типы pipeline'а выводятся во время AST-сборки через `check_pipeline_types` (`type_checking.py`).

## Diagnostic API

Линтер не использует registry/decorators. Каждая функция принимает `LintContext`
и складывает диагностики в `ctx.diagnostics` через `ctx.error(...)`:

```python
from ssc_codegen.core.contexts import LintContext, ErrorCode
# ErrorCode.INVALID_SYNTAX == "E000", ErrorCode.TYPE_MISMATCH == "E100", ...

def my_check(node, lint: LintContext) -> None:
    if not _is_valid(node):
        lint.error(
            node,
            code=ErrorCode.MISSING_ARGUMENT,   # "E001"
            message="'css' requires one argument",
            hint='example: css ".item"',
        )
```

`LintContext` также хранит `walk_context: WalkCtx` (MODULE / STRUCT_BODY /
INIT_BLOCK / PIPELINE / JSON_TYPEDEF / SPECIAL_FIELD), текущий путь
(`_path_segments`) и счётчик `_predicate_depth` для контекстно-зависительных
проверок (напр. `len-*` только внутри `assert`).

## Где размещать правило

| Тип правила | Файл | Точка входа |
|---|---|---|
| Структурная проверка top-level / struct body / json | `linter.py` | `_lint_top_level`, `_lint_single_struct`, `_lint_single_json`, `_lint_json_children` |
| Аргументы операции pipeline (`css`, `re`, `attr`, …) | `linter.py` | `lint_pipeline_op` (dispatch по `node.name`) |
| Аргументы предиката (`eq`, `attr-eq`, `len-gt`, …) | `linter.py` | `lint_predicate_op` |
| Валидация regex / CSS / XPath | `linter.py` | `lint_validate_regex`, `lint_validate_css`, `lint_validate_xpath` |
| Cross-reference проверки (define/json/struct ссылки) | `linter.py` | `lint_cross_refs` |
| Тип pipeline | `type_checking.py` | `check_pipeline_types`, `_resolve_op_ret`, `OpSig` |
| @request placeholders | `linter.py` | `lint_request_placeholders` |

## Валидаторы аргументов

В `linter.py` уже есть хелперы:

- `lint_require_args(node, lint, min_n, max_n=None, exact=None)`
- `lint_require_int_args(node, lint, ...)`
- `lint_require_predicate_ctx(node, lint)` — для предикатов вне filter/assert/match
- `lint_require_assert_ctx(node, lint)` — для `len-*`, `re-any`, `re-all`, `gt/lt/ge/le`

## Форматирование вывода

```python
from ssc_codegen.core import format_diagnostics, format_diagnostic
# text
text = format_diagnostics(errs, filepath=path, fmt="text")
# JSON (для LLM-pipelines)
js = format_diagnostics(errs, filepath=path, fmt="json")
```

CLI использует те же функции: `ssc-gen check -f json` / `ssc-gen generate -f json`.
