# REST API support — `struct type=rest`

Проектирование и план внедрения поддержки чистых JSON REST API эндпоинтов в DSL.

## Мотивация

Сейчас DSL покрывает только HTML парсинг (CSS/XPath → DOCUMENT). JSON поддерживается частично: `json` блоки + `jsonify` работают только когда JSON вложен в HTML документ. Чисто JSON REST API (`GET /api/x → {...}`) требуют костылей (`struct { data { raw; jsonify Schema } }`).

Цель: first-class поддержка REST API без изобретения нового OpenAPI. Миграция из swagger (mitmproxy2swagger output) должна быть механической.

## Дизайн

### Новый `type=rest` для `struct`

Один `struct type=rest` = один сгенерированный класс-клиент с методами. Каждый `@request` внутри — метод класса.

```kdl
json Article {
    id    int
    title str
    url   str
}

json ArticleList array=#true { (array)Article }

json User {
    id       int
    username str
    role     str
}

json ApiError {
    error      str
    error_code int
}

struct ArticlesAPI type=rest {
    @doc "sample docstring for API client class"

    @request name=articles response=ArticleList doc="fetch articles by id" """
    GET /articles/{{id}} HTTP/2
    Host: api.example.com
    Authorization: Bearer {{token}}
    """

    @request name=user-get response=User doc="fetch user by id" """
    curl https://api.example.com/user/get/{{id}}
    """

    @request name=user-delete doc="delete user (no response body)" """
    DELETE /user/{{id}} HTTP/2
    Host: api.example.com
    """

    @error 404 ApiError
    @error 500 ApiError
    @error 200 field="error_code" ApiError
}
```

Генерируется (Python, упрощённо):
```python
class ArticlesAPI:
    """sample docstring for API client class"""

    def articles(self, id: str, token: str) -> ArticleList: ...
    def user_get(self, id: str) -> User: ...
    def user_delete(self, id: str) -> None: ...
```

Семантика:
- `type=rest` — новый вариант `StructType` (рядом с `ITEM|LIST|DICT|TABLE|FLAT`)
- Тело struct содержит **только** директивы: `@doc`, `@request`, `@error` — никаких полей и пайплайнов
- `@request` получает новые атрибуты:
  - `name=<identifier>` — имя метода. Обязателен если в struct > 1 `@request`. Для одного `@request` можно опустить → метод называется `fetch()`
  - `response=<JsonSchema>` — имя json-схемы для 2xx ответа. Опционален; отсутствие → метод возвращает `None`/`void`
  - `doc="..."` — docstring метода. Опционален. Поддерживает `define`
  - Основной аргумент — raw HTTP или curl c `{{placeholders}}` (как сейчас)
  - Все строковые аргументы (`doc=`, тело) поддерживают `define`
- `@error <status> [field="<name>"] <JsonSchema>` — **struct-level**, применяется ко всем `@request` внутри. 0+ директив
- `@doc` — docstring класса (опционален)

### Почему именно так

- **Один struct = один класс** — естественное группирование эндпоинтов одного API. Меньше шума в файле
- **`response=` как атрибут** — схема ответа co-located с запросом, легче читать "что возвращает этот метод"
- **`@error` struct-level** — DRY для типичного кейса (все эндпоинты API имеют общую `ApiError` схему для одних и тех же статусов). Если endpoint уникален по ошибкам — выноси в отдельный struct
- **Reference по имени, не inline** — переиспользование схем, консистентность с `jsonify Schema`
- **Errors → exceptions, не union** — идиоматично в Python/JS/Go, `fetch()` возвращает чистый `ArticleList`
- **Нет `status` поля** — статус это транспорт, не данные; если API кладёт `status` в body — это обычное поле json схемы
- **Нет новых top-level keyword'ов** — переиспользование `struct` ортогонально `type=`

### Naming convention для методов

`name=` в KDL — kebab-case или snake-case идентификатор. Трансформация при кодогенерации:
- Python: `user-get` → `user_get()`
- JS/TS: `user-get` → `userGet()`
- Go: `user-get` → `UserGet()`

При одном `@request` без `name=` генерируется метод `fetch()` / `Fetch()`.

### Ошибки в body при 2xx статусе

Некоторые API всегда возвращают `200 OK`, а факт ошибки сигнализируют полем в теле (`{"error_code": 42, "error": "..."}`). Status-based роутинг не работает — нужен дискриминатор по body.

Синтаксис:
```kdl
@error <status> [field="<name>"] <Schema>
```

- `field="error_code"` — если поле присутствует в body, ответ трактуется как ошибка схемы `Schema`
- Без `field=` — чистый status-based матчинг
- Несколько `@error 200 field="..."` с разными полями допустимы — проверка по порядку объявления, первый подошедший выигрывает
- `@error 200 <Schema>` без `field=` запрещён линтером (иначе любой 200 всегда ошибка)

