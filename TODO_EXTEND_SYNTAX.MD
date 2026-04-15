# TODO: Extend DSL Syntax For Request-Aware Codegen

## Goal

Расширить DSL и кодогенерацию так, чтобы схема могла:

- принимать сырой HTTP request или `curl` command через copy-paste;
- поддерживать placeholder'ы `{{param}}`;
- генерировать transport-aware helper поверх текущего `document -> parser`;
- принимать подготовленный пользователем `client`;
- выполнять request, извлекать body и передавать его в текущий parser;
- не ломать старые `.kdl` схемы и не раздувать DSL лишними магическими блоками.

Ключевая идея: не заменять текущий вход `document`, а добавить поверх него опциональный transport layer.

---

## Non-Goals

Следующее **не входит** в scope данного расширения:

- Auth / session management;
- Rate limiting / retries / backoff;
- Connection pooling;
- Cookie jar management;
- Proxy configuration;
- Captcha / anti-bot bypass;
- Browser automation (рассмотреть отдельно в будущем);
- Multi-step workflows (CSRF token fetch → POST);
- Client lifecycle management.

Всё перечисленное — ответственность пользовательского client/adapter.

---

## Current State

Сейчас проект ориентирован на `document string` или DOM-like object:

- Python targets генерируют `__init__(document)` и парсят HTML/string.
- JS target генерирует `constructor(document)`.
- Go target тоже принимает `document string`.

Это значит, что лучший путь расширения:

- оставить текущий parser API как low-level слой;
- поверх него опционально сгенерировать classmethod вида `fetch(client, **params)`;
- транспорт описывать декларативно в DSL.

---

## High-Level Design

### Main principle

Один новый магический блок:

- `@request`

Без дополнительных `@prepare`, `@flow`, `@response`, `@http`, `@fetch`, `@browser` и т.д. на первом этапе, чтобы не плодить магические методы.

### Runtime model

Считать, что:

- пользователь сам подготовил `client`;
- пользователь сам настроил auth/session/proxy/cookies/retries;
- генератор не управляет жизненным циклом клиента;
- генератор только:
  - собирает request из template + `**params`;
  - вызывает клиент;
  - достаёт body;
  - передаёт его в parser.

### Pipeline order

Полный порядок выполнения при наличии `@request`:

```
@request → fetch → extract body → @pre-validate → @split-doc → fields
```

`@pre-validate` валидирует уже полученный document, не transport.

---

## Proposed DSL: `@request`

### Syntax

`@request` принимает только multiline string.

Примеры:

```kdl
struct SearchResults type=list {
    @request """
curl 'https://example.com/search?q={{query}}&page={{page}}' \
  -H 'User-Agent: {{user_agent}}' \
  -H 'X-Api-Key: {{api_key}}'
"""

    @split-doc { css-all ".result" }
    title { css ".title"; text }
}
```

```kdl
struct SearchResults type=list {
    @request """
POST https://example.com/search?q={{query}} HTTP/1.1
Host: example.com
User-Agent: {{user_agent}}
Cookie: session={{session}}
Content-Type: application/json

{"filters": {{filters_json}}, "limit": {{limit}}}
"""
}
```

### Auto-detection

Никакого `mode="curl"` или `mode="raw-http"` не добавлять.

Формат определять автоматически:

- если первая значимая часть строки начинается с `curl ` -> parse as curl;
- если первая строка похожа на `METHOD SP URI SP HTTP/` -> parse as raw HTTP;
- иначе lint error: unsupported `@request` payload format.

### Placeholders

Placeholder syntax:

- `{{name}}`

Все placeholder'ы в v1 считаются **строковыми** (`str`). Типизация placeholder'ов не входит в v1.

Назначение placeholder'ов:

- URL path/query params;
- headers;
- cookies;
- form body;
- JSON body;
- raw body chunks.

### Internal normalized form

После парсинга `@request` компилируется во внутренний `RequestSpec`, примерно такой:

- `method`
- `url`
- `headers`
- `cookies`
- `query`
- `body_kind` = `empty | form | json | raw`
- `body_template`
- `placeholders`

