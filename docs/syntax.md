# KDL Schema DSL — Syntax Reference

> **Version:** 2.1
> **Last Updated:** 2026-03-21

Полное руководство по синтаксису KDL Schema DSL для определения структур извлечения данных из HTML/XML документов.

---

## Table of Contents

- [Overview](#overview)
- [Module Level](#module-level)
  - [import](#import)
  - [@doc](#doc)
  - [define](#define)
  - [json](#json-mappings)
  - [transform](#transform)
  - [dsl](#dsl)
  - [struct](#struct)
- [Struct Types](#struct-types)
- [Special Fields](#special-fields)
- [Regular Fields](#regular-fields)
- [Pipeline](#pipeline)

---

## Overview

KDL Schema DSL - это декларативный язык для описания структур извлечения данных из HTML/XML документов. Компилируется в код на Python (BeautifulSoup4, lxml, parsel, selectolax) и JavaScript.

**Основные концепции:**
- **Module** - файл с определениями: imports, defines, json, transforms, structs
- **Struct** - структура данных с полями
- **Field** - поле с pipeline операций
- **Pipeline** - последовательность операций извлечения и трансформации

---

## Module Level

Модуль (файл `.kdl`) может содержать следующие объявления верхнего уровня:

```kdl
import "./shared.kdl"

@doc "Module description"

define BASE-URL="https://example.com"
define EXTRACT { css ".x"; text }

json Schema { field str }

transform my-fn accept=STRING return=STRING {
    py { code "{{NXT}} = {{PRV}}.upper()" }
}

dsl my-dsl lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

struct MyStruct type=item { ... }
```

---

### import

Импорт определений из других файлов:

```kdl
import "./shared_defines.kdl"
import "./shared_struct.kdl"
```

**Особенности:**
- Импортируются `define`, `transform`, `dsl`, `json`, `struct` определения
- Пути относительные от текущего файла
- Поддерживается транзитивный импорт
- Обнаружение циклических импортов

---

### @doc

Документирование модуля и структур:

```kdl
@doc """
Example parser for quotes.toscrape.com

Usage:
    GET https://quotes.toscrape.com/js/
"""

struct Main {
    @doc "Extract quotes from JSON embedded in HTML"
    // fields...
}
```

- Документация переносится в сгенерированный код
- Поддерживает многострочные строки

---

### define

Определение констант и блочных выражений для переиспользования.

#### Скалярные define

```kdl
// Строки
define BASE-URL="https://example.com"

// Шаблоны с placeholder {{}}
define FMT-URL="https://books.toscrape.com/catalogue/{{}}"

// Regex patterns (с VERBOSE флагом)
define JSON-PATTERN=#"""
(?xs)
    var\s+data\s*=\s*     # START ANCHOR
    (
        \[                # START ARRAY
        .*                # JSON DATA
        \]                # END ARRAY
    )
    ;\s+for              # END ANCHOR
"""#
```

Скалярные define подставляются как значения аргументов:

```kdl
field {
    css "a"
    attr "href"
    fmt FMT-URL     // подставляется значение FMT-URL
    re JSON-PATTERN // подставляется regex
}
```

#### Блочные define

```kdl
define EXTRACT-HREF {
    css "a"
    attr "href"
}

define REPL-RATING {
    repl {
        One "1"
        Two "2"
        Three "3"
        Four "4"
        Five "5"
    }
}
```

Блочные define вызываются как операции в pipeline или через `expr`:

```kdl
field {
    EXTRACT-HREF       // раскрывается в: css "a"; attr "href"
    trim
}

// или
field {
    expr EXTRACT-HREF  // то же самое, явный вызов
    trim
}

rating {
    css ".star-rating"
    attr "class"
    REPL-RATING        // блочный define с repl
    to-int
}
```

**Типизация блочных define:**
- Тип вычисляется автоматически из содержимого
- Поддерживается цепочка define (один define вызывает другой)
- Обнаружение циклических ссылок

---

### JSON Mappings

Определение структур для десериализации JSON:

```kdl
// Простая структура
json Author {
    name str
    goodreads_links str
    slug str
}

// Массив с вложенными структурами
json Quote array=#true {
    tags (array)str        // Массив строк
    author Author          // Вложенная структура
    text str
}
```

**Синтаксис:**
- `json <Name> { ... }` - определение схемы
- `array=#true` - маркер массива верхнего уровня
- `(array)type` - маркер массива для поля
- Ссылки на другие JSON структуры по имени

**Использование с `jsonify`:**

```kdl
struct Main {
    @init {
        data { raw; re JSON-PATTERN }
    }

    all-quotes {
        @data
        jsonify Quote              // Применить схему Quote
    }

    first-quote {
        @data
        jsonify Quote path="0"     // Первый элемент массива
    }

    author-slug {
        @data
        jsonify Quote path="2.author.slug"  // Навигация по вложенным полям
    }
}
```

**path навигация:**
- `""` - применить схему к результату
- `"0"`, `"1"` - индекс в массиве
- `"field"` - доступ к полю
- `"0.author.slug"` - комбинация

---

### transform

Пользовательские функции трансформации с мультиязычной поддержкой:

```kdl
transform to-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = str(b64decode({{PRV}}))"
    }
    js {
        import "const atob = require('atob')"
        code "{{NXT}} = atob({{PRV}})"
    }
}
```

**Свойства:**
- `accept` - входной тип (обязательно, AUTO не допускается)
- `return` - выходной тип (обязательно, AUTO не допускается)

**Языковые блоки:**
- `py { ... }`, `js { ... }`, `go { ... }`, `lua { ... }` и т.д.
- `import "..."` - добавляется в секцию импортов (опционально)
- `code "..."` - код трансформации (обязательно, может быть несколько строк)

**Маркеры:**
- `{{PRV}}` - предыдущее значение в pipeline (вход)
- `{{NXT}}` - следующее значение (выход/результат)

**Использование:**

```kdl
struct Main {
    title {
        css "title"
        text
        transform to-base64
    }
}
```

---

### dsl

Именованные инлайн-блоки кода для одного языка. Упрощённая альтернатива `transform`:

```kdl
dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

dsl decode-b64 lang=py accept=STRING return=STRING {
    import "from base64 import b64decode"
    code "{{NXT}} = b64decode({{PRV}}).decode()"
}
```

**Свойства:**
- `lang` - язык реализации (обязательно): `py`, `js`, `go`, `lua`, ...
- `accept` - входной тип (опционально)
- `return` - выходной тип (опционально)

**Дочерние элементы:**
- `import "..."` - импорты (опционально, может быть несколько)
- `code "..." "..." ...` - строки кода (обязательно, минимум одна)

**Использование через `expr`:**

```kdl
struct Main {
    title {
        css "title"
        text
        expr upper-py    // вызвать dsl блок
    }
}
```

**Отличия от transform:**

| | transform | dsl |
|---|---|---|
| Мультиязычность | Да (py, js, ...) | Один язык |
| accept/return | Обязательно | Опционально |
| Вызов | `transform NAME` | `expr NAME` |

---

### struct

Основная единица - структура данных:

```kdl
struct <Name> type=<StructType> {
    // special fields
    @doc "..."
    @init { ... }
    @pre-validate { ... }
    @split-doc { ... }
    @key { ... }
    @value { ... }
    @table { ... }
    @rows { ... }
    @match { ... }

    // regular fields
    field-name { ... }
}
```

---

## Struct Types

### `type=item` (default)

Извлечение одного объекта:

```kdl
struct Article {
    title { css "h1"; text }
    author { css ".author"; text }
}
```

**Результат:** `{"title": "...", "author": "..."}`

---

### `type=list`

Извлечение списка объектов. Требуется `@split-doc`.

```kdl
struct Book type=list {
    @split-doc { css-all ".book-card" }

    name { css ".title"; text }
    price { css ".price"; text; re #"(\d+\.?\d*)"#; to-float }
}
```

**Результат:** `[{"name": "...", "price": 9.99}, ...]`

---

### `type=flat`

Плоский список без вложенности. Требуется `@split-doc`.

```kdl
struct Links type=flat {
    @split-doc { css-all "a" }
    url { attr "href" }
}
```

**Результат:** `["url1", "url2", "url3"]`

---

### `type=dict`

Извлечение словаря key-value. Требуется `@split-doc`, `@key`, `@value`.

```kdl
struct MetaOG type=dict {
    @split-doc {
        css-all "meta[property^='og:']"
        match { has-attr "property" "content" }
    }
    @key { attr "property"; rm-prefix "og:" }
    @value { attr "content" }
}
```

**Результат:** `{"title": "...", "description": "...", ...}`

---

### `type=table`

Извлечение данных из HTML таблиц. Требуется `@table`, `@rows`, `@match`, `@value`.

```kdl
struct ProductInfo type=table {
    @table { css "table" }
    @rows { css-all "tr" }
    @match { css "th"; text; trim; lower }
    @value { css "td"; text }

    upc {
        match { eq "upc" }
    }
    price {
        match { starts "price" }
        re #"(\d+\.\d+)"#
        to-float
    }
    is-available {
        match { eq "availability" }
        assert { contains "In stock" }
        to-bool
        fallback #false
    }
}
```

**Результат:** `{"upc": "abc123", "price": 51.77, "is_available": true}`

---

## Special Fields

| Field | Struct Types | Описание |
|-------|-------------|----------|
| `@doc` | все | Документация структуры |
| `@pre-validate` | все | Валидация документа перед парсингом |
| `@init` | все | Предвычисленные (кэшированные) значения |
| `@split-doc` | list, flat, dict | Разбиение на элементы |
| `@key` | dict | Pipeline для извлечения ключа |
| `@value` | dict, table | Pipeline для извлечения значения |
| `@table` | table | Селектор таблицы |
| `@rows` | table | Селектор строк |
| `@match` | table | Pipeline для извлечения ключа из строки |

### @init

Предвычисленные значения, доступные через `@<name>`:

```kdl
struct Main {
    @init {
        raw-json {
            raw
            re JSON-PATTERN
        }
        base-url {
            css "base"
            attr "href"
        }
    }

    data {
        @raw-json          // ссылка на @init поле
        jsonify Quote
    }
}
```

### @pre-validate

Проверка наличия элементов перед парсингом:

```kdl
struct Book type=list {
    @pre-validate {
        assert { css ".product_pod" }
    }
    // ...
}
```

### @split-doc

Разбиение документа на элементы для `list`/`flat`/`dict`:

```kdl
@split-doc { css-all ".book-card" }

// с фильтрацией
@split-doc {
    css-all "a[href]"
    match { attr-starts "href" "https" }
}
```

---

## Regular Fields

Обычные поля с pipeline операций:

```kdl
struct Example {
    // многострочная форма
    title {
        css "h1"
        text
        trim
    }

    // inline форма
    link { css "a"; attr "href" }

    // однострочная (bare) форма
    html { raw }

    // nested
    books { nested Book }
}
```

---

## Pipeline

Каждое поле содержит **pipeline** - последовательность операций:

```
Selector -> Extract -> Transform -> Convert -> Result
```

```kdl
price {
    css ".price"         // DOCUMENT -> DOCUMENT
    text                 // DOCUMENT -> STRING
    trim                 // STRING -> STRING
    re #"(\d+\.\d+)"#   // STRING -> STRING
    to-float             // STRING -> FLOAT
    fallback 0.0         // FLOAT (с fallback)
}
```

Полный список операций см. в [operations.md](operations.md).
Предикаты (filter, assert, match) см. в [predicates.md](predicates.md).
Система типов см. в [types.md](types.md).
