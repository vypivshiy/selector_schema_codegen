# 0003: Audit and Document Traversal Engine and Target Backends

**Type**: `wayfinder:grilling` (HITL)  
**Status**: Closed  
**Blocked by**: None  
**Part of**: [Documentation and Codebase Audit Map](map.md)

## Question
Как устроены контракты расширения генераторов кода: диспетчеризация `BaseWalker`, состояние `WalkContext`, аккумуляция в `ModuleBuilder` и интерфейсы стратегий `DomSpelling` и `HttpLibStrategy` для Python, JavaScript и Go?

## Target Scope
- `ssc_codegen/traversal/walker.py` (`BaseWalker`, 3 режима обхода)
- `ssc_codegen/traversal/context.py` (`WalkContext`)
- `ssc_codegen/traversal/utils.py`
- `ssc_codegen/generation/builder.py` (`ModuleBuilder`)
- `ssc_codegen/generation/runtime.py` (рантайм-сборка)
- `ssc_codegen/targets/python/` (`PythonVisitor`, `DomSpelling` bs4/lxml/parsel/slax, `HttpLibStrategy` httpx/aiohttp/requests)
- `ssc_codegen/targets/javascript/` (`JsVisitor`, `JsHttpLibStrategy` fetch/axios)
- `ssc_codegen/targets/golang/` (`GoVisitor`, REST generator)

## Resolution
1. **Ядро обхода и 3 режима диспетчеризации (`BaseWalker`)**:
   - Зафиксирована закрытая таблица `_DISPATCH` и трехрежимный обход дочерних узлов в `walk_children`:
     - *Container* (`JsonDef`, `TypeDef`, `StructBase`, `Init`): глубина `depth+1`, `index=0`, сиблинги не инкрементируют индекс.
     - *Pipeline* (`Field`, `FunctionDef`, `InitField`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `Table*`): глубина `depth+1`, последовательный инкремент индекса (`ctx.advance()`) после каждого шага с пробросом `Fallback`-ветвей.
     - *Predicate* (`Filter`, `Assert`, `Match`, `Logic*`): глубина `depth+1`, `index=0`, инкремент между предикатными условиями.
2. **Контекст обхода (`WalkContext`) и аккумулятор (`ModuleBuilder`)**:
   - Добавлены Google-style docstrings с `Attributes:`, примерами и аннотациями для всех методов (`prv`/`nxt`, `advance()`, `deeper()`, `reset_index()`).
   - `ModuleBuilder` задокументирован как идемпотентный язык-независимый аккумулятор импортов, стандартных хелперов (`require_std`) и рантайм-расширений (`require_runtime`).
3. **Инвариант генерации Runtime-хелперов в Go**:
   - Зафиксировано, что в Go-бэкенде все хелперы (`stdFallback`, `std_unescape_text`, REST runtime) **всегда** генерируются в единый `sscgen_runtime.go` в пределах того же пакета (`package main`), исключая коллизии повторного объявления символов (`redeclared in this block`) при компиляции нескольких файлов.
4. **Контракт интерфейса `DomSpelling`**:
   - `DomSpelling` в Python строго разделяет методы выражений (`list[str]`) и предикатов (`str`), а также флаг `supports_xpath: bool` для декларации возможностей парсеров (`lxml`/`parsel` = `True`, `bs4`/`slax` = `False`).
   - Все 4 реализации (`Bs4DomSpelling`, `LxmlDomSpelling`, `ParselDomSpelling`, `SlaxDomSpelling`) снабжены Google-style docstrings.
5. **Транспортная модель `HttpLibStrategy`**:
   - Специфицированы контракты сетевых клиентов для Python (`HttpxStrategy`, `AioHttpStrategy`, `RequestsStrategy`), JS (`FetchStrategy`, `AxiosStrategy`) и Go (`NetHttpStrategy`).
   - Стратегия зафиксирована как единый источник правды для импортов, типов клиентов, `ssc_rest_call` и `MethodFetch`.
6. **Двухпроходная кодогенерация (Two-pass codegen)**:
   - В `docs/maintainers/converters.md` подробно описан жизненный цикл двухпроходного обхода (Pass 1 — discovery, Pass 2 — emission).
7. **Сборка API Reference**:
   - Обновлены и валидированы `docs/api/traversal.md` и `docs/api/targets.md`. Сборка `mkdocs build` проходит чисто без предупреждений.
