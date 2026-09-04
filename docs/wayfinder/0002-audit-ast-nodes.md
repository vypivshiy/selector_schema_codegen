# 0002: Audit and Document AST Data Model

**Type**: `wayfinder:grilling` (HITL)  
**Status**: Closed  
**Blocked by**: None  
**Part of**: [Documentation and Codebase Audit Map](map.md)

## Question
Каковы точные инварианты и семантика каждого AST-узла промежуточного представления (IR), какие поля являются обязательными/опциональными, и как структурировать атрибуты нод по стандарту Google Style?

## Target Scope
- `ssc_codegen/ast/base.py` (`Node`)
- `ssc_codegen/ast/types.py` (`VariableType`, `StructType`, `TypeInfo`)
- `ssc_codegen/ast/module.py` (`Module`, `Utilities`, `CodeStartHook`, `CodeEndHook`, `Docstring`)
- `ssc_codegen/ast/struct.py` (`StructBase`, `Struct`, `StructRest`, `Field`, `Init`, `InitField`, `InitFieldCall`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `TableConfig`, `TableRows`, `TableMatchKey`, `RequestHttp`, `MethodBase`, `MethodFetch`, `MethodRest`, `ErrorResponse`, `PlaceholderSpec`, `PlaceholderTemplate`, `StartParse`)
- `ssc_codegen/ast/selectors.py` (`CssSelect`, `CssSelectAll`, `XpathSelect`, `XpathSelectAll`, `CssRemove`, `XpathRemove`)
- `ssc_codegen/ast/extract.py` (`Text`, `Raw`, `Attr`)
- `ssc_codegen/ast/string.py` (`Trim`, `Ltrim`, `Rtrim`, `NormalizeSpace`, `RmPrefix`, `RmSuffix`, `RmPrefixSuffix`, `Fmt`, `Repl`, `ReplMap`, `Lower`, `Upper`, `Split`, `Join`, `Unescape`)
- `ssc_codegen/ast/regex.py` (`Re`, `ReAll`, `ReSub`)
- `ssc_codegen/ast/array.py` (`Index`, `Slice`, `Len`, `Unique`)
- `ssc_codegen/ast/cast.py` (`ToInt`, `ToFloat`, `ToBool`, `Jsonify`, `Nested`)
- `ssc_codegen/ast/control.py` (`Self`, `Fallback`, `Return`)
- `ssc_codegen/ast/predicate_containers.py` (`Filter`, `Assert`, `Match`)
- `ssc_codegen/ast/predicate_ops.py` (все предикаты сравнения, строк, regex, DOM, количества, логические связки)
- `ssc_codegen/ast/extension.py` (`ExtensionType`, `ExtensionImport`, `ExtensionHelper`, `ExtensionTarget`, `ExtensionDef`, `ExtensionCall`)
- `ssc_codegen/ast/rest.py` (`ResultVariantDef`, `ResultAliasDef`, `MatcherEntry`, `MatcherListDef`)
- `ssc_codegen/ast/jsondef.py` (`JsonDef`, `JsonDefField`)
- `ssc_codegen/ast/typedef.py` (`TypeDef`, `TypeDefField`)
- `ssc_codegen/ast/function.py` (`FunctionDef`)

## Resolution
1. **Google-style docstrings для всей модели AST**: Все 50+ dataclass-узлов промежуточного представления снабжены полными Google-style docstrings с секциями `Attributes:`, `Args:` и `Returns:`, согласованными со спецификацией типов PEP 484/604 и обогащены примерами трансляции для Python, JavaScript и Go.
2. **Многоуровневая документация (Module docstrings + Class docstrings)**:
   - В заголовках модулей (`struct.py`, `rest.py`, `control.py`, `typedef.py`, `jsondef.py` и др.) описаны концептуальные архитектурные диаграммы, сквозные жизненные циклы (`@init`, `@pre-validate`, REST-синтез, таблицы) и правила именования.
   - В docstrings классов зафиксированы детальные сигнатуры полей, назначение и примеры генерации кода.
3. **Единообразие Deprecation и печать предупреждений**:
   - Во все устаревшие свойства (`Node.ret`, `Node.accept`, `Node.type_info`, `CssSelect.query`, `CssSelectAll.query`, `XpathSelect.query`, `XpathSelectAll.query`, `Module.docstring`, `StructBase.docstring`, узел `Docstring`) добавлен вызов `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
   - Внутренние вызовы в компиляторе переведены на канонические поля (`ret_type_info`, `accept_type_info`, `queries`).
4. **Контекст и генерация runtime helper'а `stdFallback` в Go**:
   - Задокументировано, что для целевых бэкендов без синтаксиса `try/catch` (например, Go) генератор создает generic helper `stdFallback[T any](fn func() T, fallback T) T` с panic recovery через `defer / recover`.
5. **Глубокое раскрытие REST и транспортной модели**:
   - В `ast/rest.py`, `ast/struct.py` и `docs/maintainers/ast_spec.md` полностью специфицирован 5-этапный жизненный цикл REST: KDL-декларация → синтез артефактов в `core/rest_artifacts.py` (`ResultVariantDef`, `ResultAliasDef`, `MatcherListDef`) → шаблонизация плейсхолдеров `PlaceholderSpec` / `PlaceholderTemplate` → стратегии HTTP-транспорта (`httpx`, `aiohttp`, `requests`, `fetch`, `axios`, `net/http`) → сопоставление ошибок и монадический тип `Result[T, E]`.
6. **Соглашения по именованию типов и предотвращению коллизий**:
   - Зафиксированы суффиксы `Type` для синтезированных `TypeDef` (`ProductType`) и `Json` для `JsonDef` (`UserJson`), исключающие затенение классов парсеров.
7. **Обновление спецификации и API Reference**:
   - Актуализирован `docs/maintainers/ast_spec.md` и страница `docs/api/ast.md`.
   - Сборка `mkdocs build` проходит чисто без предупреждений.
