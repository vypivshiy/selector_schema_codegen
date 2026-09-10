# Конвертеры: как писать новый backend

**Назначение:** архитектура и контракт кодогенератора  
**Спецификация всех AST-узлов с примерами:** [ast_spec.md](ast_spec.md)  
**Последнее обновление:** 2026-09-04  

Конвертер принимает `Module` AST (`ssc_codegen.ast`) и генерирует исходный
код для целевого runtime. Текущая архитектура:

```
traversal/    — language-agnostic обход AST (BaseWalker, WalkContext, utils)
generation/   — data accumulator (ModuleBuilder) + runtime-file assembly
targets/      — бэкенды (python, javascript, golang) + resolver & profiles
```

## Основной контракт

```
KDL schema -> kdlquery -> core/reader -> Module AST -> BaseWalker -> output source
```

Конвертер отвечает за:
- рендеринг импортов и std-helper'ов из `ModuleBuilder`;
- объявления классов / структур / TypedDict / JSDoc;
- реализацию pipeline операций (выражения);
- реализацию предикатов (фильтры, ассерты, матчинг);
- вызовы `nested` / `jsonify` / JSON allowlist проекции;
- интеграцию с DOM API (через `DomSpelling` в Python, DOM API в JS, `goquery` в Go, `dom_query` в Rust);
- интеграцию с HTTP-клиентом (через `HttpLibStrategy` в Python, `JsHttpLibStrategy` в JS, `GoHttpLibStrategy` в Go);
- генерацию REST-result типов (`Ok`, `Err<Status>`, `UnknownErr`, `TransportErr`).

Конвертер НЕ отвечает за:
- парсинг KDL (`kdlquery`);
- семантическую валидацию и типы (`core/`);
- lint diagnostics.

## Базовые классы и ядро обхода

`ssc_codegen/traversal/`:
- `context.py` — `WalkContext` (immutable):
  - `index`: текущий индекс шага pipeline (`0, 1, 2, ...`);
  - `depth`: уровень вложенности отступов;
  - `var_name`: префикс переменных (по умолчанию `"v"`);
  - `indent_char`: единица отступа (4 пробела для Python, 2 для JS, `\t` для Go);
  - `prv` / `nxt`: имена входной (`v`, `v1`) и выходной (`v1`, `v2`) переменных;
  - `advance()`, `advance_n(n)`, `deeper()`, `reset_index()`.
- `walker.py` — `BaseWalker`:
  - Централизованная таблица `_DISPATCH` сопоставляет типы AST-нод с методами `visit_*`.
  - Метод `walk(node, ctx)` вызывает обработчик и нормализует результат в `list[str]`.
  - Метод `walk_children(node, ctx)` реализует 3 режима обхода в зависимости от категории узла:
    1. **Container** (`JsonDef`, `TypeDef`, `StructBase`, `Init`): `depth + 1`, `index = 0`, сиблинги не инкрементируют индекс.
    2. **Pipeline** (`Field`, `FunctionDef`, `InitField`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `Table*`): делегирует в `walk_pipeline` с инкрементом индекса (`ctx.advance()`) после каждого шага.
    3. **Predicate** (`Filter`, `Assert`, `Match`, `Logic*`): `depth + 1`, `index = 0`, индекс инкрементируется между предикатными условиями.
  - Специальная обработка `Fallback`: узел `Fallback` самостоятельно обходит свое тело через `walk_pipeline`, а внешний контекст сдвигается на количество узлов тела на глубине `depth + 1` для синхронизации нумерации переменных.
- `utils.py` — утилиты анализа AST: `module_has_rest`, `module_uses_http`, `module_is_rest_only`, `module_has_html_struct`, `module_is_extension_only`, `err_subclass_name`, `dict_needs_builder`, `find_predicate_container`, `find_enclosing_module`, `resolve_json_def`, `jsonify_path_to_segments`, `json_def_descriptors`, `json_def_mapping`.

`ssc_codegen/generation/`:
- `builder.py` — `ModuleBuilder` (чистый аккумулятор данных):
  - `require_import(line)`: идемпотентная регистрация импортов с сохранением порядка.
  - `require_std(name, *, code, imports)`: регистрация стандартных вспомогательных функций.
  - `require_runtime(name, *, code, imports)`: регистрация пользовательских хелперов расширений (с валидацией конфликтов).