Рантайм (в порядке проверок):
1. HTTP status non-2xx → ищем `@error <status>` без `field=` → десериализация → `raise RestApiError(status, payload)`
2. 2xx → парсим body, проверяем `@error <status> field="..."` по порядку: если поле присутствует → десериализация по error-схеме → `raise RestApiError`
3. Иначе → десериализация по `response=` схеме (или `None` если `response=` не задан)
4. Если для non-2xx статуса нет `@error` — поднять generic `HTTPError`

MVP — только проверка присутствия поля (`field in body`). Сравнение значений — extension.

### Что НЕ входит в MVP

- `oneOf`/`allOf`/`discriminator` в json schemas — реальные mitm2swagger выводы этого почти не содержат
- Auth как first-class директива — пока через header placeholder `{{token}}`
- Polymorphic responses (union на одном статусе) — не встречается в практике RE API
- Множественные content-types / negotiation — игнорируется, подразумевается `application/json`
- Response headers extraction (`Location`, pagination cursors) — extension
- Per-request `@error` override — всё struct-level
- Типизация request body (`@body Schema`) — сейчас body внутри raw HTTP payload с `{{placeholders}}` достаточно

## План реализации

### Этап 1. AST и парсер

**Файлы:** `ssc_codegen/ast/struct.py`, `ssc_codegen/ast/types.py`, `ssc_codegen/parser.py`

- [ ] Добавить `StructType.REST` в `types.py`
- [ ] Расширить существующий `Request` node: `response_schema: str | None = None`, `doc: str = ""`
- [ ] Новый node `ErrorResponse(Node)`: `status: int`, `schema_name: str`, `discriminator_field: str | None = None`
- [ ] Поддержать синтаксис `struct X type=rest` в парсере KDL
- [ ] Парсить атрибуты `@request name=... response=... doc="..."` внутри `type=rest` struct
- [ ] Парсить `@error <int> [field="<name>"] <Name>` на struct-level
- [ ] Резолвить имя схемы в ссылку на `JsonStruct` (переиспользовать механизм из `jsonify`)
- [ ] Все строковые атрибуты `@request` и `@error` поддерживают `define`
- [ ] Property `Struct.errors: list[ErrorResponse]`, `Struct.requests: list[Request]`

### Этап 2. Линтер

**Файл:** `ssc_codegen/linter/rules_struct.py`

- [ ] `type=rest` требует минимум один `@request`
- [ ] Все `name=` в `@request` уникальны внутри struct
- [ ] `name=` обязателен если `@request` больше одного; можно опустить если ровно один
- [ ] `response=<Name>` ссылается на существующий `json` блок
- [ ] `@error` запрещён вне `type=rest`
- [ ] Поля/пайплайны (`Field`, `SplitDoc`, `Key`, etc.) запрещены в `type=rest`
- [ ] `@error <status>` — `status` в диапазоне `[100, 599]`
- [ ] `@error` уникален по паре `(status, field)` — `field=None` и `field="x"` считаются разными
- [ ] `@error <2xx>` без `field="..."` запрещён (иначе любой успешный ответ → ошибка)
- [ ] `@error <status> field="..."` — `field` непустая строка
- [ ] `@error` ссылается на существующий `json` блок

### Этап 3. Конвертеры

**Файлы:** `ssc_codegen/converters/py_bs4.py`, `ssc_codegen/converters/js_pure.py`, остальные по мере готовности

- [ ] Генератор для `type=rest`:
  - Struct → класс `<StructName>` (literal — как named в KDL)
  - Каждый `@request` → метод (sync + async вариант)
  - Имя метода: `name=` → snake_case/camelCase по target-language convention; без `name=` (одиночный endpoint) → `fetch`/`Fetch`
  - Возвращаемый тип: `response=<Schema>` → тип `Schema`; отсутствие `response=` → `None`/`void`
  - `doc=` → docstring метода; `@doc` на struct → docstring класса
  - Десериализация: `json.loads(response.text)` → маппинг на схему (переиспользовать логику `jsonify`)
  - Роутинг ответа:
    1. non-2xx → ищем `@error <status>` без `field=` → десериализация → `raise RestApiError(status, payload)`
    2. 2xx с `response=` → для всех `@error <status> field="..."` по порядку: если поле в body → ошибка
    3. Иначе → десериализация по `response=` (либо `return None` если `response=` нет)
  - Если для non-2xx статуса нет `@error` — поднять generic `HTTPError`
- [ ] НЕТ генерации parse/parse-методов (struct пустой со стороны HTML пайплайна)
- [ ] Поддержать все `--http-client` варианты (requests/httpx, fetch/axios)

### Этап 4. Документация

- [ ] Новый файл `docs/learn/11-rest-api.md` — полный гайд
- [ ] Обновить `docs/syntax.md` — синтаксис `type=rest`, атрибуты `@request`, `@error`
- [ ] Обновить `docs/llm.txt` и корневой `llm.txt`
- [ ] Обновить `.agents/skills/kdl-schema-dsl/SKILL.md` + references
- [ ] Пример в `examples/` — небольшой REST API (animevost как кандидат: 3 эндпоинта, минимум схем)

