# AST Nodes Reference

> **Version:** 2.0  
> **Last Updated:** 2026-03-11

Полное описание всех AST нод в KDL Schema DSL.

---

## Table of Contents

- [Overview](#overview)
- [Module Level Nodes](#module-level-nodes)
- [Struct Nodes](#struct-nodes)
- [Field Nodes](#field-nodes)
- [Selector Nodes](#selector-nodes)
- [Extract Nodes](#extract-nodes)
- [String Operations](#string-operations)
- [Type Conversion Nodes](#type-conversion-nodes)
- [Predicate Nodes](#predicate-nodes)
- [JSON Nodes](#json-nodes)
- [Transform Nodes](#transform-nodes)
- [Control Flow Nodes](#control-flow-nodes)

---

## Overview

Все AST ноды наследуются от базового класса `Node`:

```python
@dataclass
class Node:
    parent: Node | None = None
    ret: VariableType = VariableType.NULL
```

**Основные свойства:**
- `parent` - ссылка на родительскую ноду
- `ret` - тип возвращаемого значения
- Каждая нода имеет специфичные поля

---

## Module Level Nodes

### `Module`

Корневой узел модуля.

```python
@dataclass
class Module(Node):
    name: str = ""
    body: list[Node] = field(default_factory=list)
    imports: Imports = field(default_factory=Imports)
    utilities: Utilities = field(default_factory=Utilities)
```

**Содержит:**
- `body` - список структур, JSON схем, transform'ов
- `imports` - секция импортов
- `utilities` - утилитарные функции

---

### `Imports`

Секция импортов модуля.

```python
@dataclass
class Imports(Node):
    libs: list[str] = field(default_factory=list)
    transform_imports: dict[str, set[str]] = field(default_factory=dict)
```

**Особенности:**
- `transform_imports` - импорты из transform'ов, собранные при парсинге
- Ключи: `"py"`, `"js"` и т.д.
- Автоматически заполняется парсером

**Пример:**
```python
# После парсинга transform с импортами
module.imports.transform_imports = {
    "py": {"from base64 import b64decode"},
    "js": set()
}
```

---

### `Docstring`

Документация модуля или структуры.

```python
@dataclass
class Docstring(Node):
    content: str = ""
```

**DSL:**
```kdl
@doc """
Module documentation
Multi-line supported
"""
```

---

## Struct Nodes

### `Struct`

Основная структура данных.

```python
@dataclass  
class Struct(Node):
    name: str = ""
    struct_type: StructType = StructType.ITEM
    body: list[Field | Key | Value] = field(default_factory=list)
    init: Init = field(default_factory=Init)
    pre_validate: PreValidate | None = None
    split_doc: SplitDoc | None = None
    table_config: TableConfig | None = None
    table_match_key: TableMatchKey | None = None
    table_row: TableRow | None = None
```

**Типы структур (`StructType`):**
- `ITEM = 1` - один объект
- `LIST = 2` - список объектов
- `DICT = 3` - словарь
- `FLAT = 4` - плоский список
- `TABLE = 5` - таблица

**DSL:**
```kdl
struct MainCatalogue { ... }           // type=item (default)
struct Book type=list { ... }
struct Metadata type=dict { ... }
struct ProductInfo type=table { ... }
```

---

### `Field`

Поле структуры с pipeline операций.

```python
@dataclass
class Field(Node):
    name: str = ""
    body: list[Node] = field(default_factory=list)
    accept: VariableType = VariableType.DOCUMENT
```

**DSL:**
```kdl
title {
    css "h1"
    text
    trim
}
```

**Pipeline:**
1. Селекторы (`css`, `xpath`)
2. Извлечение (`text`, `attr`, `raw`)
3. Трансформации (`trim`, `upper`, `re`)
4. Конвертация типов (`to-int`, `to-float`)

---

### `InitField`

Предвычисленное поле в `@init`.

```python
@dataclass
class InitField(Node):
    name: str = ""
    body: list[Node] = field(default_factory=list)
    accept: VariableType = VariableType.DOCUMENT
```

**DSL:**
```kdl
-init {
    raw-json {
        raw
        re JSON-PATTERN
    }
}
```

**Использование:**
```kdl
data {
    @raw-json  // Ссылка на InitField
    jsonify Quote
}
```

---

### `Key` / `Value`

Специальные поля для `type=dict`.

```python
@dataclass
class Key(Node):
    body: list[Node] = field(default_factory=list)

@dataclass
class Value(Node):
    body: list[Node] = field(default_factory=list)
```

**DSL:**
```kdl
struct Metadata type=dict {
    @split-doc { css-all "meta" }
    
    @key {
        attr "property"
    }
    
    @value {
        attr "content"
    }
}
```

---

### Special Struct Fields

#### `PreValidate`

Валидация документа перед парсингом.

```python
@dataclass
class PreValidate(Node):
    body: list[Node] = field(default_factory=list)
```

**DSL:**
```kdl
-pre-validate {
    assert { css ".required-element" }
}
```

---

#### `SplitDoc`

Разбиение документа на элементы (для `type=list`, `type=dict`, `type=flat`).

```python
@dataclass
class SplitDoc(Node):
    body: list[Node] = field(default_factory=list)
```

**DSL:**
```kdl
-split-doc { css-all ".book-card" }
```

---

#### `TableConfig`, `TableMatchKey`, `TableRow`

Специальные поля для `type=table`.

```python
@dataclass
class TableConfig(Node):
    body: list[Node] = field(default_factory=list)

@dataclass
class TableMatchKey(Node):
    body: list[Node] = field(default_factory=list)

@dataclass
class TableRow(Node):
    body: list[Node] = field(default_factory=list)
```

**DSL:**
```kdl
struct ProductInfo type=table {
    @table { css "table" }
    @rows { css-all "tr" }
    @match { css "th"; text; lower }
    @value { css "td"; text }
}
```

---

## Selector Nodes

### CSS Selectors

```python
@dataclass
class CssSelect(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.DOCUMENT

@dataclass
class CssSelectAll(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.LIST_DOCUMENT

@dataclass
class CssRemove(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.DOCUMENT
```

**DSL:**
```kdl
css "h1"           // CssSelect
css-all "a"        // CssSelectAll
css-rm ".ads"      // CssRemove
```

**Типы:**
- `css`: `DOCUMENT → DOCUMENT`
- `css-all`: `DOCUMENT → LIST_DOCUMENT`
- `css-rm`: `DOCUMENT → DOCUMENT` (удаляет элементы, возвращает doc)

---

### XPath Selectors

```python
@dataclass
class XpathSelect(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.DOCUMENT

@dataclass
class XpathSelectAll(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.LIST_DOCUMENT

@dataclass
class XpathRemove(Node):
    query: str = ""
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.DOCUMENT
```

**DSL:**
```kdl
xpath "//div[@class='content']"
xpath-all "//a"
xpath-rm "//script"
```

---

## Extract Nodes

### `Text`

Извлечение текстового содержимого.

```python
@dataclass
class Text(Node):
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.STRING
```

**Типы:**
- `DOCUMENT → STRING`
- `LIST_DOCUMENT → LIST_STRING`

**DSL:**
```kdl
title { css "h1"; text }
```

**Генерируемый код:**
```python
# bs4
v2 = v1.text

# lxml
v2 = v1.text_content()
```

---

### `Attr`

Извлечение атрибутов.

```python
@dataclass
class Attr(Node):
    keys: tuple[str, ...] = field(default_factory=tuple)
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
attr "href"                      // Один атрибут
attr "class" "data-value"        // Конкатенация атрибутов
```

**Генерируемый код:**
```python
# bs4
v2 = ' '.join(v1.get_attribute_list('href'))

# lxml
v2 = v1.get('href', '')
```

---

### `Raw`

Извлечение HTML кода.

```python
@dataclass
class Raw(Node):
    accept: VariableType = VariableType.DOCUMENT
    ret: VariableType = VariableType.STRING
```

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

### `Trim` / `LTrim` / `RTrim`

```python
@dataclass
class Trim(Node):
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
text { css "p"; text; trim }
```

---

### `Upper` / `Lower`

```python
@dataclass
class Upper(Node):
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING

@dataclass
class Lower(Node):
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

---

### `RmPrefix` / `RmSuffix`

```python
@dataclass
class RmPrefix(Node):
    value: str = ""
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
rm-prefix "../"
rm-suffix ".html"
```

---

### `Fmt`

Форматирование строки с шаблоном.

```python
@dataclass
class Fmt(Node):
    template: str = ""
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
define FMT-URL="https://example.com/{{}}"

url { css "a"; attr "href"; fmt FMT-URL }
```

**Генерируемый код:**
```python
v3 = "https://example.com/{}".format(v2)
```

---

### `Re` - Regex extraction

```python
@dataclass
class Re(Node):
    pattern: str = ""  # Inline форма с флагами: (?is)pattern
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
price { css ".price"; text; re #"(\d+\.\d+)"# }
```

**Генерируемый код:**
```python
v3 = re.search('(?s)\\d+\\.\\d+', v2)[1]
```

**Особенности:**
- Паттерн нормализован: VERBOSE удален, флаги inline
- Возвращает первую группу захвата

---

### `ReAll` - All regex matches

```python
@dataclass
class ReAll(Node):
    pattern: str = ""
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.LIST_STRING
```

**DSL:**
```kdl
numbers { css ".text"; text; re-all #"\d+"# }
```

**Типы:**
- `STRING → LIST_STRING`

---

### `ReSub` - Regex substitution

```python
@dataclass
class ReSub(Node):
    pattern: str = ""
    repl: str = ""
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
clean { css ".text"; text; re-sub #"\s+" " " }
```

---

### `Repl` - Dictionary replacement

```python
@dataclass
class Repl(Node):
    mapping: dict[str, str] = field(default_factory=dict)
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
define REPL-RATING {
    repl {
        One "1"
        Two "2"
    }
}

rating { css ".rating"; attr "class"; REPL-RATING }
```

---

## Type Conversion Nodes

### `ToInt` / `ToFloat` / `ToBool`

```python
@dataclass
class ToInt(Node):
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.INT

@dataclass
class ToFloat(Node):
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.FLOAT

@dataclass
class ToBool(Node):
    accept: VariableType = VariableType.AUTO
    ret: VariableType = VariableType.BOOL
```

**DSL:**
```kdl
count { css ".count"; text; to-int }
price { css ".price"; text; to-float }
active { css ".active"; to-bool }
```

---

### `Len`

```python
@dataclass
class Len(Node):
    accept: VariableType = VariableType.LIST_AUTO
    ret: VariableType = VariableType.INT
```

**DSL:**
```kdl
links-count { css-all "a"; len }
```

**Типы:**
- `LIST_* → INT`
- `STRING → INT`

---

### `Fallback`

```python
@dataclass
class Fallback(Node):
    value: str | int | float | bool | None = None
```

**DSL:**
```kdl
fallback #null
fallback #true
fallback 0
fallback "default"
```

---

## Predicate Nodes

Используются в `match { ... }` и `assert { ... }`.

### String Predicates

```python
@dataclass
class PredEq(Node):
    values: tuple[str, ...] = field(default_factory=tuple)

@dataclass
class PredStarts(Node):
    values: tuple[str, ...] = field(default_factory=tuple)

@dataclass
class PredEnds(Node):
    values: tuple[str, ...] = field(default_factory=tuple)

@dataclass
class PredContains(Node):
    values: tuple[str, ...] = field(default_factory=tuple)
```

**DSL:**
```kdl
match { eq "value" }
match { starts "prefix" }
match { ends "suffix" }
match { contains "substring" }
```

---

### Regex Predicates

```python
@dataclass
class PredRe(Node):
    pattern: str = ""  # Normalized inline form

@dataclass
class PredReAll(Node):
    pattern: str = ""

@dataclass
class PredReAny(Node):
    pattern: str = ""
```

**DSL:**
```kdl
match { re #"pattern"# }
assert { re-all #"pattern"# }  // Все элементы соответствуют
assert { re-any #"pattern"# }  // Хотя бы один
```

---

### Attribute Predicates

```python
@dataclass
class PredHasAttr(Node):
    attrs: tuple[str, ...] = field(default_factory=tuple)

@dataclass
class PredAttrEq(Node):
    name: str = ""
    values: tuple[str, ...] = field(default_factory=tuple)

@dataclass
class PredAttrRe(Node):
    name: str = ""
    pattern: str = ""
```

**DSL:**
```kdl
match { has-attr "class" }
match { attr-eq "class" "active" }
match { attr-re "href" #"^https"# }
```

---

### Element Predicates

```python
@dataclass
class PredCss(Node):
    query: str = ""

@dataclass
class PredXpath(Node):
    query: str = ""
```

**DSL:**
```kdl
assert { css ".required" }
assert { xpath "//div[@id='main']" }
```

---

## JSON Nodes

### `JsonDef`

Определение JSON схемы.

```python
@dataclass
class JsonDef(Node):
    name: str = ""
    is_array: bool = False
    body: list[JsonDefField] = field(default_factory=list)
```

**DSL:**
```kdl
json Quote array=#true {
    text str
    author Author
    tags (array)str
}
```

---

### `JsonDefField`

Поле JSON схемы.

```python
@dataclass
class JsonDefField(Node):
    name: str = ""
    ret: VariableType = VariableType.STRING
    is_array: bool = False
    ref_name: str = ""  # Ссылка на другую JSON схему
```

**DSL:**
```kdl
text str              // ret=STRING, is_array=False
tags (array)str       // ret=STRING, is_array=True
author Author         // ret=JSON, ref_name="Author"
```

---

### `Jsonify`

Применение JSON схемы к данным.

```python
@dataclass
class Jsonify(Node):
    schema_name: str = ""
    path: str | None = None
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.JSON
    is_array: bool = False
```

**DSL:**
```kdl
jsonify Quote                       // Применить схему
jsonify Quote path="0"              // Взять первый элемент
jsonify Quote path="2.author.slug"  // Навигация по полям
```

**path навигация:**
- Пустой path: применить схему к результату
- Числовой индекс: unwrap array
- Путь через точку: навигация по полям

**is_array:**
- `True` если результат - массив
- `False` если результат - одиночный объект

---

## Transform Nodes

### `TransformDef`

Определение transform функции.

```python
@dataclass
class TransformDef(Node):
    name: str = ""
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
    body: list[TransformTarget] = field(default_factory=list)
```

**DSL:**
```kdl
transform to-base64 accept=STRING return=STRING {
    py { ... }
    js { ... }
}
```

---

### `TransformTarget`

Реализация transform для конкретного языка.

```python
@dataclass
class TransformTarget(Node):
    lang: str = ""  # "py", "js", etc.
    imports: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
```

**DSL:**
```kdl
py {
    import "from base64 import b64decode"
    code "{{NXT}} = str(b64decode({{PRV}}))"
}
```

**Placeholders:**
- `{{PRV}}` - предыдущее значение
- `{{NXT}}` - результирующее значение

---

### `TransformCall`

Вызов transform в pipeline.

```python
@dataclass
class TransformCall(Node):
    name: str = ""
    transform_def: TransformDef | None = None
    accept: VariableType = VariableType.STRING
    ret: VariableType = VariableType.STRING
```

**DSL:**
```kdl
title {
    css "title"
    text
    transform to-base64
}
```

**Особенности:**
- `transform_def` - ссылка на определение transform
- Импорты автоматически регистрируются в `Module.imports.transform_imports`

---

## Control Flow Nodes

### `Filter`

Фильтрация списка по предикатам.

```python
@dataclass
class Filter(Node):
    body: list[Node] = field(default_factory=list)  # Predicates
    accept: VariableType = VariableType.LIST_DOCUMENT
    ret: VariableType = VariableType.LIST_DOCUMENT
```

**DSL:**
```kdl
match {
    css ".active"
    attr-eq "class" "highlight"
}
```

---

### `Assert`

Проверка условия (выбрасывает исключение если false).

```python
@dataclass
class Assert(Node):
    body: list[Node] = field(default_factory=list)  # Predicates
```

**DSL:**
```kdl
assert { css ".required-element" }
assert { contains "In stock" }
```

---

### `Nested`

Вложенная структура.

```python
@dataclass
class Nested(Node):
    struct_name: str = ""
    is_array: bool = False
```

**DSL:**
```kdl
struct Book type=list { ... }

struct Catalogue {
    books { nested Book }  // is_array=True (Book is LIST type)
}
```

---

### `Self`

Ссылка на предвычисленное значение из `@init`.

```python
@dataclass
class Self(Node):
    name: str = ""
```

**DSL:**
```kdl
-init {
    raw-json { raw; re PATTERN }
}

data {
    @raw-json  // Использование
    jsonify Quote
}
```

---

### `Return`

Явное возвращение значения (обычно не требуется).

```python
@dataclass
class Return(Node):
    pass
```

---

## TypeDef Nodes

### `TypeDef`

Определение типа для структуры (генерируется автоматически).

```python
@dataclass
class TypeDef(Node):
    name: str = ""
    struct_type: StructType = StructType.ITEM
    body: list[TypeDefField] = field(default_factory=list)
```

**Используется для генерации:**
- Python: `TypedDict`
- JavaScript: TypeScript interfaces

---

### `TypeDefField`

Поле TypeDef.

```python
@dataclass
class TypeDefField(Node):
    name: str = ""
    ret: VariableType = VariableType.STRING
    is_array: bool = False
    nested_ref: str = ""  # Ссылка на nested struct
    json_ref: str = ""    # Ссылка на JSON schema
```

**Генерируется для:**
- Обычных полей
- Nested полей
- JSON полей
- Key/Value для dict типов

---

## Summary

**Категории нод:**
- **Module Level:** Module, Imports, Docstring
- **Structures:** Struct, Field, InitField, Key, Value
- **Selectors:** CssSelect, XpathSelect и варианты
- **Extract:** Text, Attr, Raw
- **String Ops:** Trim, Upper, Lower, Fmt, Re, Repl
- **Type Conv:** ToInt, ToFloat, ToBool, Len, Fallback
- **Predicates:** PredEq, PredRe, PredHasAttr и др.
- **JSON:** JsonDef, JsonDefField, Jsonify
- **Transforms:** TransformDef, TransformTarget, TransformCall
- **Control:** Filter, Assert, Nested, Self, Return

**Типы данных (`VariableType`):**
- `DOCUMENT` / `LIST_DOCUMENT`
- `STRING` / `LIST_STRING`
- `INT` / `LIST_INT`
- `FLOAT` / `LIST_FLOAT`
- `BOOL`
- `JSON`
- `NESTED`
- `AUTO` - автоопределение

**Все ноды типизированы** с проверкой `accept` → `ret` в compile-time.

