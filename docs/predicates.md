# Predicates Reference

> **Version:** 2.1
> **Last Updated:** 2026-03-21

Справочник по предикатам и логическим контейнерам для `filter`, `assert` и `match`.

---

## Table of Contents

- [Контейнеры](#контейнеры)
- [String Predicates](#string-predicates)
- [Numeric Predicates](#numeric-predicates)
- [Length Predicates](#length-predicates)
- [Attribute Predicates](#attribute-predicates)
- [Text Predicates](#text-predicates)
- [Element Predicates](#element-predicates)
- [Regex Predicates](#regex-predicates)
- [Logic Containers](#logic-containers)
- [Примеры](#примеры)

---

## Контейнеры

Предикаты используются внутри трёх контейнеров:

### `filter { ... }`

Фильтрует элементы списка. Требует `LIST_*` на входе. Возвращает тот же тип.

```kdl
links {
    css-all "a"
    attr "href"
    filter {
        starts "https"
        not { contains "utm" }
    }
}
```

---

### `assert { ... }`

Проверяет условие. Выбрасывает исключение если false. Не меняет тип.

```kdl
@pre-validate {
    assert { css ".required-element" }
}

field {
    css ".stock"; text
    assert { contains "In stock" }
}
```

---

### `match { ... }`

Сопоставление ключа для `type=table`. Должен быть **первой операцией** в поле.

**Тип:** `DOCUMENT -> STRING` (через `@match` pipeline)

```kdl
price {
    match { starts "price" }
    re #"(\d+\.\d+)"#
    to-float
}
```

---

## String Predicates

Работают со значением как строкой.

### `eq <value> [value2 ...]`

Равно одному из значений.

```kdl
match { eq "upc" }
match { eq "value1" "value2" }  // любое из значений
```

---

### `ne <value> [value2 ...]`

Не равно значению(ям).

```kdl
match { ne "skip" "ignore" }
```

---

### `starts <value> [value2 ...]`

Начинается с одного из значений.

```kdl
match { starts "price" }
filter { starts "https" "/" }
```

---

### `ends <value> [value2 ...]`

Заканчивается одним из значений.

```kdl
filter { ends ".html" ".htm" }
```

---

### `contains <value> [value2 ...]`

Содержит одно из значений.

```kdl
assert { contains "In stock" }
filter { contains "example" "test" }
```

---

### `in <value> [value2 ...]`

Значение входит в перечисленный набор.

```kdl
filter { in "active" "pending" "completed" }
```

---

## Numeric Predicates

Работают с числовыми значениями. Доступны только в `assert`.

### `gt <value>` / `ge <value>` / `lt <value>` / `le <value>`

Сравнения: больше, больше-равно, меньше, меньше-равно.

```kdl
assert { gt 0 }
assert { le 100 }
```

---

## Length Predicates

Проверяют длину строки или списка.

### `len-eq <n> [n2 ...]` / `len-ne <n> [n2 ...]`

Длина равна / не равна значению(ям). Значения - неотрицательные целые числа.

```kdl
filter { len-eq 5 }
filter { len-ne 0 }
```

---

### `len-gt <n>` / `len-lt <n>` / `len-ge <n>` / `len-le <n>`

Длина больше / меньше / больше-равно / меньше-равно. Ровно один аргумент.

```kdl
filter { len-gt 0 }
filter { len-le 100 }
```

---

### `len-range <min> <max>`

Длина в диапазоне [min, max]. Ровно два аргумента.

```kdl
filter { len-range 1 10 }
```

---

## Attribute Predicates

Проверяют атрибуты HTML-элементов. Работают с `DOCUMENT`/`LIST_DOCUMENT`.

### `has-attr <name> [name2 ...]`

Элемент имеет атрибут(ы). Если несколько - проверяются все (AND).

```kdl
match { has-attr "href" }
match { has-attr "href" "title" }
```

---

### `attr-eq <name> <value> [value2 ...]`

Атрибут равен одному из значений.

```kdl
filter { attr-eq "class" "active" }
filter { attr-eq "type" "text" "email" }
```

---

### `attr-ne <name> <value> [value2 ...]`

Атрибут не равен значению(ям).

```kdl
filter { attr-ne "class" "hidden" }
```

---

### `attr-starts <name> <value> [value2 ...]`

Атрибут начинается с одного из значений.

```kdl
filter { attr-starts "href" "https" "/" }
```

---

### `attr-ends <name> <value> [value2 ...]`

Атрибут заканчивается одним из значений.

```kdl
filter { attr-ends "src" ".jpg" ".png" }
```

---

### `attr-contains <name> <value> [value2 ...]`

Атрибут содержит одно из значений.

```kdl
filter { attr-contains "class" "active" }
```

---

### `attr-re <name> <pattern>`

Атрибут соответствует regex. Ровно два аргумента: имя атрибута и паттерн.

```kdl
filter { attr-re "href" #"^https://example\.com"# }
```

---

## Text Predicates

Проверяют текстовое содержимое элемента.

### `text-starts <value> [value2 ...]`

Текст начинается с одного из значений.

```kdl
filter { text-starts "Chapter" "Section" }
```

---

### `text-ends <value> [value2 ...]`

Текст заканчивается одним из значений.

```kdl
filter { text-ends "." "!" "?" }
```

---

### `text-contains <value> [value2 ...]`

Текст содержит одно из значений.

```kdl
filter { text-contains "important" "critical" }
```

---

### `text-re <pattern>`

Текст соответствует regex. Один аргумент.

```kdl
filter { text-re #"\d+ items"# }
```

---

## Element Predicates

Проверяют наличие дочерних элементов.

### `css <query>`

Элемент содержит потомка по CSS селектору.

```kdl
assert { css ".required-element" }
filter { css ".verified" }
```

---

### `xpath <query>`

Элемент содержит потомка по XPath.

```kdl
assert { xpath "//div[@id='main']" }
```

---

## Regex Predicates

### `re <pattern>`

Значение соответствует regex.

```kdl
match { re #"^product"# }
assert { re #"\d+"# }
```

---

### `re-all <pattern>`

Все элементы списка соответствуют regex. Используется в `assert`.

```kdl
assert { re-all #"^\d+$"# }
```

---

### `re-any <pattern>`

Хотя бы один элемент соответствует regex. Используется в `assert`.

```kdl
assert { re-any #"special"# }
```

---

## Logic Containers

### `not { ... }`

Инвертировать предикат(ы).

```kdl
filter { not { contains "spam" } }
match { not { eq "draft" } }
```

---

### `and { ... }`

Все предикаты должны быть true (по умолчанию предикаты внутри контейнера уже AND).

```kdl
filter {
    and {
        starts "https"
        not { contains "utm" }
    }
}
```

---

### `or { ... }`

Хотя бы один предикат должен быть true.

```kdl
filter {
    or {
        attr-starts "href" "https"
        attr-starts "href" "/"
    }
}
```

---

## Примеры

### Фильтрация ссылок

```kdl
struct SafeLinks type=flat {
    @split-doc {
        css-all "a[href]"
        match {
            has-attr "href"
            not { attr-starts "href" "javascript:" }
            not { attr-eq "rel" "nofollow" }
        }
    }
    url { attr "href" }
}
```

### Валидация перед парсингом

```kdl
struct SecurePage {
    @pre-validate {
        assert {
            css "meta[name='csrf-token']"
            css "#main-content"
        }
    }
    // fields...
}
```

### Таблица с условиями

```kdl
struct ProductInfo type=table {
    @table { css "table.info" }
    @rows { css-all "tr" }
    @match { css "th"; text; lower; trim }
    @value { css "td"; text }

    price {
        match { or { starts "price" ; eq "cost" } }
        re #"(\d+\.\d+)"#
        to-float
    }
}
```

### Комбинированная логика

```kdl
filter {
    and {
        len-gt 0
        not { eq "" }
        or {
            starts "http"
            starts "/"
        }
    }
}
```