Эта структура внутренняя, в DSL не светится.

### Method inference

- Если в curl нет `-X`/`-d`/`--data`/`--json`, а в raw HTTP method = `GET` — `body_kind = empty`.
- `GET` с body технически допустим по RFC, но в v1 считается lint warning.

---

## Generated Runtime API

### Public API

Не плодить много runtime методов.

Минимальный набор:

- сохранить текущий `__init__(document)` или аналог в target'е;
- добавить `fetch(cls, client, **params)`.

Идея:

```python
class SearchResults:
    def __init__(self, document): ...

    @classmethod
    def fetch(cls, client, **params): ...
```

`fetch`:

1. Собирает request template.
2. Вызывает подготовленный клиент.
3. Извлекает body.
4. Передаёт итоговый document в обычный parser path.

### Async support

Если target-библиотека поддерживает async (например `httpx`, `aiohttp`), генерировать `async` вариант:

```python
class SearchResults:
    def __init__(self, document): ...

    @classmethod
    async def fetch(cls, client, **params): ...
```

Библиотеки без async-поддержки (например `requests`) генерируют sync-вариант.

Решение sync/async принимается на уровне конкретного converter target, не в DSL.

### Error handling

Transport-ошибки (HTTP 4xx/5xx, network timeout, connection error) **не обрабатываются** генерированным кодом. Исключения пробрасываются as-is. Это ответственность пользовательского client.

> **Open question:** стоит ли рассмотреть генерацию monad-like обёртки (Result/Either) вместо исключений для transport layer? Это позволило бы отделить transport errors от parse errors на уровне типов. Отложено на будущее.

---

## Client Contract

### Plain HTTP mode

Для `@request` generated code должен ожидать, что клиент умеет нечто совместимое с:

```python
client.request(method, url, headers=..., cookies=..., params=..., data=..., json=...)
```

Сильно привязываться к `requests`/`httpx` внутри DSL не нужно.

### Why not encode backend client in DSL

Не зашивать `requests`, `httpx`, `aiohttp` или другие backend-specific особенности в саму схему.

Причины:

- проще backport;
- меньше platform lock-in;
- DSL остаётся transport-declarative, а не library-specific;
- adapter можно выбирать отдельно в кодогенераторе позже, если понадобится.

---

## JSON Responses And SSR HTML Fragments

### Problem

Ответ не всегда plain HTML.

В реальных SSR/API сценариях сервер может вернуть:

- plain HTML;
- JSON, внутри которого лежит HTML string;
- JSON, внутри которого лежит список HTML fragment'ов;
- JSON с mixed payload, где HTML хранится по path.

### Design conclusion

Нельзя жёстко делить `@request` на "HTML request" и "JSON request".

Лучше дать `@request` возможность указать, где находится итоговый document.

### Recommended extension

Не добавлять отдельный `@response` block на первом этапе.

Если нужно поддержать JSON -> HTML extraction, использовать свойства у `@request`:

- `response-path="payload.html"`
- `response-join=""`

Примеры:

```kdl
struct SearchResults type=list {
    @request response-path="payload.html" """
curl 'https://example.com/api/search?q={{query}}'
"""

    @split-doc { css-all ".result" }
    title { css ".title"; text }
}
```

```kdl
struct SearchResults type=list {
    @request response-path="fragments" response-join="" """
curl 'https://example.com/api/search?q={{query}}'
"""

    @split-doc { css-all ".result" }
}
```

### `response-path` syntax

`response-path` использует **dot-notation для JSON keys**. Это не JSONPath и не jmespath.

Поддерживается:

```
response-path="payload.html"        # obj["payload"]["html"]
response-path="data.fragments"      # obj["data"]["fragments"]
response-path="result.content"      # obj["result"]["content"]
```

**Не поддерживается** в v1:

- Array indexing: `data.items[0]`
- Wildcards: `data.*.html`
- Filters: `data[?active]`

### Runtime semantics

If `response-path` is not set:

- use `response.text` as document.

If `response-path` is set:

