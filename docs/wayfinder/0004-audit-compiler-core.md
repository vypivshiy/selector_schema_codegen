# 0004: Audit and Document Compiler Core, Linter, and Semantic Passes

**Type**: `wayfinder:grilling` (HITL)  
**Status**: Closed  
**Blocked by**: None  
**Part of**: [Documentation and Codebase Audit Map](map.md)

## Question
Как описать семантические правила валидации, проходы линтера, вывод типов в конвейерах и фазы парсинга KDL в AST, чтобы выявить любые скрытые предположения или невалидируемые краевые случаи?

## Target Scope
- `ssc_codegen/core/reader.py` (`parse_module`, фазы ридера)
- `ssc_codegen/core/contexts.py` (`ParseContext`, `LintContext`, `WalkCtx`, `ErrorCode`)
- `ssc_codegen/core/linter.py` (правила структурного, символьного и селекторного линтинга)
- `ssc_codegen/core/type_checking.py` (вывод типов в pipeline и предикатах)
- `ssc_codegen/core/expressions.py` & `predicates.py` (парсинг операций)
- `ssc_codegen/core/struct_parser.py` (парсинг тел структур)
- `ssc_codegen/core/module_handler.py`, `imports.py`, `extensions.py`, `rest_artifacts.py`
- `ssc_codegen/core/format.py` (форматирование диагностики)

## Resolution
1. **Канонический `ErrorCode` и стандартизация кодов**: В `ssc_codegen/core/contexts.py` добавлен `class ErrorCode(str, Enum)` с исчерпывающим описанием всех диагностических кодов (`E000`–`E403`, `W011`, `W040`) и обратной совместимостью со строковыми аргументами `kdlquery.ReadDiagnostic`.
2. **Google-style docstrings для всего ядра компилятора (`core/`)**: Все 12 модулей подсистемы `ssc_codegen.core` снабжены полными Google-style docstrings с секциями `Args:`, `Returns:`, `Raises:`, `Attributes:` без дублирования типов из аннотаций.
3. **Дуализм разрешения типов**:
   - В пределах одного файла зафиксировано строгое правило **Top-Down Declaration Order** (`ErrorCode.INVALID_DECLARATION_ORDER` / `E302`): хелперы и зависимые типы объявляются строго выше потребителей.
   - Для межфайловых импортов зафиксирован контракт **Topological Dependency Closure** в `core/imports.py`: граф зависимостей транзитивно строится и автоматически сортируется.
4. **Синтез REST-артефактов в API Reference**: В `docs/api/core.md` добавлена секция `## REST Artifact Synthesis` (`::: ssc_codegen.core.rest_artifacts`), полностью документирующая генерацию `ResultVariantDef`, `ResultAliasDef` и `MatcherListDef`.
5. **Актуализация руководства мейнтейнеров**: Обновлен `docs/maintainers/linter.md` со сводной таблицей кодов ошибок `ErrorCode`, 5-фазным конвейером `parse_module` и описанием точек расширения правил.
6. **Валидация сборки**: `uv run mkdocs build` проходит чисто без предупреждений Griffe, typecheck `uv run mypy ssc_codegen/` и `uv run ruff check` завершаются без ошибок.
