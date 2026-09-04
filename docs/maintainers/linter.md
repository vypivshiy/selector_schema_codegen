# Линтер: как добавлять правила и семантические проверки

**Аудитория:** мейнтейнеры  
**Последнее обновление:** 2026-09-04  

Линтер интегрирован в парсер `core/` — отдельного модуля `linter/` больше нет.
Валидация происходит в едином конвейере вместе с построением AST.

## Где находится код

Каталог: `ssc_codegen/core/`

Ключевые файлы:
- `reader.py` — публичный API: `parse_module(src, source_path)` возвращает `(Module, list[ReadDiagnostic])`. Оркестрирует 5 проходов компилятора.
- `contexts.py` — `ParseContext`, `LintContext`, `ErrorCode`, `WalkCtx`, `DefineKind`, `DefineInfo`.
- `linter.py` — структурная валидация KDL-узлов: `lint_module`, `lint_cross_refs`, плюс per-op проверки (`lint_pipeline_op`, `lint_predicate_op`, `lint_validate_regex`, `lint_validate_css`, `lint_validate_xpath`, …).
- `type_checking.py` — `OpSig`, `check_pipeline_types`, вывод и совместимость типов.
- `expressions.py` — парсинг pipeline-операций в AST + `typedef_from_struct` (генерация `TypeDef` из struct).
- `predicates.py` — парсинг предикатов (`filter`/`assert`/`match` + `not/and/or`).
- `struct_parser.py` — разбор тела struct, fn и json.
- `module_handler.py` — `handle_define`, `handle_json`, `handle_struct`, `handle_function`.
- `imports.py` — mandatory typed imports, `SymbolId`, `SourceUnit`, private scopes и dependency closure.
- `extensions.py` — `extension` declarations и signature resolution.
- `rest_artifacts.py` — синтез REST-result узлов (`ResultVariantDef`, `ResultAliasDef`, `MatcherListDef`) из `StructRest`.
- `format.py` — `format_diagnostics(...)` (Rust-style text + JSON).

KDL-парсер — внешний: `kdlquery` (`KDLParseError`, `KdlNode`, `ReadDiagnostic`, `Severity`, `Span`).
Селекторы kdlquery — отдельный документ: [kdlquery.md](kdlquery.md).

## Модель выполнения (5 проходов в `parse_module`)

1. **KDL parse** — `kdlquery.parse(src)`. Синтаксические ошибки оборачиваются в `ReadDiagnostic` с `code=ErrorCode.SYNTAX_ERROR` (`"E000"`).
2. **resolve_imports** — source-scoped symbol graph; explicit roots + private closure превращаются в topo-sorted top-level nodes.
3. **lint_module** — структурная валидация текущего файла (top-level decls, struct bodies, json children, @request placeholders, field names, top-down local order).
4. **lint_cross_refs** — cross-file проверки: ссылки на define/json/struct, циклы, unknown ops, multi-target symbol collision checks.
5. **build Module AST** — `handle_define` / `handle_extension` → `handle_json` / `handle_struct` → synthetic artifacts → diagnostics merged.

Типы pipeline'а выводятся во время AST-сборки через `check_pipeline_types` (`type_checking.py`).

## Дуализм разрешения типов (Top-Down Order vs Topological Import Closure)

В компиляторе действуют два взаимодополняющих инварианта:

1. **Top-Down Declaration Order (в пределах одного файла)**:
   - Внутри одного `.kdl` файла зависимые типы (`nested <Struct>`, ссылки на `json <Type>`) должны объявляться строго **выше** потребителей (helpers first, entrypoint last).
   - Нарушение порядка немедленно диагностируется линтером как `ErrorCode.INVALID_DECLARATION_ORDER` (`E302`).
2. **Topological Dependency Closure (при межфайловых импортах)**:
   - При использовании `import "./path.kdl" { (struct)Helper }` модуль `core/imports.py` строит ориентированный граф зависимостей символов.
   - Зависимости автоматически топологически сортируются и помещаются перед ссылающимися нодами в результирующем плоском списке, исключая необходимость ручной сортировки импортов.

