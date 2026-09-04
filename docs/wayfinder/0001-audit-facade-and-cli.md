# 0001: Audit and Document Public Facade and CLI

**Type**: `wayfinder:grilling` (HITL)  
**Status**: Closed  
**Blocked by**: None  
**Part of**: [Documentation and Codebase Audit Map](map.md)

## Question
Как точно специфицировать и задокументировать публичный интерфейс библиотеки и команды CLI, и какие расхождения есть между CLI флагами (`ssc-gen`), резолвером целей (`resolve`) и документацией?

## Target Scope
- `ssc_codegen/__init__.py` (`parse_module`, `resolve`, `TargetSpec`, `TargetProfile`, `check_struct_health`, `run_scout`, `run_discover` etc.)
- `ssc_codegen/main.py` (команды `generate`, `check`, `run`, `health`, `scout`, `discover`, `version`)
- `ssc_codegen/targets/spec.py` (`TargetSpec`)
- `ssc_codegen/targets/profile.py` (`TargetProfile`)
- `ssc_codegen/targets/resolver.py` (`resolve`, `ResolutionError`)
- `ssc_codegen/exceptions.py` (`ParseError`, `BuildTimeError`)
- `ssc_codegen/health.py` (`check_struct_health`, `HealthResult`, `SelectorCheck`)
- `ssc_codegen/explore.py` (`run_scout`, `run_discover`, `ScoutResult`, `DiscoverResult`)
- `ssc_codegen/core/reader.py` (`parse_module`)
- `ssc_codegen/core/format.py` (`format_diagnostics`)

## Resolution
1. **Расширенный публичный фасад**: В `ssc_codegen/__init__.py` добавлен полный публичный фасад с явным `__all__` и модульным docstring, экспортирующий `parse_module`, `resolve`, `TargetSpec`, `TargetProfile`, `ResolutionError`, `ParseError`, `BuildTimeError`, `format_diagnostics`, `check_struct_health`, `HealthResult`, `run_scout`, `run_discover`, `ScoutResult`, `DiscoverResult`.
2. **Строгая валидация целей (`resolve`)**: Сохранено строгое именование языков (`"python"`, `"javascript"`/`"js"`, `"go"`) и валидация взаимоисключающих флагов (например, запрет `--lib` для JS и Go, запрет `--http-client` для Go).
3. **Разделение ответственности**: `TargetSpec` зафиксирован как спецификатор целевой платформы и конвертера для `resolve()`, в то время как параметры файловой компоновки (`package`, `runtime_name`, `skip_lint`) передаются напрямую на этапе сборки/генерации.
4. **Стандарт документации**: Все публичные функции, классы и CLI-хелперы снабжены Google-style docstrings с секциями `Args`, `Returns`, `Raises`, `Attributes` и практическими блоками `Examples:`.
5. **Валидация MkDocs**: Обновлена страница `docs/api/index.md`, генерация API Reference через `mkdocs build` проходит чисто.
