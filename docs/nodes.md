# AST Nodes Reference

> **Version:** 2.0  
> **Last Updated:** 2026-03-13

Актуальная сводка AST-нод и DSL-имен на основе реализаций из `ssc_codegen/kdl/ast/*` и регистраций в `ssc_codegen/kdl/parser.py`.

---

## Overview

Все AST-ноды наследуются от базового класса `Node`:

```python
@dataclass
class Node:
    accept: VariableType = field(default=VariableType.AUTO)
    ret: VariableType = field(default=VariableType.AUTO)
    parent: Node | None = field(default=None, repr=False)
    body: list[Node] = field(default_factory=list)
```

### VariableType

Поддерживаемые типы:

- `AUTO`, `LIST_AUTO`
- `DOCUMENT`, `LIST_DOCUMENT`
- `STRING`, `OPT_STRING`, `LIST_STRING`
- `INT`, `OPT_INT`, `LIST_INT`
- `FLOAT`, `OPT_FLOAT`, `LIST_FLOAT`
- `BOOL`, `NULL`, `NESTED`, `JSON`

### StructType

- `ITEM`
- `LIST`
- `DICT`
- `TABLE`
- `FLAT`

---

## DSL entries recognized by parser

Это не всегда отдельные AST-ноды, но это реальные имена, которые знает `parser.py`.

### Module-level DSL entries

- `@doc`
- `define`
- `transform`
- `struct`
- `json`

### Struct-level DSL entries

- `@doc`
- `@init`
- `@pre-validate`
- `@split-doc`
- `@key`
- `@value`
- `@table`
- `@rows`
- `@match`
- `<field-name>`

### Pipeline expression names

- `css`, `css-all`, `xpath`, `xpath-all`, `css-remove`, `xpath-remove`
- `text`, `raw`, `attr`
- `trim`, `ltrim`, `rtrim`, `normalize-space`
- `rm-prefix`, `rm-suffix`, `rm-prefix-suffix`
- `fmt`, `repl`, `lower`, `upper`, `split`, `join`, `unescape`
- `re`, `re-all`, `re-sub`
- `index`, `first`, `last`, `slice`, `len`, `unique`
- `to-int`, `to-float`, `to-bool`
- `jsonify`, `nested`, `fallback`, `filter`, `assert`, `match`, `transform`
- `@name` — ссылка на значение из `@init` (парсер превращает это в `Self`)

### Predicate names inside `filter` / `assert` / `match`

- `eq`, `ne`, `gt`, `lt`, `ge`, `le`, `range`
- `starts`, `ends`, `contains`, `in`
- `re`, `re-all`, `re-any`
- `css`, `xpath`, `has-attr`
- `attr-eq`, `attr-ne`, `attr-starts`, `attr-ends`, `attr-contains`, `attr-re`
- `text-starts`, `text-ends`, `text-contains`, `text-re`
- `len-eq`, `len-gt`
- `and`, `or`, `not`

> **Note:** в AST есть `PredCountLt`, но в текущем `parser.py` отдельное имя `len-lt` не зарегистрировано. Вместо этого второй раз зарегистрирован `len-eq`, который создаёт `PredCountLt`.

---

## Module-level AST nodes

| AST class | DSL | Назначение |
|---|---|---|
| `Module` | — | Корневой AST-узел модуля |
| `Docstring` | `@doc` | Документация модуля |
| `Imports` | — | Техническая секция импортов для codegen |
| `Utilities` | — | Техническая секция helper-функций |
| `CodeStartHook` | — | Точка вставки кода в начале файла |
| `CodeEndHook` | — | Точка вставки кода в конце файла |
| `JsonDef` | `json` | JSON schema definition |
| `TransformDef` | `transform` | Модульное определение transform |
| `Struct` | `struct` | Описание структуры парсинга |
| `TypeDef` | — | Автогенерируемое описание типа для `Struct` |

### `Module`

`Module.__post_init__()` заранее добавляет в `body`:

1. `Docstring`
2. `Imports`
3. `Utilities`
4. `CodeStartHook`

А уже после парсинга в `body` добавляются `TransformDef`, `TypeDef`, `Struct`.

### `Docstring`

```python
@dataclass
class Docstring(Node):
    value: str = ""
```

**DSL:**
```kdl
@doc "module docs"
```

---

## Struct AST nodes