## Сводная таблица кодов ошибок (`ErrorCode`)

| Код | Константа `ErrorCode` | Категория | Описание |
|---|---|---|---|
| `E000` | `SYNTAX_ERROR` | Синтаксис | Ошибка парсинга KDL синтаксиса |
| `E001` | `INVALID_ARGUMENT_COUNT` | Аргументы | Неверное количество позиционных аргументов директивы/операции |
| `E002` | `INVALID_ARGUMENT_VALUE` | Аргументы | Невалидное значение аргумента (некорректный regex, CSS, XPath, HTTP-статус) |
| `E003` | `INVALID_IMPORT` | Импорты | Ошибка в пути или сигнатуре импорта, циклический импорт |
| `E040` | `MALFORMED_DOTPATH` | JSON | Некорректный dot-path (напр. ведущая/висячая точка или `..`) |
| `E041` | `DUPLICATE_JSON_KEY` | JSON | Коллизия имен ключей источника или псевдонимов |
| `E100` | `TYPE_MISMATCH` | Типы | Несовместимость типов в pipeline или fallback ветке |
| `E200` | `UNKNOWN_NODE` | Грамматика | Неизвестная нода верхнего уровня или операция pipeline |
| `E203` | `DISALLOWED_DIRECTIVE` | Грамматика | Директива не разрешена в данном контексте (напр. `@init` внутри `fn`) |
| `E300` | `UNDEFINED_SYMBOL` | Символы | Ссылка на необъявленный struct, json, define или extension |
| `E301` | `UNDEFINED_INIT_FIELD` | Символы | Ссылка на необъявленное поле `@init` через `@<field>` |
| `E302` | `INVALID_DECLARATION_ORDER` | Порядок | Локальный тип объявлен ниже точки первого использования |
| `E400` | `INVALID_TYPE_DECLARATION` | Модель AST | Неизвестный тип struct или невалидная сигнатура расширения |
| `E401` | `MISSING_REQUIRED_FIELD` | Модель AST | Отсутствуют обязательные директивы структуры (`@split-doc`, `@request` и др.) |
| `E402` | `DUPLICATE_DECLARATION` | Символы | Дублирование имен объявлений или коллизия в целевом языке |
| `E403` | `INVALID_IDENTIFIER` | Идентификаторы | Имя символа не образует валидный идентификатор в целевом языке |
| `W011` | `DEPRECATED_JSON_ALIAS` | Предупреждение | Устаревший позиционный псевдоним JSON (рекомендуется `from="..."`) |
| `W040` | `WHITESPACE_IN_PATH` | Предупреждение | Пробельные символы в начале или конце пути `from` |

## Diagnostic API

Линтер не использует registry/decorators. Каждая функция принимает `LintContext`
и складывает диагностики в `ctx.diagnostics` через `ctx.error(...)` или `ctx.warning(...)`:

```python
from ssc_codegen.core.contexts import LintContext, ErrorCode

def my_check(node, lint: LintContext) -> None:
    if not _is_valid(node):
        lint.error(
            node,
            code=ErrorCode.INVALID_ARGUMENT_COUNT,   # "E001"
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
| @request placeholders | `linter.py` | `_lint_request_placeholders` |

## Валидаторы аргументов

В `linter.py` реализованы стандартные хелперы:

- `lint_require_args(node, lint, exact=..., min_count=..., max_count=...)`
- `lint_require_int_args(node, lint, args)`
- `lint_require_predicate_ctx(node, lint)` — для предикатов вне filter/assert/match
- `lint_require_assert_ctx(node, lint)` — для `len-*`, `re-any`, `re-all`, `gt/lt/ge/le`

## Форматирование вывода

```python
from ssc_codegen.core import format_diagnostics, format_diagnostic
# Rust-style text
text = format_diagnostics(errs, filepath=path, fmt="text")
# JSON (для LLM-pipelines и инструментов автоматизации)
js = format_diagnostics(errs, filepath=path, fmt="json")
```

CLI использует те же функции: `ssc-gen check -f json` / `ssc-gen generate -f json`.
