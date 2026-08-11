# Синтаксис и структура файла

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-07-21

KDL Schema DSL — декларативный язык для описания структур извлечения данных из
HTML/XML. Файл `.kdl` состоит из модульных объявлений и `struct` описаний.

## Базовые понятия

- **Module** — файл с объявлениями `import`, `define`, `json`, `struct`.
- **Struct** — структура результата.
- **Field** — поле структуры с pipeline операций.
- **Pipeline** — цепочка операций преобразования.

## KDL2 особенности

- Необязательно ставить кавычки вокруг строк без пробелов: `css title`.
- Последняя операция может быть без `;` и обертки в отдельный узел (KDL2 bare).
- Аргументы могут быть строками, числами и спец-литералами `#true`, `#false`, `#null`.

## Объявления модуля

### import

Импортирует определения из другого файла `.kdl`.

```kdl
import "./shared.kdl"
import "./shared.kdl" { Book PriceTransform }
```

Правила:
- Путь всегда указывается как первый аргумент.
- Путь разрешается относительно текущего файла.
- Разрешены селективные импорты через блок `{ Name1 Name2 }`.
- Конфликты имен запрещены.
- Импортируются `define`, `json`, `struct`.
- Импорт транзитивный: если `A` импортирует `B`, а `B` импортирует `C`, то `A` видит `C`.
- Циклические импорты запрещены.
- Импорт работает только при парсинге из файла (нужен путь для резолва).

### Пример импорта

`shared_defines.kdl`:

```kdl
define BASE-URL="https://example.com/{{}}"
define RE-PRICE=#"(\d+\.\d+)"#
```

`main.kdl`:

```kdl
import "./shared_defines.kdl"

struct Page {
    link { css "a"; attr "href"; fmt BASE-URL }
    price { css ".price"; text; re RE-PRICE; to-float }
}
```

Селективный импорт:

```kdl
import "./shared_defines.kdl" { BASE-URL }
```

### @doc

Документация для модуля или структуры:

```kdl
@doc "Parser for books.toscrape.com"

struct Book {
    @doc "Single book card"
    title { css "h3 a"; attr "title" }
}
```

### define

Скалярные и блочные определения для переиспользования.

Скалярный define:

```kdl
define BASE-URL="https://books.toscrape.com/"
define RE-PRICE=#"(\d+(?:\.\d+)?)"#
```

Блочный define:

```kdl
define EXTRACT-HREF {
    css "a"
    attr "href"
}
```

Использование:

```kdl
url { EXTRACT-HREF; rm-prefix "../" }
price { text; re RE-PRICE; to-float }
```

Правила:
- Скалярный define подставляется только в аргументы.
- Блочный define разворачивается как набор операций.
- Скалярный define нельзя использовать как pipeline-операцию.

### json

Объявление JSON схем. См. [json.md](json.md).

### struct

Объявление структуры результата:

```kdl
struct Main {
    title { css "h1"; text }
}
```

Свойства:
- `type=item|list|dict|table|flat` (по умолчанию `item`)
- `keep-order=#true` (только для `type=flat`)

## Типы структур и обязательные поля

| type | Результат | Обязательные поля |
|---|---|---|
| `item` | `dict` | - |
| `list` | `list[dict]` | `@split-doc` |
| `dict` | `dict[str, any]` | `@split-doc`, `@key`, `@value` |
| `table` | `dict` | `@table`, `@rows`, `@match`, `@value` |
| `flat` | `list[str]` | - |
| `raw` | `dict` или `list[dict]` | - |

Примечания:
- `flat` собирает строки из полей структуры и удаляет дубли.  
  С `keep-order=#true` порядок первых вхождений сохраняется.
- `dict` использует `@split-doc` для набора элементов, затем `@key`/`@value`.
- `raw` — парсер простого текста без HTML-бэкенда. Документ — строка `str`,
  поля принимают `STRING` напрямую. ITEM/LIST определяется автоматически:
  `@split-doc` есть → LIST, нет → ITEM. HTML-операции (`css`, `xpath`, `text`,
  `attr`, `raw`) запрещены. Поддерживаются `@request`/`fetch()`, `@init`,
  `@pre-validate`, `@check`.

### fn / (raw)fn

Module-level функция для извлечения одного значения. Генерирует standalone
функцию вместо класса.

```kdl
fn page_title {
    @doc "Extract page title"
    css "h1"
    text
}

(raw)fn csrf_token {
    re { #"name="csrf" value="([^"]+)""# }
}
```

Правила:
- Тело — pipeline операций (как поле `struct`).
- `@doc` поддерживается — генерирует docstring/комментарий.
- Struct-level директивы (`@init`, `@check`, `@pre-validate`, `@split-doc`,
  `@request`, `@error`) **запрещены** — используйте `struct`.
- `(raw)fn` — документ-строка, HTML-операции запрещены (как `(raw)struct`).
- Количество `fn` на модуль — неограничено.
- Возвращаемый тип выводится из pipeline.
- Имя функции конвертируется по конвенции языка:
  Python `snake_case`, JS `camelCase`, Go `PascalCase`.

## Специальные поля

| Поле | Назначение |
|---|---|
| `@doc` | Документация структуры |
| `@request` | Встроенный HTTP конструктор (необязательный) |
| `@pre-validate` | Предварительная валидация документа |
| `@init` | Предвычисление значений (кешируются) |
| `@split-doc` | Разбиение на элементы (`list`, `dict`, `raw` auto-LIST) |
| `@key` | Ключ для `dict` |
| `@value` | Значение для `dict` и `table` |
| `@table` | Селектор таблицы |
| `@rows` | Селектор строк таблицы |
| `@match` | Извлечение ключа строки для сравнения |