| AST class | DSL | Назначение |
|---|---|---|
| `Struct` | `struct` | Структура парсинга |
| `StructDocstring` | `@doc` внутри `struct` | Документация структуры |
| `Init` | `@init` | Контейнер для предвычисляемых pipeline |
| `InitField` | `<name>` внутри `@init` | Одно предвычисляемое значение |
| `PreValidate` | `@pre-validate` | Валидация документа перед парсингом |
| `SplitDoc` | `@split-doc` | Деление документа на элементы |
| `Key` | `@key` | Ключ для `StructType.DICT` |
| `Value` | `@value` | Значение для `DICT` / `TABLE` |
| `TableConfig` | `@table` | Выбор таблицы |
| `TableRow` | `@rows` | Выбор строк таблицы |
| `TableMatchKey` | `@match` | Извлечение ключевой ячейки для table-match |
| `Field` | `<field-name>` | Обычное выходное поле |
| `StartParse` | — | Техническая нода, добавляется в конец `Struct.body` |

### `Struct`

```python
@dataclass
class Struct(Node):
    name: str = ""
    struct_type: StructType = StructType.ITEM
    keep_order: bool = False
```

**DSL:**
```kdl
struct Product {}
struct ProductList type=list {}
struct Meta type=dict {}
struct PriceTable type=table {}
struct FlatList type=flat keep-order=#true {}
```

### `StructDocstring`

```python
@dataclass
class StructDocstring(Node):
    value: str = ""
```

**DSL:**
```kdl
struct Example {
    @doc "struct docs"
}
```

### `Init` / `InitField`

`Init` — контейнер, `InitField` — конкретный pipeline с именем.

**DSL:**
```kdl
struct Example {
    @init {
        raw-json {
            raw
            re #"\{.*\}"#
        }
    }

    data {
        @raw-json
        jsonify Quote
    }
}
```

### `PreValidate`

- `accept = DOCUMENT`
- `ret = DOCUMENT`

**DSL:**
```kdl
@pre-validate {
    assert { css ".required" }
}
```

### `SplitDoc`

- `accept = DOCUMENT`
- `ret = LIST_DOCUMENT`

**DSL:**
```kdl
@split-doc { css-all ".item" }
```

### `Key` / `Value`

**DSL:**
```kdl
struct Meta type=dict {
    @split-doc { css-all "meta" }
    @key { attr "property" }
    @value { attr "content" }
}
```

### `TableConfig` / `TableRow` / `TableMatchKey`

**DSL:**
```kdl
struct ProductInfo type=table {
    @table { css "table" }
    @rows { css-all "tr" }
    @match { css "th" text lower }
    @value { css "td" text }
}
```

### `Field`

Для обычных структур `Field.accept` по умолчанию `DOCUMENT`.
Для `type=table` поле создаётся с `accept=STRING`.

### `StartParse`

Техническая нода, парсер всегда добавляет её в конец `Struct.body` после разбора структуры.

---

## Selector nodes

| AST class | DSL | Типы |
|---|---|---|
| `CssSelect` | `css` | `DOCUMENT -> DOCUMENT` |
| `CssSelectAll` | `css-all` | `DOCUMENT -> LIST_DOCUMENT` |
| `XpathSelect` | `xpath` | `DOCUMENT -> DOCUMENT` |
| `XpathSelectAll` | `xpath-all` | `DOCUMENT -> LIST_DOCUMENT` |
| `CssRemove` | `css-remove` | `DOCUMENT -> DOCUMENT` |
| `XpathRemove` | `xpath-remove` | `DOCUMENT -> DOCUMENT` |

**Пример:**
```kdl
title {
    css "h1"
    text
}
```

---

## Extract nodes

| AST class | DSL | Типы |
|---|---|---|
| `Text` | `text` | `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING` |
| `Raw` | `raw` | `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING` |
| `Attr` | `attr` | зависит от числа ключей и предыдущего типа |

### `Attr`

```python
@dataclass
class Attr(Node):
    keys: tuple[str, ...] = field(default_factory=tuple)
```

**DSL:**
```kdl
attr "href"
attr "class" "data-value"
```

Если ключ один, обычно результат скалярный. Если ключей несколько, результат используется как список строк.

---

## String operation nodes

| AST class | DSL |
|---|---|
| `Trim` | `trim` |
| `Ltrim` | `ltrim` |
| `Rtrim` | `rtrim` |
| `NormalizeSpace` | `normalize-space` |
| `RmPrefix` | `rm-prefix` |
| `RmSuffix` | `rm-suffix` |
| `RmPrefixSuffix` | `rm-prefix-suffix` |
| `Fmt` | `fmt` |
| `Repl` | `repl old new` |
| `ReplMap` | `repl { old new ... }` |
| `Lower` | `lower` |
| `Upper` | `upper` |
| `Split` | `split` |
| `Join` | `join` |
| `Unescape` | `unescape` |

