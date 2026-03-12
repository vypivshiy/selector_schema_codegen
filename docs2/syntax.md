# KDL Schema DSL — Syntax Reference

> **Version:** 2.0  
> **Status:** Active Development  
> **Last Updated:** 2026-03-11

Полное руководство по синтаксису KDL Schema DSL для определения структур извлечения данных из HTML/XML документов.

---

## Table of Contents

- [Overview](#overview)
- [Module Level](#module-level)
  - [Documentation](#documentation)
  - [Defines](#defines)
  - [JSON Mappings](#json-mappings)
  - [Transforms](#transforms)
  - [Structs](#structs)
- [Struct Types](#struct-types)
- [Fields](#fields)
- [Special Fields](#special-fields)
- [Selectors](#selectors)
- [Extract Operations](#extract-operations)
- [String Operations](#string-operations)
- [Type Conversions](#type-conversions)
- [Predicates](#predicates)
- [Examples](#examples)

---

## Overview

KDL Schema DSL - это декларативный язык для описания структур извлечения данных из HTML/XML документов. Компилируется в код на Python (BeautifulSoup4, lxml, selectolax) и JavaScript.

**Основные концепции:**
- **Struct** - структура данных с полями
- **Field** - поле с pipeline операций
- **Pipeline** - последовательность операций извлечения и трансформации
- **Selector** - выбор элементов (CSS, XPath)
- **Extract** - извлечение данных (text, attr, raw)
- **Transform** - преобразование данных

---

## Module Level

### Documentation

Документирование модуля и структур:

```kdl
-doc """
Example parser for quotes.toscrape.com

Usage:
    GET https://quotes.toscrape.com/js/
"""

struct Main {
    -doc """
    Extract quotes from JSON embedded in HTML
    
    Returns: List of Quote objects
    """
    // fields...
}
```

**Особенности:**
- Используется синтаксис `-doc` с многострочными строками
- Документация переносится в сгенерированный код
- Поддерживает Markdown форматирование

---

### Defines

Определение констант и переменных для переиспользования:

```kdl
// Простые значения
define BASE-URL="https://example.com"
define MAX-ITEMS=100

// Шаблоны с placeholder {{}}
define FMT-URL="https://books.toscrape.com/catalogue/{{}}"
define FMT-PAGE="https://example.com/page-{{}}.html"

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

// Replacement mappings
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

**Типы defines:**
- `str` - строковые значения
- `int` / `float` - числовые значения
- `Pattern` - regex паттерны (автоматически компилируются)
- `repl` - маппинги для замены

**Особенности VERBOSE regex:**
- Флаг `(?x)` позволяет использовать пробелы и комментарии
- Автоматически конвертируется в inline форму при генерации
- Флаги `(?i)` и `(?s)` встраиваются как `(?is)pattern`

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

**Использование:**

```kdl
struct Main {
    data {
        raw
        re JSON-PATTERN
        jsonify Quote              // Применить схему Quote
    }
    
    first-quote {
        self data
        jsonify Quote path="0"     // Взять первый элемент массива
    }
    
    author-slug {
        self data
        jsonify Quote path="2.author.slug"  // Навигация по вложенным полям
    }
}
```

**path навигация:**
- `""` - применить схему к результату
- `"0"`, `"1"` - индекс в массиве (unwrap)
- `"field"` - доступ к полю
- `"0.author.slug"` - комбинация

---

### Transforms

Пользовательские функции преобразования с мультиязычной поддержкой:

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

transform to-list-base64 accept=LIST_STRING return=LIST_STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = [str(b64decode(i)) for i in {{PRV}}]"
    }
}

transform pow2 accept=INT return=INT {
    py {
        code "{{NXT}} = {{PRV}}**2"
    }
}
```

**Использование:**

```kdl
struct Main {
    titleb64 {
        css "title"
        text
        transform to-base64  // Применить трансформ
    }
    
    urls-count {
        css-all "a"
        len
        transform pow2
    }
}
```

**Особенности:**
- `{{PRV}}` - предыдущее значение в pipeline
- `{{NXT}}` - следующее значение (результат)
- `import` - автоматически добавляется в секцию импортов
- Типизация: `accept` и `return` проверяются в compile-time

---

### Structs

Основная единица - структура данных:

```kdl
struct <Name> type=<StructType> {
    // special fields
    -doc "..."
    -init { ... }
    -split-doc { ... }
    -pre-validate { ... }
    -table { ... }
    -rows { ... }
    -match { ... }
    -value { ... }
    
    // regular fields
    field-name { ... }
}
```

---

## Struct Types

### `type=item` (default)

Извлечение одного объекта:

```kdl
struct MainCatalogue {
    title {
        css "h1"
        text
    }
    description {
        css ".description"
        text
    }
}
```

**Использование:**
```python
parser = MainCatalogue(html)
result = parser.parse()  # -> dict
```

---

### `type=list`

Извлечение списка объектов:

```kdl
struct Book type=list {
    -split-doc { css-all ".book-card" }
    
    name {
        css ".title"
        text
    }
    price {
        css ".price"
        text
        re #"(\d+\.?\d*)"#
        to-float
    }
}
```

**Особенности:**
- Требуется `-split-doc` для разбиения на элементы
- Каждое поле обрабатывает один элемент списка

**Использование:**
```python
parser = Book(html)
result = parser.parse()  # -> List[dict]
```

---

### `type=flat`

Извлечение списка без вложенности (один селектор):

```kdl
struct Links type=flat {
    -split-doc { css-all "a" }
    
    url {
        attr "href"
    }
}
```

**Результат:** `[url1, url2, url3]` вместо `[{url: url1}, {url: url2}, ...]`

---

### `type=table`

Извлечение данных из HTML таблиц:

```kdl
struct ProductInfo type=table {
    -table { css "table" }
    -rows { css-all "tr" }
    -match { css "th"; text; trim; lower }
    -value { css "td"; text }
    
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

**Специальные поля:**
- `-table` - селектор таблицы
- `-rows` - селектор строк
- `-match` - pipeline для извлечения ключа из строки
- `-value` - pipeline для извлечения значения из строки

**Поля:**
- `match { ... }` - предикаты для сопоставления ключа
- После match - обычный pipeline для обработки значения

---

### `type=dict`

Извлечение словаря key-value:

```kdl
struct MetaOpenGraphOther type=dict {
    -split-doc {
        css-all "meta[property^='og:']"
        match { 
            has-attr "property" "content"
        }
    }
    
    -key {
        attr "property"
        rm-prefix "og:"
    }
    
    -value {
        attr "content"
    }
}
```

**Результат:** `{"title": "...", "description": "...", ...}`

**Специальные поля:**
- `-key` - pipeline для извлечения ключа
- `-value` - pipeline для извлечения значения

---

## Fields

Обычные поля с pipeline операций:

```kdl
struct Example {
    field-name {
        // 1. Selector
        css "h1"
        
        // 2. Extract
        text
        
        // 3. Transform
        trim
        upper
        
        // 4. Type conversion
        to-int
        
        // 5. Fallback
        fallback "default"
    }
}
```

**Pipeline выполняется последовательно:**
1. Селекторы - выбор элементов
2. Извлечение - text, attr, raw
3. Трансформации - trim, upper, fmt, re, ...
4. Конвертация типов - to-int, to-float, to-bool
5. Fallback - значение по умолчанию при ошибке

---

## Special Fields

### `-init` - Предвычисленные значения

Кэширование значений для переиспользования:

```kdl
struct Main {
    -init {
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
        self raw-json  // Использование предвычисленного значения
        jsonify Quote
    }
}
```

**Особенности:**
- Вычисляются один раз при инициализации
- Доступны через `self <name>`
- Полезно для дорогих операций

---

### `-pre-validate` - Валидация документа

Проверка наличия ключевых элементов:

```kdl
struct Book type=list {
    -pre-validate {
        assert { css ".col-lg-3 .thumbnail" }
    }
    // fields...
}
```

**Выбрасывает исключение** если элемент не найден.

---

### `-split-doc` - Разбиение на элементы

Для `type=list`, `type=flat`, `type=dict`:

```kdl
struct Book type=list {
    -split-doc { css-all ".book-card" }
    // каждое поле обрабатывает один элемент из списка
}
```

---

## Selectors

### CSS Selectors

```kdl
css ".class"           // Первый элемент
css-all ".class"       // Все элементы
css-rm ".ads"          // Удалить элементы (возвращает текущий doc)
```

**Примеры:**
```kdl
title { css "h1"; text }
links { css-all "a"; attr "href" }
clean-content { css-rm ".ads"; css ".content"; text }
```

---

### XPath Selectors

```kdl
xpath "//div[@class='content']"       // Первый элемент
xpath-all "//a"                        // Все элементы
xpath-rm "//script"                    // Удалить элементы
```

---

## Extract Operations

### `text` - Извлечение текста

```kdl
title { css "h1"; text }
```

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

---

### `attr` - Извлечение атрибутов

```kdl
url { css "a"; attr "href" }
classes { css "div"; attr "class" "data-attr" }  // Конкатенация атрибутов
```

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

---

### `raw` - HTML код

```kdl
html-content { css ".content"; raw }
```

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

---

## String Operations

### `trim` / `ltrim` / `rtrim`

```kdl
text { css "p"; text; trim }
```

---

### `upper` / `lower`

```kdl
tag { css ".tag"; text; lower }
```

---

### `rm-prefix` / `rm-suffix`

```kdl
url {
    css "img"
    attr "src"
    rm-prefix "../"
    ltrim "."
}
```

---

### `fmt` - Форматирование

```kdl
define FMT-URL="https://example.com/{{}}"

url {
    css "a"
    attr "href"
    fmt FMT-URL  // https://example.com/path
}
```

**Placeholder:** `{{}}`

---

### `re` - Regex извлечение

```kdl
price {
    css ".price"
    text
    re #"(\d+\.\d+)"#  // Извлечь первую группу
}
```

**Типы:**
- `STRING → STRING`
- `LIST_STRING → LIST_STRING` (map)

---

### `re-all` - Все совпадения

```kdl
numbers {
    css ".content"
    text
    re-all #"\d+"#  // ["1", "2", "3"]
}
```

**Типы:**
- `STRING → LIST_STRING`

---

### `re-sub` - Замена

```kdl
clean {
    css ".text"
    text
    re-sub #"\s+" " "  // Заменить множественные пробелы
}
```

---

### `repl` - Замена по словарю

```kdl
define REPL-RATING {
    repl {
        One "1"
        Two "2"
        Three "3"
    }
}

rating {
    css ".star-rating"
    attr "class"
    rm-prefix "star-rating "
    REPL-RATING
}
```

---

## Type Conversions

### `to-int` / `to-float` / `to-bool`

```kdl
count { css ".count"; text; to-int }
price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
active { css ".active"; to-bool }  // Наличие элемента → true/false
```

---

### `len` - Длина

```kdl
links-count { css-all "a"; len }  // Количество ссылок
```

**Типы:**
- `LIST_* → INT`
- `STRING → INT`

---

### `fallback` - Значение по умолчанию

```kdl
is-available {
    css ".stock"
    to-bool
    fallback #false
}
```

**Значения:**
- `#null` - null/None
- `#true` / `#false` - boolean
- `0` - число
- `""` - строка

---

## Predicates

Используются в `match { ... }` и `assert { ... }`:

### String Predicates

```kdl
match { eq "value" }              // Равно
match { ne "value" }              // Не равно
match { starts "prefix" }         // Начинается с
match { ends "suffix" }           // Заканчивается на
match { contains "substring" }    // Содержит
match { re #"pattern"# }          // Regex
```

---

### Attribute Predicates

```kdl
match { has-attr "class" }
match { attr-eq "class" "active" }
match { attr-re "href" #"^https"# }
```

---

### Element Predicates

```kdl
assert { css ".required-element" }     // Элемент существует
assert { xpath "//div[@id='main']" }
```

---

### List Predicates

```kdl
assert { re-all #"pattern"# }   // Все элементы соответствуют
assert { re-any #"pattern"# }   // Хотя бы один соответствует
```

---

## Examples

### Простая структура

```kdl
struct Article {
    title {
        css "h1"
        text
    }
    author {
        css ".author"
        text
    }
    content {
        css ".content"
        text
        trim
    }
}
```

---

### Список с nested структурой

```kdl
struct Book type=list {
    -split-doc { css-all ".book" }
    
    title { css ".title"; text }
    price { css ".price"; text; re #"(\d+)"#; to-float }
}

struct Catalogue {
    books { nested Book }
    total-count { css-all ".book"; len }
}
```

---

### JSON парсинг с path

```kdl
define JSON-PATTERN=#"var data = (\[.*\])"#

json Quote array=#true {
    text str
    author str
}

struct Main {
    -init {
        raw-json { raw; re JSON-PATTERN }
    }
    
    all-quotes {
        self raw-json
        jsonify Quote
    }
    
    first-quote {
        self raw-json
        jsonify Quote path="0"
    }
}
```

---

### Таблица с валидацией

```kdl
struct ProductInfo type=table {
    -table { css "table.info" }
    -rows { css-all "tr" }
    -match { css "th"; text; lower }
    -value { css "td"; text }
    
    -pre-validate {
        assert { css "table.info" }
    }
    
    price {
        match { starts "price" }
        re #"(\d+\.\d+)"#
        to-float
    }
    
    stock {
        match { eq "availability" }
        assert { contains "In stock" }
        to-bool
        fallback #false
    }
}
```

---

### Transform с импортами

```kdl
transform decode-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = b64decode({{PRV}}).decode('utf-8')"
    }
}

struct Main {
    encoded {
        css "#data"
        attr "data-encoded"
        transform decode-base64
    }
}
```

---

## Summary

**Основные концепции:**
- Pipeline-based обработка данных
- Типизированные операции с проверкой в compile-time
- Переиспользование через `define`, `transform`, `nested`
- Мультиязычная кодогенерация (Python, JavaScript)
- Линтинг и валидация на этапе компиляции

**Поддерживаемые генераторы:**
- `py-bs4` - Python + BeautifulSoup4
- `py-lxml` - Python + lxml
- `js-pure` - JavaScript (pure)

**CLI:**
```bash
# Генерация кода
ssc-kdl generate schema.kdl -t py-bs4

# Проверка синтаксиса
ssc-kdl check schema.kdl

# Генерация из директории
ssc-kdl generate schemas/ -t py-lxml -o output/
```
