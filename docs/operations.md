# Operations Reference

> **Version:** 2.1
> **Last Updated:** 2026-03-21

Полный справочник по операциям pipeline в KDL Schema DSL.

Каждая операция имеет `accept` (входной тип) и `ret` (выходной тип). Линтер проверяет совместимость типов в compile-time.

---

## Table of Contents

- [Selectors](#selectors)
- [Extract Operations](#extract-operations)
- [String Operations](#string-operations)
- [Regex Operations](#regex-operations)
- [Type Conversions](#type-conversions)
- [Array Operations](#array-operations)
- [Control Flow](#control-flow)
- [Structured Operations](#structured-operations)
- [Code Operations](#code-operations)

---

## Selectors

### `css <query>`

Выбрать первый элемент по CSS селектору.

**Тип:** `DOCUMENT -> DOCUMENT`

```kdl
title { css "h1" }
link { css "a.primary" }
```

---

### `css-all <query>`

Выбрать все элементы по CSS селектору.

**Тип:** `DOCUMENT -> LIST_DOCUMENT`

```kdl
links { css-all "a" }
items { css-all ".item" }
```

---

### `css-remove <query>`

Удалить элементы по CSS селектору, вернуть документ.

**Тип:** `DOCUMENT -> DOCUMENT`

```kdl
clean-content {
    css-remove ".ads"
    css-remove "script"
    css ".content"
    text
}
```

---

### `xpath <query>`

Выбрать первый элемент по XPath.

**Тип:** `DOCUMENT -> DOCUMENT`

```kdl
content { xpath "//div[@class='content']" }
```

---

### `xpath-all <query>`

Выбрать все элементы по XPath.

**Тип:** `DOCUMENT -> LIST_DOCUMENT`

```kdl
links { xpath-all "//a[@href]" }
```

---

### `xpath-remove <query>`

Удалить элементы по XPath.

**Тип:** `DOCUMENT -> DOCUMENT`

```kdl
clean { xpath-remove "//script"; xpath-remove "//style" }
```

---

## Extract Operations

### `text`

Извлечь текстовое содержимое элемента.

**Типы:**
- `DOCUMENT -> STRING`
- `LIST_DOCUMENT -> LIST_STRING`

```kdl
title { css "h1"; text }
paragraphs { css-all "p"; text }
```

---

### `raw`

Извлечь HTML-код элемента.

**Типы:**
- `DOCUMENT -> STRING`
- `LIST_DOCUMENT -> LIST_STRING`

```kdl
html-content { css ".content"; raw }
```

---

### `attr <name> [name2 ...]`

Извлечь значение атрибута(ов). Несколько атрибутов конкатенируются через пробел.

**Типы:**
- `DOCUMENT -> STRING`
- `LIST_DOCUMENT -> LIST_STRING`

```kdl
url { css "a"; attr "href" }
classes { css "div"; attr "class" "data-value" }  // конкатенация
```

---

## String Operations

Все строковые операции работают как `STRING -> STRING` и `LIST_STRING -> LIST_STRING` (map).

### `trim` / `ltrim` / `rtrim`

Удалить пробелы по краям строки. Принимают опциональный аргумент - набор символов.

```kdl
text { css "p"; text; trim }
text { css "p"; text; ltrim }
text { css "p"; text; rtrim }
text { css "p"; text; trim "/" }  // удалить "/" по краям
```

---

### `upper` / `lower`

Преобразовать регистр.

```kdl
tag { css ".tag"; text; lower }
title { css "h1"; text; upper }
```

---

### `normalize-space`

Свернуть последовательные пробелы в один.

```kdl
text { css ".content"; text; normalize-space }
```

---

### `rm-prefix <value>` / `rm-suffix <value>`

Удалить префикс/суффикс из строки.

```kdl
url {
    css "img"
    attr "src"
    rm-prefix "../"
    rm-suffix ".jpg"
}
```

---

### `rm-prefix-suffix <value>`

Удалить одновременно и префикс, и суффикс.

```kdl
slug { css ".slug"; text; rm-prefix-suffix "/" }
```

---

### `fmt <template>`

Форматировать строку по шаблону. Placeholder: `{{}}`.

```kdl
define FMT-URL="https://example.com/{{}}"

url {
    css "a"
    attr "href"
    fmt FMT-URL
}
```

---

### `repl <old> <new>`

Замена подстроки. Два варианта:

**Inline (два аргумента):**

```kdl
text { css "p"; text; repl "foo" "bar" }
```

**Block (словарь замен):**

```kdl
define REPL-RATING {
    repl {
        One "1"
        Two "2"
        Three "3"
        Four "4"
        Five "5"
    }
}

rating {
    css ".star-rating"
    attr "class"
    rm-prefix "star-rating "
    REPL-RATING
    to-int
}
```

---

### `split <separator>`

Разбить строку на список.

**Тип:** `STRING -> LIST_STRING`

```kdl
tags { css ".tags"; text; split ", " }
```

---

### `join <separator>`

Объединить список в строку.

**Тип:** `LIST_STRING -> STRING`

```kdl
joined { css-all ".tag"; text; join ", " }
```

---

### `unescape`

Декодировать HTML-сущности (`&amp;` -> `&`, `&lt;` -> `<`, и т.д.).

```kdl
text { css ".content"; text; unescape }
```

---

## Regex Operations

### `re <pattern>`

Извлечь первую группу захвата. Паттерн должен содержать **ровно одну** группу захвата.

**Тип:** `STRING -> STRING`, `LIST_STRING -> LIST_STRING` (map)

```kdl
price {
    css ".price"
    text
    re #"(\d+\.\d+)"#
}
```

**VERBOSE паттерн:**

```kdl
define JSON-PATTERN=#"""
(?xs)
    var\s+data\s*=\s*     # START ANCHOR
    (\[.*\])              # CAPTURE GROUP
    ;\s+for               # END ANCHOR
"""#

data { raw; re JSON-PATTERN }
```

Флаги `(?x)` автоматически убираются, паттерн нормализуется в inline форму.

---

### `re-all <pattern>`

Извлечь все совпадения (без групп захвата).

**Тип:** `STRING -> LIST_STRING`

```kdl
numbers {
    css ".content"
    text
    re-all #"\d+"#
}
```

---

### `re-sub <pattern> <replacement>`

Заменить совпадения regex.

**Тип:** `STRING -> STRING`

```kdl
clean { css ".text"; text; re-sub #"\s+" " " }
```

---

## Type Conversions

### `to-int`

**Тип:** `STRING -> INT`

```kdl
count { css ".count"; text; to-int }
```

---

### `to-float`

**Тип:** `STRING -> FLOAT`

```kdl
price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
```

---

### `to-bool`

**Типы:**
- `DOCUMENT -> BOOL` - проверка наличия элемента
- `STRING -> BOOL` - проверка непустой строки
- `INT -> BOOL`

```kdl
has-content { css ".content"; to-bool }
```

---

## Array Operations

### `index <n>`

Получить элемент по индексу.

**Тип:** `LIST_* -> <scalar type>`

```kdl
second { css-all "a"; index 1; attr "href" }
```

---

### `first` / `last`

Получить первый/последний элемент.

**Тип:** `LIST_* -> <scalar type>`

```kdl
first-link { css-all "a"; first; attr "href" }
last-link { css-all "a"; last; attr "href" }
```

---

### `slice <start> <end>`

Получить подсписок `[start:end]`.

**Тип:** `LIST_* -> LIST_*`

```kdl
subset { css-all "a"; attr "href"; slice 1 3 }
```

---

### `len`

Получить длину списка или строки.

**Типы:**
- `LIST_* -> INT`
- `STRING -> INT`

```kdl
links-count { css-all "a"; len }
```

---

### `unique`

Удалить дубликаты из списка.

**Тип:** `LIST_* -> LIST_*`

```kdl
unique-tags { css-all ".tag"; text; unique }
```

---

## Control Flow

### `fallback <value>`

Значение по умолчанию при ошибке. Оборачивает предыдущие операции в try/except.

```kdl
fallback #null       // None/null -> тип становится OPT_*
fallback #true       // boolean
fallback #false
fallback 0           // число
fallback ""          // строка
```

**Блочный fallback** (для списков - возвращает пустой список при ошибке):

```kdl
links {
    css-all "a"
    attr "href"
    fallback {}      // -> [] при ошибке
}
```

---

### `self <name>` / `@<name>`

Использовать предвычисленное значение из `@init`:

```kdl
@init {
    raw-json { raw; re PATTERN }
}

data {
    @raw-json            // сахар для self "raw-json"
    jsonify Quote
}
```

---

### `filter { ... }`

Фильтровать список по предикатам. Требует `LIST_*` на входе.

```kdl
links {
    css-all "a"
    attr "href"
    filter { not { contains "utm" } }
}
```

Подробнее о предикатах см. [predicates.md](predicates.md).

---

### `assert { ... }`

Проверить условие, выбросить исключение если false.

```kdl
is-available {
    css ".stock"
    text
    assert { contains "In stock" }
    to-bool
}
```

---

### `match { ... }`

Сопоставление ключа строки таблицы. Используется в `type=table` полях, должен быть **первой** операцией.

```kdl
price {
    match { starts "price" }
    re #"(\d+\.\d+)"#
    to-float
}
```

---

## Structured Operations

### `nested <StructName>`

Вызвать вложенную структуру.

**Тип:** `DOCUMENT -> NESTED`

```kdl
struct Book type=list { ... }

struct Catalogue {
    books { nested Book }
}
```

---

### `jsonify <SchemaName> [path="..."]`

Десериализовать JSON строку по схеме.

**Тип:** `STRING -> JSON`

```kdl
all-quotes { @data; jsonify Quote }
first-quote { @data; jsonify Quote path="0" }
author-slug { @data; jsonify Quote path="2.author.slug" }
```

---

## Code Operations

### `transform <name>`

Вызвать пользовательскую функцию трансформации (определённую через `transform`).

```kdl
title {
    css "title"
    text
    transform to-base64
}
```

Типы проверяются по `accept`/`return` определения transform.

---

### `expr <name>`

Вызвать блочный define или dsl-блок.

```kdl
define EXTRACT-HREF {
    css "a"
    attr "href"
}

dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

struct Main {
    link { expr EXTRACT-HREF; trim }
    title { css "h1"; text; expr upper-py }
}
```

**Отличие от прямого вызова define:** `expr` является явным вызовом и валидируется линтером как ссылка на dsl или блочный define.