Большинство этих нод работают по map-semantics:

- `STRING -> STRING`
- `LIST_STRING -> LIST_STRING`

Исключения:

- `Split`: `STRING -> LIST_STRING`
- `Join`: `LIST_STRING -> STRING`

**Примеры:**
```kdl
name { text trim normalize-space }
slug { text lower rm-prefix "/" rm-suffix ".html" }
url { attr "href" fmt "https://example.com/{{}}" }
rating { text repl "One" "1" }
parts { text split "," }
joined { text split "," join " | " }
```

---

## Regex nodes

| AST class | DSL | Типы |
|---|---|---|
| `Re` | `re` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |
| `ReAll` | `re-all` | `STRING -> LIST_STRING` |
| `ReSub` | `re-sub` | `STRING -> STRING`, `LIST_STRING -> LIST_STRING` |

Паттерны нормализуются через `normalize_regex_pattern()`.

**Примеры:**
```kdl
price { text re #"(\d+\.\d+)"# }
nums { text re-all #"\d+"# }
clean { text re-sub #"\s+"# " " }
```

---

## Array / collection nodes

| AST class | DSL | Назначение |
|---|---|---|
| `Index` | `index` | Взять элемент по индексу |
| `Index` | `first` | Сокращение для первого элемента |
| `Index` | `last` | Сокращение для последнего элемента |
| `Slice` | `slice` | Взять диапазон |
| `Len` | `len` | Длина списка |
| `Unique` | `unique` | Убрать дубликаты из списка строк |

**Примеры:**
```kdl
first-link { css-all "a" attr "href" first }
last-link { css-all "a" attr "href" last }
subset { css-all "a" attr "href" slice 0 10 }
count { css-all "a" len }
uniq { css-all "a" attr "href" unique }
```

---

## Cast / conversion nodes

| AST class | DSL | Типы |
|---|---|---|
| `ToInt` | `to-int` | `STRING -> INT`, `LIST_STRING -> LIST_INT` |
| `ToFloat` | `to-float` | `STRING -> FLOAT`, `LIST_STRING -> LIST_FLOAT` |
| `ToBool` | `to-bool` | `AUTO -> BOOL` |
| `Jsonify` | `jsonify` | `STRING -> JSON` |
| `Nested` | `nested` | `DOCUMENT -> NESTED` |

### `Jsonify`

```python
@dataclass
class Jsonify(Node):
    schema_name: str = ""
    path: str | None = None
    is_array: bool = False
```

**DSL:**
```kdl
payload { text jsonify Quote }
payload { text jsonify Quote path="0.author" }
```

### `Nested`

```kdl
books {
    css-all ".book"
    nested Book
}
```

---

## Control and flow nodes

| AST class | DSL | Назначение |
|---|---|---|
| `Fallback` | `fallback` | Вернуть literal при ошибке pipeline |
| `FallbackStart` | — | Техническая служебная нода |
| `FallbackEnd` | — | Техническая служебная нода |
| `Self` | `@init-name` | Ссылка на уже вычисленное значение |
| `Return` | — | Неявный конец pipeline |
| `Filter` | `filter` | Фильтрация списка по предикатам |
| `Assert` | `assert` | Проверка значения без изменения |
| `Match` | `match` | Table-match контейнер |

### `Fallback`

**DSL:**
```kdl
value { text to-int fallback 0 }
value { text fallback #null }
```

### `Self`

`Self` остаётся AST-нодой, но в DSL создаётся только через специальную ссылку:

- `@name` — ссылка на `InitField`

Это должен быть первый шаг pipeline.

### `Return`

`Return` не пишется в DSL: парсер автоматически добавляет его в конец каждого верхнеуровневого pipeline.

---

## Predicate container nodes

| AST class | DSL | Назначение |
|---|---|---|
| `Filter` | `filter { ... }` | Фильтрация списков |
| `Assert` | `assert { ... }` | Проверка без изменения значения |
| `Match` | `match { ... }` | Выбор строки в table-парсере |
| `LogicAnd` | `and { ... }` | Явная логическая группировка AND |
| `LogicOr` | `or { ... }` | Логическая группировка OR |
| `LogicNot` | `not { ... }` | Инверсия вложенного блока |

**Примеры:**
```kdl
filter {
    or {
        contains "foo"
        contains "bar"
    }
}

assert {
    not {
        css ".disabled"
    }
}
```

---

## Predicate operation nodes

### Comparison / scalar predicates