### @init и ссылки на него

`@init` позволяет посчитать значение один раз и переиспользовать в полях:

```kdl
struct Main {
    @init {
        raw-json { raw; re JSON-PATTERN }
    }
    data { @raw-json; jsonify Quote }
}
```

Ссылки:
- `@raw-json` — актуальный синтаксис.
- `self raw-json` — старый синтаксис, оставлен для совместимости.

### @pre-validate

```kdl
@pre-validate { assert { css ".product_pod" } }
```

Если условие не выполнено, парсинг прерывается (с учетом `fallback`).

### @value для dict и table

- В `dict` `@value` может возвращать любой тип.
- В `table` `@value` должен возвращать строку. Поля `table` начинают pipeline с `match`.

### @request и per-call kwargs

Сгенерированные методы (`fetch`, `async_fetch`, REST-методы) принимают
дополнительные per-call параметры для передачи headers, cookies, timeout и
т.д. — всё применяется **только к запросу**, объект клиента не мутируется.

| Язык | Сигнатура | Пример вызова |
|---|---|---|
| Python | `**kwargs: Any` | `API.fetch(client, id="42", headers={"Referer": "..."})` |
| JS | `opts = {}` | `API.fetch(client, {id}, {headers: {Referer: "..."}})` |
| Go | `opts ...sscReqOpt` | `NewAPI().Fetch(client, "42", WithHeader("Referer", "..."))` |

**Go нейминг методов**: REST-struct получает пустой маркер + фабрику
`New<Name>()` + receiver-методы (`NewAPI().Fetch(...)`,
`NewAPI().GetUsers(...)` при `@request name=get-users`). HTML+`@request`
генерирует free-function `New<Struct>Fetch(...)` (или `New<Struct><X>`
при `name=X`) — sibling конструктор к `New<Struct>(input)`. Так
несколько схем в одном Go-пакете не конфликтуют именами.

**Shallow-merge**: если DSL задаёт `headers` и пользователь передаёт свои
`headers`, они объединяются (ключи пользователя перезаписывают DSL-ключи).
Неструктивные kwargs (`timeout`, `verify`, ...) заменяются целиком.

## Обычные поля

Формы записи:

```kdl
title {
    css "h1"
    text
    trim
}

link { css "a"; attr "href" }

html { raw }
```

Вложенные структуры:

```kdl
books { nested Book }
```

## Pipeline

Pipeline — это цепочка операций. Начальный тип — `DOCUMENT` (или значение `@init`).

```kdl
price {
    css ".price"
    text
    re #"(\d+\.\d+)"#
    to-float
    fallback 0.0
}
```

### Pattern-matching селекторы

Для `css`, `css-all`, `xpath`, `xpath-all` можно использовать block форму
с несколькими селекторами:

```kdl
title {
    css {
        ".main-title"
        "h1.title"
        "h1"
    }
    text
}
```

Селекторы проверяются по порядку; используется первый непустой результат.
Разрешена только одна форма вызова: либо `css ".title"`, либо `css { ... }`.
Для `css-remove` и `xpath-remove` block форма не поддерживается.

Полный список операций см. в [operations.md](operations.md).
Предикаты см. в [predicates.md](predicates.md).

## (raw)struct — парсинг простого текста

`(raw)struct` предназначен для документов, которые **не являются HTML**:
JavaScript-файлы, URL-строки, текстовые данные, плейлисты, CSV.

### Ключевые отличия от обычного `struct`

| Аспект | `struct` (HTML) | `(raw)struct` |
|---|---|---|
| Тип документа | `DOCUMENT` (DOM) | `STRING` (текст) |
| HTML-парсер | bs4 / lxml / parsel / slax | не используется |
| Первая операция | `css` / `xpath` / `text` / `attr` | `re` / `split` / `fmt` / ... |
| HTML-операции | разрешены | **запрещены** (lint error) |
| `@split-doc` | `DOCUMENT → LIST_DOCUMENT` | `STRING → LIST_STRING` |
| `@request` / `fetch()` | response → HTML | response → raw text |

### Автоопределение ITEM / LIST

- `@split-doc` **отсутствует** → ITEM (один объект `dict`).
- `@split-doc` **присутствует** → LIST (список объектов `list[dict]`).

Явный `type=list` **не нужен**.

### Пример: извлечение из JS

```kdl
(raw)struct PlayerScript {
    @doc "Извлечь URL плейлиста из inline <script>."

    playlist_url {
        re #"Playerjs\([^)]*file:\s*[\"']([^\"']+)[\"']"#
    }
}
```

### Пример: URL query-params

```kdl
(raw)struct AnimeParams {
    dubbing_code {
        split "?"
        index 1
        split "&"
        filter { starts "dubbing_code=" }
        index 0
        rm-prefix "dubbing_code="
    }
}
```

### Пример: текст в строки (auto-LIST)

```kdl
(raw)struct PlaylistLines {
    @split-doc { split "\n" }
    quality { re #"\[(\d+p)\]"# }
    url { re #"\](.+)"# }
}
```

### Пример: fetch удалённого файла

```kdl
(raw)struct RemoteScript {
    @request "curl {{script_url}}"
    file_path { re #"file:\s*[\"']([^\"']+)[\"']"#
}
```

`fetch()` / `async_fetch()` конструируют парсер из тела ответа как raw text.

### Запрещённые операции

В полях `(raw)struct` следующие операции вызовут lint-ошибку:

`css`, `css-all`, `css-remove`, `xpath`, `xpath-all`, `xpath-remove`, `text`,
`attr`, `raw`.

Документ — это строка, не DOM; эти операции не имеют смысла.
