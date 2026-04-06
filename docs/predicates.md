# Предикаты и логика

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Предикаты используются внутри контейнеров `filter`, `assert`, `match`.

## Контейнеры

```kdl
filter { starts "https"; not { contains "utm" } }
assert { len-gt 0 }
match { starts "price" }
```

Правила:
- `filter` применим только к `LIST_*` и возвращает тот же тип.
- `assert` не меняет тип и выбрасывает ошибку при несоответствии.
- `match` доступен только в `type=table` и должен быть первой операцией поля.

## Логические контейнеры

```kdl
filter {
    and { starts "http"; not { contains "utm" } }
}
```

Контейнеры: `not`, `and`, `or`.

## String predicates

| Операция | Аргументы |
|---|---|
| `eq` | 1+ |
| `ne` | 1+ |
| `starts` | 1+ |
| `ends` | 1+ |
| `contains` | 1+ |
| `in` | 1+ |
| `re` | 1 (regex pattern) |

## Length predicates (assert-only)

| Операция | Аргументы |
|---|---|
| `len-eq` | 1+ |
| `len-ne` | 1+ |
| `len-gt` | 1 |
| `len-lt` | 1 |
| `len-ge` | 1 |
| `len-le` | 1 |
| `len-range` | 2 |

Все аргументы должны быть неотрицательными целыми.


## Attribute predicates

| Операция | Аргументы |
|---|---|
| `has-attr` | 1+ |
| `attr-eq` | 2+ |
| `attr-ne` | 2+ |
| `attr-starts` | 2+ |
| `attr-ends` | 2+ |
| `attr-contains` | 2+ |
| `attr-re` | 2 |

## Text predicates

| Операция | Аргументы |
|---|---|
| `text-re` | 1 |
| `text-starts` | 1+ |
| `text-ends` | 1+ |
| `text-contains` | 1+ |

## Document predicates

| Операция | Аргументы | Scope |
|---|---|---|
| `css` | 1 (selector) | filter, assert |
| `xpath` | 1 (selector) | filter, assert |

Проверяют наличие дочернего элемента по селектору.

## Regex predicates (assert-only)

| Операция | Аргументы |
|---|---|
| `re-any` | 1 |
| `re-all` | 1 |

`re-any` — хотя бы один элемент списка соответствует паттерну.
`re-all` — все элементы списка соответствуют паттерну.

## Numeric predicates (assert-only)

| Операция | Аргументы |
|---|---|
| `gt` | 1 |
| `lt` | 1 |
| `ge` | 1 |
| `le` | 1 |

## Примеры

```kdl
links {
    css-all "a"
    attr "href"
    filter { starts "https"; not { contains "utm" } }
}

count {
    css-all ".item"
    len
    assert { gt 0 }
}
```