| AST class | DSL |
|---|---|
| `PredEq` | `eq` |
| `PredNe` | `ne` |
| `PredGt` | `gt` |
| `PredLt` | `lt` |
| `PredGe` | `ge` |
| `PredLe` | `le` |
| `PredRange` | `range` |
| `PredStarts` | `starts` |
| `PredEnds` | `ends` |
| `PredContains` | `contains` |
| `PredIn` | `in` |

### Regex predicates

| AST class | DSL | Ограничения |
|---|---|---|
| `PredRe` | `re` | доступен в `filter`, `assert`, `match` |
| `PredReAll` | `re-all` | только `assert` |
| `PredReAny` | `re-any` | только `assert` |

### Document predicates

| AST class | DSL | Ограничения |
|---|---|---|
| `PredCss` | `css` | `filter`, `assert` |
| `PredXpath` | `xpath` | `filter`, `assert` |
| `PredHasAttr` | `has-attr` | `filter`, `assert` |
| `PredAttrEq` | `attr-eq` | `filter`, `assert` |
| `PredAttrNe` | `attr-ne` | `filter`, `assert` |
| `PredAttrStarts` | `attr-starts` | `filter`, `assert` |
| `PredAttrEnds` | `attr-ends` | `filter`, `assert` |
| `PredAttrContains` | `attr-contains` | `filter`, `assert` |
| `PredAttrRe` | `attr-re` | `filter`, `assert` |
| `PredTextStarts` | `text-starts` | `filter`, `assert` |
| `PredTextEnds` | `text-ends` | `filter`, `assert` |
| `PredTextContains` | `text-contains` | `filter`, `assert` |
| `PredTextRe` | `text-re` | `filter`, `assert` |

### List-length predicates

| AST class | Parser registration |
|---|---|
| `PredCountEq` | `len-eq` |
| `PredCountGt` | `len-gt` |
| `PredCountLt` | AST есть, но отдельное `len-lt` сейчас не зарегистрировано |

---

## JSON nodes

| AST class | DSL |
|---|---|
| `JsonDef` | `json` |
| `JsonDefField` | `<field-name> <type>` внутри `json` |
| `Jsonify` | `jsonify` |

### `JsonDef`

**DSL:**
```kdl
json Quote array=#true {
    text str
    author Author
    tags (array)str
}
```

### `JsonDefField`

```python
@dataclass
class JsonDefField(Node):
    name: str = ""
    type_name: str = ""
    is_optional: bool = False
    is_array: bool = False
    ref_name: str | None = None
```

Парсер при разборе вычисляет `ret`, `is_optional`, `is_array`, `ref_name` по содержимому DSL.

---

## Transform nodes

| AST class | DSL | Назначение |
|---|---|---|
| `TransformDef` | `transform` на уровне модуля | Определение transform |
| `TransformTarget` | языковой блок (`py`, `js`, ...) | Реализация transform для языка |
| `TransformCall` | `transform name` в pipeline | Вызов transform |

### `TransformDef`

**DSL:**
```kdl
transform to-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64encode"
        code "{{NXT}} = b64encode({{PRV}}.encode()).decode()"
    }
}
```

### `TransformTarget`

```python
@dataclass
class TransformTarget(Node):
    lang: str = ""
    imports: tuple[str, ...] = field(default_factory=tuple)
    code: tuple[str, ...] = field(default_factory=tuple)
```

### `TransformCall`

**DSL:**
```kdl
title {
    text
    transform to-base64
}
```

---

## TypeDef nodes

| AST class | DSL |
|---|---|
| `TypeDef` | —, генерируется автоматически |
| `TypeDefField` | —, генерируется автоматически |

`TypeDef` строится из `Struct` после парсинга и используется конвертерами для типовой информации.

---

## Summary of missing/outdated items fixed in this document

Эта версия документации синхронизирована с текущими AST и `parser.py`, в частности отражает:

- реальные DSL-имена с `@...` для struct/module special nodes
- наличие технических нод: `CodeStartHook`, `CodeEndHook`, `Utilities`, `StartParse`, `Return`
- отсутствовавшие expression/AST names: `StructDocstring`, `Init`, `NormalizeSpace`, `RmPrefixSuffix`, `ReplMap`, `Join`, `Unescape`, `Index`, `Slice`, `Unique`, `TransformCall`, `LogicAnd`, `LogicOr`, `LogicNot` и др.
- полный набор parser expression names, включая `first`, `last`, `transform`, `filter`, `assert`, `match`
- полный набор predicate names из парсера
- отличие между AST и текущей регистрацией `len-*` предикатов в `parser.py`
