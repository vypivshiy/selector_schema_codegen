# Система типов

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Линтер проверяет совместимость типов в pipeline на этапе компиляции.

## VariableType

Скалярные:

| Тип | Описание |
|---|---|
| `DOCUMENT` | HTML/XML элемент |
| `STRING` | Строка |
| `INT` | Целое число |
| `FLOAT` | Число с плавающей точкой |
| `BOOL` | Логическое значение |
| `NULL` | Null/None |
| `NESTED` | Результат `nested` (терминальный, pipeline завершается) |
| `JSON` | Результат `jsonify` (терминальный, pipeline завершается) |

Списочные:

| Тип | Описание |
|---|---|
| `LIST_DOCUMENT` | Список элементов |
| `LIST_STRING` | Список строк |
| `LIST_INT` | Список целых |
| `LIST_FLOAT` | Список float |

Optional:

| Тип | Описание |
|---|---|
| `OPT_STRING` | `STRING | null` |
| `OPT_INT` | `INT | null` |
| `OPT_FLOAT` | `FLOAT | null` |

Специальные:

| Тип | Описание |
|---|---|
| `AUTO` | Автовыведение (любой скаляр) |
| `LIST_AUTO` | Автовыведение (любой список) |

## Поток типов в pipeline

- Pipeline обычно начинается с `DOCUMENT`.
- `@init` поля имеют свой тип и могут менять стартовый тип поля.
- Многие операции автоматически работают по элементам списка (map-семантика).
- `index`/`first`/`last` превращают список в скаляр.

Пример:

```kdl
tags {
    css-all ".tag"   // DOCUMENT -> LIST_DOCUMENT
    text             // LIST_DOCUMENT -> LIST_STRING
    lower            // LIST_STRING -> LIST_STRING
}
```

## AUTO и LIST_AUTO

`AUTO` и `LIST_AUTO` используются для вывода типов:
- в блоковых `define`;
- в `@init` до вычисления фактического типа;
- при совместимости списков и скаляров в типчеке.

## Optional типы и fallback

`fallback #null` делает тип optional:

```kdl
price {
    css ".price"
    text
    to-float
    fallback #null   // FLOAT -> OPT_FLOAT
}
```

`fallback {}` — сахар для пустого списка, разрешен только для LIST_*.

## accept/return в transform и dsl

`transform` требует `accept` и `return` из набора типов, кроме `AUTO` и `LIST_AUTO`.

`dsl` допускает `accept` и `return` только из:

`DOCUMENT`, `LIST_DOCUMENT`, `STRING`, `LIST_STRING`, `INT`, `LIST_INT`, `FLOAT`,
`LIST_FLOAT`, `BOOL`, `NULL`, `OPT_STRING`, `OPT_INT`, `OPT_FLOAT`.
