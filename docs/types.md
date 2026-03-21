# Type System

> **Version:** 2.1
> **Last Updated:** 2026-03-21

Система типов KDL Schema DSL. Все pipeline-операции типизированы, линтер проверяет совместимость в compile-time.

---

## Table of Contents

- [VariableType](#variabletype)
- [StructType](#structtype)
- [Pipeline Type Flow](#pipeline-type-flow)
- [AUTO и вывод типов](#auto-и-вывод-типов)
- [Optional типы](#optional-типы)
- [Таблица типов операций](#таблица-типов-операций)

---

## VariableType

Перечисление всех типов значений в pipeline:

### Скалярные

| Тип | Описание |
|-----|----------|
| `DOCUMENT` | HTML/XML элемент |
| `STRING` | Строка |
| `INT` | Целое число |
| `FLOAT` | Число с плавающей точкой |
| `BOOL` | Boolean |
| `NULL` | Null/None |
| `NESTED` | Вложенная структура |
| `JSON` | Результат jsonify |

### Списочные

| Тип | Описание |
|-----|----------|
| `LIST_DOCUMENT` | Список элементов |
| `LIST_STRING` | Список строк |
| `LIST_INT` | Список целых чисел |
| `LIST_FLOAT` | Список float |

### Optional

| Тип | Описание |
|-----|----------|
| `OPT_STRING` | STRING \| null |
| `OPT_INT` | INT \| null |
| `OPT_FLOAT` | FLOAT \| null |

### Специальные

| Тип | Описание |
|-----|----------|
| `AUTO` | Автовыведение (скалярный) |
| `LIST_AUTO` | Автовыведение (списочный) |

### Свойства типов

- `.is_list` - является ли списочным типом
- `.scalar` - скалярный эквивалент (`LIST_STRING` -> `STRING`)
- `.as_list` - списочный эквивалент (`STRING` -> `LIST_STRING`)
- `.optional` - optional эквивалент (`STRING` -> `OPT_STRING`)

---

## StructType

Тип структуры определяет форму результата:

| Тип | Результат | Обязательные поля |
|-----|-----------|-------------------|
| `ITEM` | `dict` | - |
| `LIST` | `list[dict]` | `@split-doc` |
| `FLAT` | `list[scalar]` | `@split-doc` |
| `DICT` | `dict[str, str]` | `@split-doc`, `@key`, `@value` |
| `TABLE` | `dict` | `@table`, `@rows`, `@match`, `@value` |

---

## Pipeline Type Flow

Каждая операция принимает тип на входе (`accept`) и возвращает тип на выходе (`ret`). Pipeline начинается с `DOCUMENT`.

### Пример

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

### Map-семантика для списков

Многие операции автоматически работают со списками через map:

```kdl
tags {
    css-all ".tag"       // DOCUMENT -> LIST_DOCUMENT
    text                 // LIST_DOCUMENT -> LIST_STRING (map)
    trim                 // LIST_STRING -> LIST_STRING (map)
    lower                // LIST_STRING -> LIST_STRING (map)
}
```

### Редукция списка

Операции `first`, `last`, `index` преобразуют список в скаляр:

```kdl
first-link {
    css-all "a"          // DOCUMENT -> LIST_DOCUMENT
    first                // LIST_DOCUMENT -> DOCUMENT
    attr "href"          // DOCUMENT -> STRING
}
```

---

## AUTO и вывод типов

`AUTO` и `LIST_AUTO` - специальные типы для автоматического вывода:

- `AUTO` совместим с любым скалярным типом
- `LIST_AUTO` совместим с любым списочным типом

Используются в:
- Начале pipeline (до первой операции)
- Блочных define (тип вычисляется из содержимого)
- `self` (ссылка на @init поле)

---

## Optional типы

`fallback #null` превращает скалярный тип в optional:

```kdl
// STRING -> OPT_STRING
name {
    css ".name"
    text
    fallback #null
}

// INT -> OPT_INT
count {
    css ".count"
    text
    to-int
    fallback #null
}
```

В сгенерированном коде:
- Python: `Optional[str]`, `Optional[int]`, `Optional[float]`
- TypeScript: `string | null`, `number | null`

---

## Таблица типов операций

### Selectors

| Операция | Accept | Return |
|----------|--------|--------|
| `css` | `DOCUMENT` | `DOCUMENT` |
| `css-all` | `DOCUMENT` | `LIST_DOCUMENT` |
| `css-remove` | `DOCUMENT` | `DOCUMENT` |
| `xpath` | `DOCUMENT` | `DOCUMENT` |
| `xpath-all` | `DOCUMENT` | `LIST_DOCUMENT` |
| `xpath-remove` | `DOCUMENT` | `DOCUMENT` |

### Extract

| Операция | Accept | Return |
|----------|--------|--------|
| `text` | `DOCUMENT` | `STRING` |
| `text` | `LIST_DOCUMENT` | `LIST_STRING` |
| `raw` | `DOCUMENT` | `STRING` |
| `raw` | `LIST_DOCUMENT` | `LIST_STRING` |
| `attr` | `DOCUMENT` | `STRING` |
| `attr` | `LIST_DOCUMENT` | `LIST_STRING` |

### String

| Операция | Accept | Return |
|----------|--------|--------|
| `trim`/`ltrim`/`rtrim` | `STRING` | `STRING` |
| `upper`/`lower` | `STRING` | `STRING` |
| `normalize-space` | `STRING` | `STRING` |
| `rm-prefix`/`rm-suffix` | `STRING` | `STRING` |
| `rm-prefix-suffix` | `STRING` | `STRING` |
| `fmt` | `STRING` | `STRING` |
| `repl` | `STRING` | `STRING` |
| `unescape` | `STRING` | `STRING` |
| `split` | `STRING` | `LIST_STRING` |
| `join` | `LIST_STRING` | `STRING` |

### Regex

| Операция | Accept | Return |
|----------|--------|--------|
| `re` | `STRING` | `STRING` |
| `re` | `LIST_STRING` | `LIST_STRING` |
| `re-all` | `STRING` | `LIST_STRING` |
| `re-sub` | `STRING` | `STRING` |

### Type Conversions

| Операция | Accept | Return |
|----------|--------|--------|
| `to-int` | `STRING` | `INT` |
| `to-float` | `STRING` | `FLOAT` |
| `to-bool` | `DOCUMENT`/`STRING`/`INT` | `BOOL` |

### Array

| Операция | Accept | Return |
|----------|--------|--------|
| `index`/`first`/`last` | `LIST_*` | `<scalar>` |
| `slice` | `LIST_*` | `LIST_*` |
| `len` | `LIST_*`/`STRING` | `INT` |
| `unique` | `LIST_*` | `LIST_*` |

### Control Flow

| Операция | Accept | Return |
|----------|--------|--------|
| `filter` | `LIST_*` | `LIST_*` (прозрачный) |
| `assert` | любой | тот же (прозрачный) |
| `match` | `DOCUMENT` | `STRING` |
| `fallback <value>` | любой | тот же / `OPT_*` |
| `fallback {}` | `LIST_*` | `LIST_*` |
| `self` | - | тип @init поля |

### Structured

| Операция | Accept | Return |
|----------|--------|--------|
| `nested` | `DOCUMENT` | `NESTED` |
| `jsonify` | `STRING` | `JSON` |
| `transform` | по `accept` | по `return` |
| `expr` (dsl/define) | зависит от содержимого | зависит от содержимого |

---

## Распространённые ошибки типов

### Строковая операция на DOCUMENT

```kdl
// ОШИБКА: trim не принимает DOCUMENT
field { css ".x"; trim }

// ПРАВИЛЬНО: сначала extract
field { css ".x"; text; trim }
```

### filter на скаляре

```kdl
// ОШИБКА: filter требует LIST_*
field { css ".x"; text; filter { contains "a" } }

// ПРАВИЛЬНО: использовать assert
field { css ".x"; text; assert { contains "a" } }
```

### Несовместимый fallback

```kdl
// ОШИБКА: строковый fallback для INT pipeline
field { css ".x"; text; to-int; fallback "N/A" }

// ПРАВИЛЬНО: числовой fallback
field { css ".x"; text; to-int; fallback 0 }

// или null
field { css ".x"; text; to-int; fallback #null }
```

### join на строке

```kdl
// ОШИБКА: join требует LIST_STRING
field { css ".x"; text; join "," }

// ПРАВИЛЬНО: сначала split
field { css ".x"; text; split " "; join "," }
```
