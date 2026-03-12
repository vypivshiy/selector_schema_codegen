# Operations Reference

> **Version:** 2.0  
> **Last Updated:** 2026-03-11

Полный справочник по операциям и выражениям в KDL Schema DSL.

---

## Table of Contents

- [Overview](#overview)
- [Selectors](#selectors)
- [Extract Operations](#extract-operations)
- [String Operations](#string-operations)
- [Regex Operations](#regex-operations)
- [Type Conversions](#type-conversions)
- [Array Operations](#array-operations)
- [Predicates](#predicates)
- [Control Flow](#control-flow)
- [Special Operations](#special-operations)
- [Type Compatibility](#type-compatibility)

---

## Overview

Операции в KDL Schema DSL организованы в **pipeline** - последовательность преобразований данных:

```kdl
field-name {
    css "selector"    // 1. Selector
    text              // 2. Extract
    trim              // 3. Transform
    upper             // 4. Transform
    to-int            // 5. Type conversion
    fallback 0        // 6. Fallback
}
```

**Типизация:**
- Каждая операция имеет `accept` (входной тип) и `ret` (выходной тип)
- Проверка совместимости типов в compile-time
- Ошибки типов показываются линтером

---

## Selectors

### CSS Selectors

#### `css <query>`

Выбрать первый элемент по CSS селектору.

**Тип:** `DOCUMENT → DOCUMENT`

**DSL:**
```kdl
title { css "h1" }
link { css "a.primary" }
article { css "article > .content" }
```

**Генерируемый код:**
```python
# bs4
v2 = v1.select_one('h1')

# lxml
v2 = v1.cssselect('h1')[0]
```

---

#### `css-all <query>`

Выбрать все элементы по CSS селектору.

**Тип:** `DOCUMENT → LIST_DOCUMENT`

**DSL:**
```kdl
links { css-all "a" }
items { css-all ".item" }
```

**Генерируемый код:**
```python
# bs4
v2 = v1.select('a')

# lxml
v2 = v1.cssselect('a')
```

---

#### `css-rm <query>`

Удалить элементы по CSS селектору, вернуть документ.

**Тип:** `DOCUMENT → DOCUMENT`

**DSL:**
```kdl
clean-content {
    css-rm ".ads"
    css-rm "script"
    css ".content"
    text
}
```

**Генерируемый код:**
```python
# bs4
for elem in v1.select('.ads'):
    elem.decompose()
v2 = v1

# lxml
[e.getparent().remove(e) for e in v1.cssselect('.ads') if e.getparent() is not None]
v2 = v1
```

---

### XPath Selectors

#### `xpath <query>`

Выбрать первый элемент по XPath.

**Тип:** `DOCUMENT → DOCUMENT`

**DSL:**
```kdl
content { xpath "//div[@class='content']" }
title { xpath "//h1/text()" }
```

---

#### `xpath-all <query>`

Выбрать все элементы по XPath.

**Тип:** `DOCUMENT → LIST_DOCUMENT`

**DSL:**
```kdl
links { xpath-all "//a[@href]" }
```

---

#### `xpath-rm <query>`

Удалить элементы по XPath.

**Тип:** `DOCUMENT → DOCUMENT`

**DSL:**
```kdl
clean { xpath-rm "//script"; xpath-rm "//style" }
```

---

## Extract Operations

### `text`

Извлечь текстовое содержимое элемента.

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

**DSL:**
```kdl
title { css "h1"; text }
paragraphs { css-all "p"; text }
```

**Генерируемый код:**
```python
# bs4 (DOCUMENT)
v2 = v1.text

# bs4 (LIST_DOCUMENT)
v2 = [i.text for i in v1]

# lxml (DOCUMENT)
v2 = v1.text_content()

# lxml (LIST_DOCUMENT)
v2 = [i.text_content() for i in v1]
```

---

### `attr <name> [name2 ...]`

Извлечь значение атрибута(ов).

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

**DSL:**
```kdl
url { css "a"; attr "href" }
classes { css "div"; attr "class" "data-value" }  // Конкатенация
```

**Генерируемый код:**
```python
# bs4 (один атрибут)
v2 = ' '.join(v1.get_attribute_list('href'))

# bs4 (несколько атрибутов)
v2 = ' '.join(v1.get_attribute_list('class')) + ' ' + ' '.join(v1.get_attribute_list('data-value'))

# lxml (один атрибут)
v2 = v1.get('href', '')

# lxml (несколько атрибутов)
v2 = v1.get('class', '') + ' ' + v1.get('data-value', '')
```

---

### `raw`

Извлечь HTML код элемента.

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

**DSL:**
```kdl
html { css ".content"; raw }
```

**Генерируемый код:**
```python
# bs4
v2 = str(v1)

# lxml
v2 = html.tostring(v1, encoding='unicode')
```

---

## String Operations

### `trim` / `ltrim` / `rtrim`

Удалить пробелы по краям строки.

**Тип:** `STRING → STRING` (и `LIST_STRING → LIST_STRING`)

**DSL:**
```kdl
text { css "p"; text; trim }
text { css "p"; text; ltrim }   // Только слева
text { css "p"; text; rtrim }   // Только справа
```

**Генерируемый код:**
```python
v3 = v2.strip()
v3 = v2.lstrip()
v3 = v2.rstrip()
```

---

### `upper` / `lower`

Преобразовать регистр.

**Тип:** `STRING → STRING`

**DSL:**
```kdl
tag { css ".tag"; text; lower }
title { css "h1"; text; upper }
```

**Генерируемый код:**
```python
v3 = v2.lower()
v3 = v2.upper()
```

---

### `rm-prefix <value>` / `rm-suffix <value>`

Удалить префикс/суффикс из строки.

**Тип:** `STRING → STRING`

**DSL:**
```kdl
url {
    css "img"
    attr "src"
    rm-prefix "../"
    rm-suffix ".jpg"
}
```

**Генерируемый код:**
```python
v3 = v2.removeprefix('../')
v4 = v3.removesuffix('.jpg')
```

---

### `fmt <template>`

Форматировать строку по шаблону.

**Тип:** `STRING → STRING`

**DSL:**
```kdl
define FMT-URL="https://example.com/{{}}"

url {
    css "a"
    attr "href"
    fmt FMT-URL
}
```

**Генерируемый код:**
```python
v3 = "https://example.com/{}".format(v2)
```

**Особенности:**
- Placeholder: `{{}}`
- Можно использовать только один placeholder

---

## Regex Operations

### `re <pattern>`

Извлечь первое совпадение (первую группу захвата).

**Типы:**
- `STRING → STRING`
- `LIST_STRING → LIST_STRING` (map)

**DSL:**
```kdl
price {
    css ".price"
    text
    re #"(\d+\.\d+)"#
}

// VERBOSE паттерн
define JSON-PATTERN=#"""
(?xs)
    var\s+data\s*=\s*     # START ANCHOR
    (\[.*\])              # CAPTURE GROUP
    ;\s+for               # END ANCHOR
"""#

data {
    raw
    re JSON-PATTERN
}
```

**Генерируемый код:**
```python
# Обычный паттерн
v3 = re.search(r'(\d+\.\d+)', v2)[1]

# VERBOSE паттерн (автоматически нормализуется)
v3 = re.search('(?s)var\\s+data\\s*=\\s*(\\[.*\\]);\\s+for', v2)[1]
```

**Особенности:**
- VERBOSE флаг `(?x)` автоматически убирается
- Флаги `(?i)`, `(?s)` встраиваются inline
- Возвращает **первую группу захвата** (не всё совпадение)

---

### `re-all <pattern>`

Извлечь все совпадения.

**Тип:** `STRING → LIST_STRING`

**DSL:**
```kdl
numbers {
    css ".content"
    text
    re-all #"\d+"#
}
```

**Генерируемый код:**
```python
v3 = re.findall(r'\d+', v2)
```

---

### `re-sub <pattern> <replacement>`

Заменить совпадения regex.

**Тип:** `STRING → STRING`

**DSL:**
```kdl
clean {
    css ".text"
    text
    re-sub #"\s+" " "
}
```

**Генерируемый код:**
```python
v3 = re.sub(r'\s+', ' ', v2)
```

---

### `repl { ... }` / `<DEFINE>`

Замена по словарю.

**Тип:** `STRING → STRING`

**DSL:**
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

**Генерируемый код:**
```python
_repl_map = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}
v4 = _repl_map.get(v3, v3)
```

---

## Type Conversions

### `to-int`

Преобразовать в целое число.

**Тип:** `STRING → INT`

**DSL:**
```kdl
count { css ".count"; text; to-int }
reviews { css ".reviews"; text; re #"(\d+)"#; to-int }
```

**Генерируемый код:**
```python
v3 = int(v2)
```

---

### `to-float`

Преобразовать в число с плавающей точкой.

**Тип:** `STRING → FLOAT`

**DSL:**
```kdl
price {
    css ".price"
    text
    re #"(\d+\.\d+)"#
    to-float
}
```

**Генерируемый код:**
```python
v3 = float(v2)
```

---

### `to-bool`

Преобразовать в boolean.

**Типы:**
- `DOCUMENT → BOOL` - проверка наличия элемента
- `STRING → BOOL` - проверка непустой строки
- `INT → BOOL`

**DSL:**
```kdl
has-content { css ".content"; to-bool }
is-available {
    css ".stock"
    text
    assert { contains "In stock" }
    to-bool
    fallback #false
}
```

**Генерируемый код:**
```python
# DOCUMENT
v2 = bool(v1)  # True если элемент существует

# STRING
v2 = bool(v1)  # True если строка не пустая
```

---

### `jsonify <schema> [path="..."]`

Десериализовать JSON строку по схеме.

**Тип:** `STRING → JSON`

**DSL:**
```kdl
json Quote array=#true {
    text str
    author str
}

data {
    raw
    re JSON-PATTERN
    jsonify Quote
}

first-quote {
    self data
    jsonify Quote path="0"
}

author-slug {
    self data
    jsonify Quote path="2.author.slug"
}
```

**path навигация:**
- `""` - применить схему к результату `json.loads()`
- `"0"`, `"1"` - индекс в массиве (unwrap)
- `"field"` - доступ к полю объекта
- `"0.author.slug"` - комбинация

**Генерируемый код:**
```python
# Без path
v3 = json.loads(v2)

# С path="0"
v3 = json.loads(v2)[0]

# С path="2.author.slug"
v3 = json.loads(v2)[2]["author"]["slug"]
```

---

## Array Operations

### `len`

Получить длину массива или строки.

**Типы:**
- `LIST_* → INT`
- `STRING → INT`

**DSL:**
```kdl
links-count { css-all "a"; len }
text-length { css "p"; text; len }
```

**Генерируемый код:**
```python
v2 = len(v1)
```

---

### `match { ... }`

Фильтровать список по предикатам (для `type=table` и `type=dict`).

**Тип:** `LIST_DOCUMENT → LIST_DOCUMENT`

**DSL:**
```kdl
struct ProductInfo type=table {
    -match { css "th"; text; lower }
    
    price {
        match { starts "price" }
        re #"(\d+\.\d+)"#
        to-float
    }
}
```

**Генерируемый код:**
```python
# Фильтрация строк таблицы
[row for row in rows if row_key.startswith('price')]
```

---

## Predicates

Используются в `match { ... }` и `assert { ... }`.

### String Predicates

#### `eq <value> [value2 ...]`

Равно одному из значений.

**DSL:**
```kdl
match { eq "upc" }
match { eq "value1" "value2" }  // Любое из значений
```

**Генерируемый код:**
```python
# Одно значение
i == "upc"

# Несколько значений
i in ("value1", "value2")
```

---

#### `ne <value> [value2 ...]`

Не равно значению(ям).

**DSL:**
```kdl
match { ne "skip" }
```

---

#### `starts <value> [value2 ...]`

Начинается с одного из значений.

**DSL:**
```kdl
match { starts "price" }
match { starts "prefix1" "prefix2" }
```

**Генерируемый код:**
```python
# Одно значение
i.startswith("price")

# Несколько значений
any(i.startswith(v) for v in ("prefix1", "prefix2"))
```

---

#### `ends <value> [value2 ...]`

Заканчивается одним из значений.

**DSL:**
```kdl
match { ends "tax" }
```

---

#### `contains <value> [value2 ...]`

Содержит одно из значений.

**DSL:**
```kdl
assert { contains "In stock" }
match { contains "substring1" "substring2" }
```

**Генерируемый код:**
```python
# Одно значение
"In stock" in i

# Несколько значений
any(v in i for v in ("substring1", "substring2"))
```

---

#### `re <pattern>`

Соответствует regex паттерну.

**DSL:**
```kdl
match { re #"^product"# }
assert { re #"\d+"# }
```

**Генерируемый код:**
```python
bool(re.search(r'^product', i))
```

---

### Attribute Predicates

#### `has-attr <name> [name2 ...]`

Элемент имеет атрибут(ы).

**DSL:**
```kdl
match { has-attr "class" }
match { has-attr "href" "title" }  // Оба атрибута
```

**Генерируемый код:**
```python
# bs4 (один атрибут)
i.has_attr('class')

# lxml (один атрибут)
'class' in i.attrib

# Несколько атрибутов
all(attr in i.attrib for attr in ('href', 'title'))
```

---

#### `attr-eq <name> <value> [value2 ...]`

Атрибут равен одному из значений.

**DSL:**
```kdl
match { attr-eq "class" "active" }
match { attr-eq "type" "text" "email" }
```

**Генерируемый код:**
```python
# lxml
i.get('class', '') == 'active'
i.get('type', '') in ('text', 'email')
```

---

#### `attr-starts <name> <value>`, `attr-ends <name> <value>`, `attr-contains <name> <value>`

Атрибут начинается с / заканчивается на / содержит значение.

**DSL:**
```kdl
match { attr-starts "href" "https" }
match { attr-ends "src" ".jpg" }
match { attr-contains "class" "active" }
```

---

#### `attr-re <name> <pattern>`

Атрибут соответствует regex.

**DSL:**
```kdl
match { attr-re "href" #"^https://example\.com"# }
```

**Генерируемый код:**
```python
bool(re.search(r'^https://example\.com', i.get('href', '')))
```

---

### Element Predicates

#### `css <query>`

Элемент содержит потомка по CSS селектору.

**DSL:**
```kdl
assert { css ".required-element" }
match { css ".active" }
```

**Генерируемый код:**
```python
# bs4
bool(i.select_one('.required-element'))

# lxml
bool(i.cssselect('.required-element'))
```

---

#### `xpath <query>`

Элемент содержит потомка по XPath.

**DSL:**
```kdl
assert { xpath "//div[@id='main']" }
```

---

### List Predicates

#### `re-all <pattern>`

Все элементы списка соответствуют паттерну.

**DSL:**
```kdl
assert { re-all #"^\d+$"# }
```

**Генерируемый код:**
```python
all(re.search(r'^\d+$', j) for j in i)
```

---

#### `re-any <pattern>`

Хотя бы один элемент соответствует паттерну.

**DSL:**
```kdl
assert { re-any #"error"# }
```

**Генерируемый код:**
```python
any(re.search(r'error', j) for j in i)
```

---

## Control Flow

### `assert { ... }`

Проверить условие, выбросить исключение если false.

**DSL:**
```kdl
-pre-validate {
    assert { css ".required" }
}

is-available {
    css ".stock"
    text
    assert { contains "In stock" }
    to-bool
}
```

**Генерируемый код:**
```python
# Выбрасывает исключение если элемент не найден
assert bool(v1.select_one('.required')), "Element not found"

# Выбрасывает исключение если условие не выполнено
assert "In stock" in v2, "Assertion failed"
```

---

### `fallback <value>`

Значение по умолчанию при ошибке.

**DSL:**
```kdl
fallback #null
fallback #true
fallback #false
fallback 0
fallback "default"
```

**Генерируемый код:**
```python
try:
    v3 = int(v2)
except Exception:
    v3 = 0  # fallback value
```

---

### `nested <StructName>`

Вызвать вложенную структуру.

**DSL:**
```kdl
struct Book type=list { ... }

struct Catalogue {
    books { nested Book }
}
```

**Генерируемый код:**
```python
# Если Book имеет type=list (is_array=True)
v2 = [Book._parse_item(i) for i in v1]

# Если Book имеет type=item (is_array=False)
v2 = Book._parse_item(v1)
```

---

### `self <name>`

Использовать предвычисленное значение из `-init`.

**DSL:**
```kdl
-init {
    raw-json { raw; re PATTERN }
}

data {
    self raw-json
    jsonify Quote
}
```

**Генерируемый код:**
```python
v1 = self._raw_json  # Доступ к предвычисленному полю
```

---

## Special Operations

### `transform <name>`

Вызвать пользовательскую функцию трансформации.

**DSL:**
```kdl
transform to-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = str(b64decode({{PRV}}))"
    }
}

title {
    css "title"
    text
    transform to-base64
}
```

**Генерируемый код:**
```python
# Импорт добавляется автоматически
from base64 import b64decode

# Код трансформа с подстановкой переменных
v3 = str(b64decode(v2))
```

---

## Type Compatibility

### Pipeline Type Flow

```kdl
field {
    css "h1"          // DOCUMENT → DOCUMENT
    text              // DOCUMENT → STRING
    trim              // STRING → STRING
    upper             // STRING → STRING
    re #"(\d+)"#      // STRING → STRING
    to-int            // STRING → INT
    fallback 0        // INT (with fallback)
}
```

### Common Patterns

**Extract number from text:**
```kdl
price {
    css ".price"      // DOCUMENT → DOCUMENT
    text              // DOCUMENT → STRING
    re #"(\d+\.\d+)"# // STRING → STRING
    to-float          // STRING → FLOAT
}
```

**Filter and count:**
```kdl
active-links {
    css-all "a"       // DOCUMENT → LIST_DOCUMENT
    match { attr-starts "href" "https" }  // LIST_DOCUMENT → LIST_DOCUMENT
    len               // LIST_DOCUMENT → INT
}
```

**Extract list of strings:**
```kdl
tags {
    css-all ".tag"    // DOCUMENT → LIST_DOCUMENT
    text              // LIST_DOCUMENT → LIST_STRING
}
```

**Nested structure:**
```kdl
books {
    nested Book       // DOCUMENT → LIST[BookType] (если Book is type=list)
}
```

---

## Summary

**Категории операций:**
1. **Selectors** - выбор элементов
2. **Extract** - извлечение данных
3. **String Ops** - работа со строками
4. **Regex** - regex операции
5. **Type Conv** - конвертация типов
6. **Array** - работа с массивами
7. **Predicates** - условия и фильтры
8. **Control** - управление потоком
9. **Special** - transform, nested, jsonify

**Принципы:**
- Типизированный pipeline
- Проверка типов в compile-time
- Map семантика для списков
- Fallback для error handling

**Линтер проверяет:**
- Совместимость типов в pipeline
- Правильность аргументов операций
- Наличие required полей
- Синтаксис regex паттернов