### Этап 5. Тесты

- [ ] Unit: parser парсит `type=rest` + все атрибуты `@request`
- [ ] Unit: линтер ловит все запрещённые комбинации
- [ ] Integration: codegen для Python (requests + httpx) и JS (fetch + axios)
- [ ] E2E: сгенерированный клиент обращается к локальному mock-серверу и получает типизированный ответ

## Extensions (после MVP)

Не входит в первую итерацию, откладываем до появления реальных кейсов.

### Response headers extraction

Критично для RE: `Location` при создании, `X-Total-Count`/`Link` для пагинации, rate-limit headers.

```kdl
@request name=create-article response=Article response-header="Location:location_url" """..."""
```

Генератор добавляет `location_url: str` в возвращаемый объект либо оборачивает в `RestResponse[T]{body, headers}`.

### Per-request `@error` override

Если один метод API имеет специфические коды ошибок, отличные от остальных. MVP решает это выделением в отдельный struct. Extension — `@error name=<request-name> <status> <Schema>`.

### Typed request body

```kdl
@request name=create response=Article body=CreateArticleRequest """POST /articles HTTP/2..."""
```

Автосериализация при вызове `fetch(body=CreateArticleRequest{...})`. Сейчас достаточно raw payload с `{{placeholders}}`.

### Query array parameters

mitm2swagger часто выводит `?genres[]=1&genres[]=2`. Варианты:
- Placeholder синтаксис: `{{genres[]}}` — генератор разворачивает массив (`bracket`, `csv`, `repeat`)
- Modifier: `{{genres|bracket-array}}`

Решение — после замера реальных кейсов.

### Enum типы в `json`

```kdl
json Status enum=#true { "ongoing" "released" "announced" }
json Anime { status Status }
```

Сейчас `status str` работает без валидации и без генерации enum-классов.

### Auth как first-class

```kdl
auth BearerJWT header="Authorization" prefix="Bearer "
struct ArticlesAPI type=rest auth=BearerJWT { ... }
```

Чище чем manual `{{token}}` в каждом `@request`. Усложняет DSL — оправдано только при feedback'е о боли.

### Value-based error discriminator

Сейчас `field="x"` — только проверка присутствия. Extension: `field="x" value="ERR"` — сравнение значения.

## Миграция со swagger

Отдельная задача, **не блокирует** реализацию DSL. Пишется после того как `type=rest` работает.

### Инструмент `swagger2kdl`

```
input:  mitmproxy2swagger output (OpenAPI 3.x YAML)
output: N .kdl файлов (группировка endpoints по path-prefix → один struct)

этапы:
  1. components/schemas → json blocks (BFS по $ref, топологическая сортировка)
  2. paths.*.* → @request внутри struct type=rest
     - method + path + headers → raw HTTP payload
     - parameters (path/query/header) → {{placeholders}}
     - requestBody → тело HTTP
     - responses.2xx.schema → response=<Name>
     - responses.4xx/5xx.schema → @error <status> <Name> (struct-level, merge по группе)
  3. securitySchemes → header-инъекция в raw HTTP (Bearer/ApiKey)
```

`swagger2kdl` должен быть тупым транслятором без "умных" решений — иначе ручная правка после первого запуска ломается при повторном. Идемпотентность: либо диффать, либо генерить в `raw/` и мёрджить вручную первый раз.

### Pipeline

```
HAR/mitm flow  →  mitmproxy2swagger  →  swagger2kdl  →  ssc_codegen  →  Python/JS клиент
```

Детерминированный путь, без LLM в критической цепочке.

## Открытые вопросы

1. **Inline-пайплайн для response?** Если API оборачивает payload в `{data: [...], meta: {...}}` — `response-path="data"` в `@request` уже решает. Инлайн-пайплайн (`response={ jsonify ArticleList }`) не нужен?
2. **Множественные 2xx.** OpenAPI позволяет 200 + 201 + 204 с разными схемами. В практике RE API — редкость, игнорируем в MVP.
3. **Пагинация-курсор в body.** Частый паттерн: `{items: [...], next_cursor: "..."}`. Решение: wrapper-схема (`PaginatedArticles {items:[Article], next_cursor:str}`), пагинация — на клиенте. DSL описывает один запрос, не logic layer.
4. **Void-метод и `@error 2xx field=...`** — если `response=` опущен, стоит ли всё равно проверять `@error` с дискриминатором? Пока — **да**, проверяем; если совпало → `raise`, иначе → `return None`.

## Статус

- [ ] Этап 1: AST + парсер
- [ ] Этап 2: линтер
- [ ] Этап 3: конвертеры (py_bs4, js_pure)
- [ ] Этап 4: документация
- [ ] Этап 5: тесты
- [ ] Extensions (по feedback)
- [ ] swagger2kdl (отдельная задача)