- `runtime.py` — генерация отдельного рантайм-модуля для `-R` / `--separate-runtime`.

## Архитектура бэкендов

### 1. Python (`ssc_codegen/targets/python/`)
- `PythonVisitor(BaseWalker)`: генерирует типизированный код Python 3.10+.
- `DomSpelling(ABC)` (`html_libs/base.py`):
  - Методы выражений (`css_select`, `text`, `attr`, `raw`, `to_bool`) возвращают `list[str]` (готовые строки кода).
  - Методы предикатов (`pred_css`, `pred_xpath`, `pred_has_attr` и др.) возвращают `str` (фрагмент булева выражения).
  - Реализации: `Bs4DomSpelling`, `LxmlDomSpelling`, `ParselDomSpelling`, `SlaxDomSpelling`.
  - Флаг `supports_xpath: bool` объявляет нативную поддержку XPath (`lxml`, `parsel` = `True`).
- `HttpLibStrategy(ABC)` (`http_libs/base.py`):
  - `HttpxStrategy`: полнофункциональный sync (`httpx.Client`) и async (`httpx.AsyncClient`), ловит `httpx.HTTPError`.
  - `AioHttpStrategy`: async-only (`aiohttp.ClientSession`), `supports_sync_fetch = False`, ловит `aiohttp.ClientError`.
  - `RequestsStrategy`: sync (`requests.Session`), `async_fetch_delegates_to_sync = True` (делегирует в `run_in_executor`), ловит `requests.RequestException`.

### 2. JavaScript (`ssc_codegen/targets/javascript/`)
- `JsVisitor(BaseWalker)`: генерирует чистый ES6+ код с JSDoc-аннотациями типов.
- Нативная работа со стандартным DOM API (`querySelector`, `querySelectorAll`, `textContent`, `getAttribute`).
- `JsHttpLibStrategy(ABC)` (`http_libs/base.py`):
  - `FetchStrategy`: глобальный `fetch`.
  - `AxiosStrategy`: библиотека `axios`.

### 3. Go (`ssc_codegen/targets/golang/`)
- `GoVisitor(BaseWalker)`: генерирует код на Go 1.26+ с generics и автоформатированием через `gofmt`.
- DOM API реализован через библиотеку `goquery`.
- **Инвариант генерации Runtime-хелперов**: все хелперы (`stdFallback`, `std_unescape_text`, REST runtime) **всегда** генерируются в `sscgen_runtime.go` в пределах того же пакета (`package main`), исключая ошибки `redeclared in this block` при наличии нескольких файлов в пакете.
- `GoHttpLibStrategy(ABC)` (`http_libs/base.py`):
   - `NetHttpStrategy`: стандартная библиотека `net/http` (`*http.Client`).

### 4. Rust (`ssc_codegen/targets/rust/`)
- `RustVisitor(BaseWalker)` генерирует owned-парсеры с `Result<_, SscError>`.
- DOM хранится в `Rc<RefCell<Document>>`, а selection/cache handles представлены
  стабильными `dom_query::NodeId`; это поддерживает nested-парсеры и detached cache
  без self-referential структур.
- Общий соседний модуль `sscgen_runtime.rs` содержит DOM, Unicode, regex и JSON helpers.
- Первая версия намеренно отклоняет XPath, `@request` и REST с диагностикой генерации.
- Cargo-зависимости: `dom_query = "0.28"`, `regex`, `serde` с feature `derive`, `serde_json`.

## Two-pass сборка (Two-pass codegen)

Метод `convert_all` в `PythonVisitor`, `JsVisitor`, `GoVisitor` и `RustVisitor` выполняет обход в два прохода:
1. **Pass 1 (Discovery)**: холостой проход по AST для регистрации всех необходимых импортов, стандартных хелперов и рантайм-функций в `ModuleBuilder`.
2. **Pass 2 (Emission)**: генерация финального исходного кода с уже сформированным заголовком модуля и импортами.

## Подключение нового бэкенда

1. Создать `targets/<lang>/visitor.py` с классом-наследником `BaseWalker`.
2. Реализовать методы `visit_*` (таблица `BaseWalker._DISPATCH` сопоставит их по типам AST-нод).
3. При необходимости реализовать сетевые стратегии `HttpLibStrategy` и DOM-адаптеры.
4. Зарегистрировать цель в `targets/resolver.py` и описать профиль в `targets/profile.py`.
