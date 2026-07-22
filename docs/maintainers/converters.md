# Конвертеры: как писать новый backend

**Назначение:** архитектура и контракт кодогенератора
**Последнее обновление:** 2026-07-21

Конвертер принимает `Module` AST (`ssc_codegen.ast`) и генерирует исходный
код для целевого runtime. Текущая архитектура:

```
traversal/    — language-agnostic обход AST (BaseWalker)
generation/   — data accumulator (ModuleBuilder) + runtime-file assembly
targets/      — бэкенды (python, javascript) + resolver
```

## Основной контракт

```
KDL schema -> kdlquery -> core/reader -> Module AST -> BaseWalker -> output source
```

Конвертер отвечает за:
- рендеринг импортов и std-helper'ов из `ModuleBuilder`;
- объявления классов/TypedDict/JSDoc;
- реализацию pipeline операций (выражения);
- реализацию предикатов;
- вызовы `nested` / `jsonify`;
- интеграцию с DOM API (через `DomSpelling`);
- интеграцию с HTTP-клиентом (через `HttpLibStrategy`);
- REST-result типы (`Ok`, `Err<Status>`, `UnknownErr`, `TransportErr`).

Конвертер НЕ отвечает за:
- парсинг KDL (`kdlquery`);
- семантическую валидацию и типы (`core/`);
- lint diagnostics.

## Базовые классы

`ssc_codegen/traversal/`:
- `context.py` — `WalkContext` (immutable): `var_name`, `indent_char`,
  `meta`, `index`, `depth`, `prv`/`nxt`, `advance()`, `deeper()`,
  `reset_index()`.
- `walker.py` — `BaseWalker` (dispatch table `visit_*` через `walk()`),
  методы `walk`, `walk_children`, `walk_pipeline`. Три режима обхода тела:
  container / pipeline / predicate. Никакой кодогенерации здесь.
- `utils.py` — `module_has_rest`, `module_is_rest_only`, `err_subclass_name`,
  `dict_needs_builder`, `find_predicate_container`, `dict_entry_placeholder`,
  `jsonify_path_to_segments`.

`ssc_codegen/generation/`:
- `builder.py` — `ModuleBuilder` (pure data): `require_import(line)`,
  `require_std(name, ...)`, idempotent. Без рендеринга.
- `runtime.py` — `register_runtime_file(...)` для `-R` / `--separate-runtime`.

## Подключение бэкенда

1. Создать `targets/<lang>/visitor.py` с классом-наследником `BaseWalker`.
2. Реализовать `visit_*` методы (dispatch tablewalker'а их подберёт по
   имени класса AST-узла).
3. (Python) Реализовать или переиспользовать `DomSpelling` (data + поведение
   под HTML-библиотеку).
4. (REST) Реализовать или переиспользовать `HttpLibStrategy` для клиента.
5. Зарегистрировать в `targets/resolver.py` (фабрика `create_converter`).

Пример — `targets/python/visitor.py` (`PythonVisitor(BaseWalker)`) принимает
`dom_spelling_cls` в конструкторе; одного класса хватает для всех четырёх
HTML-библиотек (bs4/lxml/parsel/slax) — различия инкапсулированы в
`DomSpelling`.

## Модель обхода

Типы узлов, которые различает `BaseWalker`:

- **Контейнеры**: Module, Struct, StructRest, Init, json-defs, typedefs.
  Обход углубляется, индекс pipeline сбрасывается.
- **Pipeline-узлы**: Field, InitFieldCall, SplitDoc, Key, Value, Table*,
  CheckMethod, MethodRest. Обработчик делегирует в `walk_pipeline(...)`.
- **Предикаты**: Filter, Assert, Match и логические контейнеры not/and/or.
  Делегируют в `walk_predicate(...)`.

`WalkContext.prv` — входное значение текущего pipeline-шага; `WalkContext.nxt` —
выходное. Индекс увеличивается через `ctx.advance()` после каждого выражения.

## ModuleBuilder

`ModuleBuilder` заменяет старые скрытые пулы сигналов: регистрация идиомпотентна,
target-specific код решает, в каком виде рендерить.

```python
from ssc_codegen.generation.builder import ModuleBuilder

builder = ModuleBuilder()
builder.require_import("import bs4")
builder.require_std("ssc_assert", lines=["def ssc_assert(...): ..."], imports=["..."])
```

## DomSpelling (Python)

`ssc_codegen/targets/python/html_libs/`:
- `base.py` — `DomSpelling(ABC)`: методы выражений возвращают `list[str]`,
  методы предикатов возвращают `str`.
- `bs4.py`, `lxml.py`, `parsel.py`, `slax.py` — конкретные реализации.

Новый HTML-backend = новый класс `DomSpelling` + регистрация в `resolver.py`.

## HttpLibStrategy (REST transport)

`ssc_codegen/targets/python/http_libs/` и `ssc_codegen/targets/javascript/http_libs/`:
- Python: `httpx.py`, `aiohttp.py`, `requests.py` (`HttpLibStrategy(ABC)` в `base.py`).
- JS: `fetch.py`, `axios.py` (`JsHttpLibStrategy(ABC)` в `base.py`).

Стратегия владеет: import-line, sync/async client type, transport exception,
REST runtime source.

Python: `PythonVisitor.http_strategy_for(http_client)` — single source of truth,
используется и `convert_all`, и `main.py` (для threading'а стратегии в
`register_runtime_file`, чтобы `except <lib>.<Exc>` клауза в runtime-файле
совпадала с импортами parser-файла).

## TargetSpec → TargetProfile

`targets/spec.py` (`TargetSpec`) — raw user input (`lang`, `lib`,
`http_client`, `separate_runtime`).
`targets/profile.py` (`TargetProfile`) — resolved capabilities + `create_converter`
factory.
`targets/resolver.py` (`resolve(TargetSpec) -> TargetProfile`) — валидирует ввод
и возвращает профиль. Никаких статических enum-маппингов в `main.py`.

## Two-pass codegen

`convert_all` в `PythonVisitor` / `JsVisitor` запускает `_walk_module` дважды:
1. Pass 1 — собирает std/import registrations в `ModuleBuilder`.
2. Pass 2 — emits output.

Это позволяет избежать forward-reference'ов при рендере.
