# Documentation and Codebase Audit Map

## Destination
100% покрытие кодовой базы `ssc_codegen` выверенными Google-style docstrings, устранение всех расхождений между фактическим поведением кода и документацией (`docs/learn/`, `docs/maintainers/`, `docs/*.md`), и получение строго валидированного API Reference через `mkdocs build`.

## Notes
- **Domain context**: `CONTEXT.md`, `docs/maintainers/ast_spec.md`, `llm_overview.md`
- **Skills to consult**: `grilling`, `domain-modeling`
- **Docstring Standard**: Google-style docstrings (`Args`, `Returns`, `Raises`, `Yields`, `Attributes`). Без дублирования типов из PEP 484/604 аннотаций.
- **Workflow**: Интерактивный режим (HITL). Сканирование модуля → Выявление спорных контрактов/несостыковок → Интервью с разработчиком → Фиксация docstrings и документации → Проверка `uv run mkdocs build`.

## Decisions so far

- [0001: Audit and Document Public Facade and CLI](0001-audit-facade-and-cli.md): Сформирован расширенный фасад `ssc_codegen`, зафиксирована строгая валидация целей `resolve()` и разделение ответственности с `TargetSpec`, добавлены Google-style docstrings с `Examples` для всех публичных точек входа и обновлен `docs/api/index.md`.
- [0002: Audit and Document AST Data Model](0002-audit-ast-nodes.md): Все 50+ AST-нод снабжены Google-style docstrings с `Attributes:`, примерами трансляции для Python/JS/Go, спецификацией 64-битных типов `INT`/`FLOAT`, адаптацией индексов и PCRE-флагов, типизацией `Literal` и валидацией через `mkdocs build`.
- [0003: Audit and Document Traversal Engine and Target Backends](0003-audit-traversal-and-backends.md): Зафиксирована 3-режимная модель обхода `BaseWalker`, инвариант единого рантайма `sscgen_runtime.go` для Go, контракты `DomSpelling` и транспортные стратегии `HttpLibStrategy`, добавлены Google-style docstrings и обновлен `converters.md`.
- [0004: Audit and Document Compiler Core, Linter, and Semantic Passes](0004-audit-compiler-core.md): Введен формальный `ErrorCode`, задокументированы все модули ядра компилятора (`core/`), зафиксирован дуализм Top-Down порядка и топологического импорта, включен `rest_artifacts` в API Reference и обновлен `linter.md`.
- [0005: Synchronize Conceptual Guides and Architecture Specs](0005-sync-conceptual-guides-and-specs.md): Устранены расхождения в ссылках и примерах, синхронизированы руководства `docs/learn/`, спецификации мейнтейнеров `docs/maintainers/`, справочник `docs/llm.txt` и достигнута безошибочная сборка `mkdocs build --strict`.

## Active Tickets

*(Frontier is clear — all decision tickets resolved)*

## Not yet specified

- Синхронизация `docs/llm.txt` с обновленным контрактом компилятора после аудита Core.
- Добавление автоматизированного правила в CI для валидации ссылок и сборки `mkdocs build --strict`.
- [CLI Backlog] Добавление полных и сокращенных алиасов целевых языков в CLI (`python`/`py`, `javascript`/`js`, `golang`/`go`) с сохранением обратной совместимости CLI.

## Out of scope

- Изменение синтаксиса KDL DSL v2.1 или ломающие архитектурные изменения компилятора.
- Автоматический рефакторинг внутренней реализации без согласования.
