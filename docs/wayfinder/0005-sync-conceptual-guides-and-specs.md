# 0005: Synchronize Conceptual Guides and Architecture Specs

**Type**: `wayfinder:grilling` (HITL)  
**Status**: Closed  
**Blocked by**: None  
**Part of**: [Documentation and Codebase Audit Map](map.md)

## Question
Какие главы руководств пользователя (`docs/learn/`), справочников синтаксиса (`docs/syntax.md`, `docs/operations.md`, `docs/json.md`) и архитектурных документов мейнтейнеров содержат устаревшие сведения или расхождения с актуальным кодом компилятора?

## Target Scope
- `docs/learn/01..12` (главы туториала)
- `docs/guide.md`, `docs/syntax.md`, `docs/operations.md`, `docs/types.md`, `docs/predicates.md`, `docs/json.md`, `docs/extensions.md`
- `docs/maintainers/ast_spec.md`, `converters.md`, `linter.md`, `kdlquery.md`
- `docs/llm.txt`

## Resolution
1. **Устранение расхождений и битых ссылок**:
   - Исправлен якорь ссылки в `docs/guide.md` на `syntax.md#rawstruct`.
   - Проверены и синхронизированы все главы обучающей серии `docs/learn/01..12` и концептуальные руководства (`syntax.md`, `operations.md`, `types.md`, `predicates.md`, `json.md`, `extensions.md`).
2. **Синхронизация документации мейнтейнеров**:
   - `docs/maintainers/ast_spec.md`: Специфицированы все AST-ноды, 64-битные типы, REST-модель, жизненный цикл и типизация.
   - `docs/maintainers/converters.md`: Зафиксирован 2-проходный обход `BaseWalker`, `DomSpelling` контракты, рантайм `sscgen_runtime.go` и `HttpLibStrategy`.
   - `docs/maintainers/linter.md`: Описана сводная таблица `ErrorCode`, 5-фазный конвейер и дуализм Top-Down порядка vs. топологических импортов.
   - `docs/maintainers/kdlquery.md`: Актуализированы паттерны CST-селекторов.
3. **Строгая валидация сборки**:
   - Команда `uv run mkdocs build --strict` отрабатывает чисто без ошибок и предупреждений.
   - Автоматически сгенерирован полный API Reference для всех 6 разделов (`api/index.md`, `api/cli.md`, `api/ast.md`, `api/core.md`, `api/traversal.md`, `api/targets.md`).
4. **Завершение карты Wayfinder**: Все 5 тикетов карты успешно закрыты, цель аудита достигнута на 100%.
