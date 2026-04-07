# Операции pipeline

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Каждая операция принимает входной тип (`accept`) и возвращает новый (`ret`).
Линтер проверяет совместимость типов по цепочке.

## Selectors

| Операция | Тип |
|---|---|
| `css <query>` | `DOCUMENT -> DOCUMENT` |
| `css-all <query>` | `DOCUMENT -> LIST_DOCUMENT` |
| `css-remove <query>` | `DOCUMENT -> DOCUMENT` |
| `xpath <query>` | `DOCUMENT -> DOCUMENT` |
| `xpath-all <query>` | `DOCUMENT -> LIST_DOCUMENT` |
| `xpath-remove <query>` | `DOCUMENT -> DOCUMENT` |

Дополнительно для `css`, `css-all`, `xpath`, `xpath-all` поддерживается
блочный pattern-match синтаксис:

```kdl
title {
    css {
        ".article-title"
        "h1.title"
        "h1"
    }
    text
}
```

Правила:
- Можно использовать либо один аргумент (`css ".title"`), либо block
  (`css { ".a"; ".b" }`), но не одновременно.
- В block должно быть минимум 2 селектора.
- Селекторы проверяются по порядку; берется первый непустой результат.
- Если ни один селектор не подошел, поведение как у обычного `css`/`xpath`
  (ошибка на этапе выполнения pipeline, если нет `fallback`).
- `css-remove` и `xpath-remove` block-синтаксис не поддерживают.

## Extract

| Операция | Тип |
|---|---|
| `text` | `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING` |
| `raw` | `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING` |
| `attr <name>` | `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING` |
| `attr <name1> <name2> ...` | `DOCUMENT -> LIST_STRING`, `LIST_DOCUMENT -> LIST_STRING` |

При одном ключе возвращает строку (мультизначные атрибуты вроде `class` объединяются через пробел).
При нескольких ключах возвращает список строк; отсутствующие атрибуты пропускаются.

## String

| Операция | Тип |
|---|---|
| `trim [chars]` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `ltrim [chars]` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `rtrim [chars]` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `normalize-space` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `fmt <template>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `repl <old> <new>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `repl { <old> <new> ... }` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `lower` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `upper` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `rm-prefix <substr>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `rm-suffix <substr>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `rm-prefix-suffix <substr>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `unescape` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `split <sep>` | `STRING -> LIST_STRING` |
| `join <sep>` | `LIST_STRING -> STRING` |

`fmt` требует шаблон с `{{}}` placeholder или скалярный `define`, содержащий его.

## Regex

| Операция | Тип |
|---|---|
| `re <pattern>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `re-all <pattern>` | `STRING -> LIST_STRING` |
| `re-sub <pattern> <repl>` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |

Правила:
- `re` в pipeline требует ровно одну capturing group.
- В предикатах `re` разрешен без ограничения групп.

## Array

| Операция | Тип |
|---|---|
| `index <i>` | `LIST_* -> scalar` |
| `first` | `LIST_* -> scalar` |
| `last` | `LIST_* -> scalar` |
| `slice <start> <end>` | `LIST_* -> LIST_*` |
| `len` | `LIST_* -> INT` |
| `unique` | `LIST_STRING -> LIST_STRING` |

## Conversions

| Операция | Тип |
|---|---|
| `to-int` | `STRING -> INT`, `LIST_STRING -> LIST_INT` |
| `to-float` | `STRING -> FLOAT`, `LIST_STRING -> LIST_FLOAT` |
| `to-bool` | любой скаляр -> `BOOL` |

## Structured

| Операция | Тип |
|---|---|
| `nested <StructName>` | `DOCUMENT -> NESTED` |
| `jsonify <SchemaName> [path="..."]` | `STRING -> JSON` |

## Control и служебные

| Операция | Назначение |
|---|---|
| `filter { ... }` | фильтрация списков по предикатам |
| `assert { ... }` | проверка условий без изменения значения |
| `match { ... }` | выбор строки в `type=table` |
| `fallback <value>|{}` | значение по умолчанию |
| `@name` / `self name` | ссылка на `@init` значение |
| `transform <Name>` | вызов transform |
| `expr <Name>` | вызов `dsl` блока или блочного define |

Ключевые правила:
- `match` обязателен для полей `type=table` и должен быть первой операцией.
- `filter` работает только со списками (`LIST_*`).
- `fallback {}` допустим только для `LIST_*`.
- `self name` — устаревший синтаксис, используйте `@name`.
