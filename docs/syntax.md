# Синтаксис и структура файла

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

KDL Schema DSL — декларативный язык для описания структур извлечения данных из
HTML/XML. Файл `.kdl` состоит из модульных объявлений и `struct` описаний.

## Базовые понятия

- **Module** — файл с объявлениями `import`, `define`, `json`, `transform`, `dsl`, `struct`.
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
- Импортируются `define`, `transform`, `dsl`, `json`, `struct`.
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

### transform

Мультиязычные трансформации. См. [transforms.md](transforms.md).

### dsl

Именованные inline-блоки кода для одного языка. См. [transforms.md](transforms.md).

### struct

Объявление структуры результата:

```kdl
struct Main type=item {
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

Примечания:
- `flat` собирает строки из полей структуры и удаляет дубли.  
  С `keep-order=#true` порядок первых вхождений сохраняется.
- `dict` использует `@split-doc` для набора элементов, затем `@key`/`@value`.

## Специальные поля

| Поле | Назначение |
|---|---|
| `@doc` | Документация структуры |
| `@pre-validate` | Предварительная валидация документа |
| `@init` | Предвычисление значений (кешируются) |
| `@split-doc` | Разбиение на элементы (`list`, `dict`) |
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

Полный список операций см. в [operations.md](operations.md).
Предикаты см. в [predicates.md](predicates.md).