1. call `response.json()`;
2. resolve path по dot-notation;
3. if result is `str` -> use as document;
4. if result is `list[str]` -> join with `response-join`;
5. otherwise raise runtime error.

---

## Reusable Request Templates (future)

В текущем DSL уже есть механизм `define`. В будущем можно переиспользовать его для request templates:

```kdl
define SEARCH-API """
curl 'https://example.com/search?q={{query}}'
"""

struct SearchResults type=list {
    @request SEARCH-API

    @split-doc { css-all ".result" }
    title { css ".title"; text }
}

struct SearchMeta type=item {
    @request SEARCH-API

    total { css ".total"; text; to-int }
}
```

Это позволит избежать дублирования `@request` для нескольких struct'ов, работающих с одним endpoint. Реализация — после стабилизации `@request`.

---

## Linter Rules To Add

### For `@request`

- `@request` string must be non-empty.
- payload must be autodetected as either `curl` or raw HTTP.
- all placeholders must be valid identifiers.
- unresolved placeholder duplicates are allowed, but names must be consistent.
- malformed raw HTTP request -> lint error.
- malformed curl parse -> lint error.
- invalid `response-path` syntax -> lint error (only dot-notation).
- `GET` with body -> lint warning.

### For parser compatibility

- old schemas without `@request` must continue to work unchanged.

---

## AST / Parser Direction

### Likely new AST nodes

At minimum:

- `RequestConfig`

### Parser integration

Текущий parser уже умеет регистрировать новые struct-level nodes, так что расширение логично делать именно там.

Подход:

- `@request` парсится как struct node;
- хранит raw payload string;
- опционально хранит `response-path`, `response-join`;
- transport normalization (curl parse / raw HTTP parse → `RequestSpec`) происходит после parsing или в converter stage.

---

## Codegen Direction

### Python targets first

Самый разумный rollout:

1. Implement in Python converters first:
   - `py-bs4`
   - `py-lxml`
   - `py-parsel`
   - `py-slax`
2. Only later consider JS / Go support.

### Generated behavior

For structs without `@request`:

- keep current output unchanged.

For structs with `@request`:

- keep current `__init__(document)`;
- add `fetch(cls, client, **params)`;
- sync or async depending on target library capabilities.

### Important boundary

Generated code should not own:

- client initialization;
- auth setup;
- captcha solving;
- retries/backoff policy;
- proxy/session management;
- error handling for transport errors.

All of that belongs to the user-provided client.

---

## Suggested Implementation Phases

### Phase 1

- Add AST support for `@request`.
- Add parser support for raw multiline payload.
- Add curl/raw HTTP autodetection.
- Add placeholder extraction.
- Add internal `RequestSpec`.
- Generate `fetch(cls, client, **params)` for Python backends.
- Support plain `response.text`.

### Phase 2

- Add `response-path` and `response-join` support.
- Support JSON responses containing HTML strings/fragments.

### Phase 3

- Support `define` for reusable request templates.
- Add async variant generation for async-capable targets.

---

## Open Questions

1. Стоит ли генерировать monad-like обёртку (Result/Either) для разделения transport errors и parse errors на уровне типов?
2. Should `response-path` live as `@request` property, or stay out of v1?
3. Do we want one generic Python client contract only, or optional adapters later?
4. Should malformed placeholders inside JSON body be validated structurally, or only textually in v1?
5. Нужно ли поддерживать `define` для request templates в v1, или отложить?

---

## Recommended Final Direction For V1

If prioritizing simplicity and backport-friendliness:

- Add `@request """..."""` with autodetect curl/raw HTTP.
- Support `{{param}}` placeholders (all treated as strings).
- Generate `fetch(cls, client, **params)` — sync or async per target.
- Assume client is user-prepared.
- Keep existing `__init__(document)` unchanged.
- Do not handle transport errors — propagate as-is.
- Add optional `response-path` (dot-notation only) and `response-join` on `@request`.
- Delay browser support, multi-step workflows, placeholder typing.

This gives the project a useful transport layer without collapsing the DSL into a full HTTP client framework.
