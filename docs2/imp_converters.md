# Руководство по реализации нового конвертера

Документ описывает, как добавить новый backend-конвертер поверх `BaseConverter`.
В качестве эталонной реализации используется `ssc_codegen/kdl/converters/py_bs4.py`.

---

## Содержание

- [Концепция](#концепция)
- [ConverterContext](#convertercontext)
- [Система регистрации хендлеров](#система-регистрации-хендлеров)
- [Режимы обхода AST](#режимы-обхода-ast)
- [Структура нового конвертера](#структура-нового-конвертера)
- [Полный список узлов для реализации](#полный-список-узлов-для-реализации)
  - [Module level](#module-level)
  - [Struct level](#struct-level)
  - [Expressions — Selectors](#expressions--selectors)
  - [Expressions — Extract](#expressions--extract)
  - [Expressions — String](#expressions--string)
  - [Expressions — Regex](#expressions--regex)
  - [Expressions — Array](#expressions--array)
  - [Expressions — Cast](#expressions--cast)
  - [Expressions — Control](#expressions--control)
  - [Predicates](#predicates)
- [Паттерны кодогенерации](#паттерны-кодогенерации)
  - [Одна переменная — один шаг](#одна-переменная--один-шаг)
  - [Dispatch по accept-типу](#dispatch-по-accept-типу)
  - [pre + post для блоков](#pre--post-для-блоков)
  - [Predicate ops и AND-цепочка](#predicate-ops-и-and-цепочка)
- [Вспомогательные функции](#вспомогательные-функции)
- [Наследование через extend()](#наследование-через-extend)
- [Checklist](#checklist)

---

## Концепция

Конвертер — это набор функций-хендлеров, каждый из которых принимает один AST-узел и
`ConverterContext` и возвращает строку (или список строк) кода целевого языка.
`BaseConverter` обходит AST автоматически и склеивает результаты в итоговый файл.

```
Module AST
    └── BaseConverter.convert(module)   ← точка входа
            └── _emit_node(node, ctx)   ← рекурсивный обход
                    ├── pre_callback(node, ctx)   → str | list[str]
                    ├── body traversal  (авто)
                    └── post_callback(node, ctx)  → str | list[str]
```

Конвертер **не хранит состояния** — всё, что нужно знать при обходе, передаётся
через `ConverterContext` и сам узел AST.

---

## ConverterContext

```python
@dataclass
class ConverterContext:
    index: int = 0          # шаг внутри пайплайна (номер переменной)
    depth: int = 0          # уровень вложенности (отступ)
    var_name: str = "v"     # базовое имя переменной
    indent_char: str = "    "
```

| свойство | описание | пример при `index=2, depth=2` |
|----------|----------|-------------------------------|
| `ctx.prv` | входная переменная шага | `v2` |
| `ctx.nxt` | выходная переменная шага | `v3` |
| `ctx.indent` | строка отступа | `"        "` (8 пробелов) |

Каждый expression-шаг читает из `ctx.prv` и пишет в `ctx.nxt`.
`BaseConverter` автоматически вызывает `ctx.advance()` после каждого шага пайплайна.

---

## Система регистрации хендлеров

```python
from ssc_codegen.kdl.converters.base import BaseConverter, ConverterContext

MY_CONVERTER = BaseConverter()

# Основной хендлер (вызывается ДО обхода body)
@MY_CONVERTER(NodeType)
def _(node: NodeType, ctx: ConverterContext) -> str | list[str]:
    ...

# Дополнительный хендлер (вызывается ПОСЛЕ обхода body)
@MY_CONVERTER.post(NodeType)
def _(node: NodeType, ctx: ConverterContext) -> str | list[str]:
    ...

# pre + inline post за один декоратор
@MY_CONVERTER(NodeType, post_callback=lambda _, ctx: ctx.indent + "}")
def _(node: NodeType, ctx: ConverterContext) -> str | list[str]:
    ...
```

Хендлер обязан вернуть `str`, `list[str]` или `None` (пропускается).
Регистрировать хендлер для узла **не обязательно** — необработанные узлы молча пропускаются.

---

## Режимы обхода AST

`BaseConverter._emit_node` обходит `node.body` в одном из трёх режимов
в зависимости от типа узла:

| тип узла | режим | изменение контекста |
|----------|-------|---------------------|
| `JsonDef`, `TypeDef`, `Struct`, `Init` | **container** | `depth+1`, `index=0` |
| `Field`, `TableField`, `InitField`, `PreValidate`, `SplitDoc`, `Key`, `Value`, `TableConfig`, `TableMatchKey`, `TableRow` | **pipeline** | `depth+1` через `_emit_pipeline()`, `index` растёт с каждым шагом |
| `Filter`, `Assert`, `Match`, `LogicNot`, `LogicAnd`, `LogicOr` | **predicate** | `depth+1`, `index=0`, advance после каждого дочернего узла |

**Pipeline** — особый случай: `FallbackStart`/`FallbackEnd` создают `try/except`-блок
с `depth+1` для тела, индексы переменных при этом сквозные.

Хендлеры для pipeline-узлов (`Field`, `InitField` и т.д.) получают в `ctx` контекст
**до** `depth+1` — сам `_emit_pipeline` вызывается внутри `BaseConverter` автоматически.
Хендлер должен только сгенерировать заголовок метода/функции.

---

## Структура нового конвертера

Рекомендуемая структура файла:

```python
# my_converter.py

from ssc_codegen.kdl.converters.base import BaseConverter, ConverterContext
from ssc_codegen.kdl.converters.helpers import to_pascal_case, to_snake_case, ...
from ssc_codegen.kdl.ast import *   # нужные узлы

MY_CONVERTER = BaseConverter()

# ── 1. Маппинг типов ──────────────────────────────────────────────────────────
MY_TYPES = { VariableType.STRING: "string", ... }

# ── 2. Module level ───────────────────────────────────────────────────────────
@MY_CONVERTER(Docstring)
...

@MY_CONVERTER(Imports)
...

@MY_CONVERTER(Utilities)
...

@MY_CONVERTER(JsonDef)
...

@MY_CONVERTER(TypeDef)
...

# ── 3. Struct level ───────────────────────────────────────────────────────────
@MY_CONVERTER(Struct)
...

@MY_CONVERTER(Init)
...

@MY_CONVERTER(StartParse)
...

@MY_CONVERTER.post(StartParse)
...

# ── 4. Expressions ────────────────────────────────────────────────────────────
# selectors, extract, string, regex, array, cast, control ...

# ── 5. Predicates ─────────────────────────────────────────────────────────────
# filter, assert, match, pred ops ...
```

---

## Полный список узлов для реализации

Ниже — все узлы, которые требуют хендлера. Узлы помечены:
- ✅ — обязательно
- ⚠️ — нужен хотя бы `NotImplementedError`, если backend не поддерживает
- 💡 — опционально / только при поддержке фичи

### Module level

| узел | обязательность | что генерировать |
|------|---------------|-----------------|
| `Docstring` | ✅ | комментарий или строковой литерал уровня модуля |
| `Imports` | ✅ | все импорты/require/using для целевого языка |
| `Imports` (post) | 💡 | дополнительные зависимости (библиотека парсера и т.д.) |
| `Utilities` | ✅ | вспомогательные функции (`repl_map`, `normalize_text`, backport'ы и т.д.) |
| `JsonDef` | ✅ | определение типа для JSON-структуры |
| `JsonDefField` | ✅ | поле внутри JSON-типа |
| `TypeDef` | ✅ | определение типа возврата struct |
| `TypeDefField` | ✅ | поле внутри TypeDef |

### Struct level

| узел | обязательность | что генерировать |
|------|---------------|-----------------|
| `Struct` | ✅ | объявление класса / структуры |
| `StructDocstring` | 💡 | docstring внутри класса |
| `StartParse` (pre) | ✅ | сигнатура публичного метода `parse` |
| `StartParse` (post) | ✅ | тело `parse`: обход по полям в зависимости от `StructType` |
| `Init` | ✅ | конструктор/init-метод; принимает документ, парсит его, инициализирует `self._doc` |
| `InitField` | ✅ | заголовок приватного метода для pre-computed поля |
| `Field` | ✅ | заголовок приватного метода `_parse_{name}` |
| `TableField` | ✅ | аналог `Field`, возврат — `type | sentinel` |
| `PreValidate` | ✅ | метод `_pre_validate`, возврат `void/None` |
| `SplitDoc` | ✅ | метод `_split_doc`, возвращает коллекцию элементов |
| `Key` | ✅ | метод `_parse_key`, возврат `string` |
| `Value` | ✅ | метод `_parse_value` |
| `TableConfig` | ✅ | метод `_table_config`, возврат одного элемента |
| `TableMatchKey` | ✅ | метод `_table_match_key`, возврат `string` |
| `TableRow` | ✅ | метод `_table_row`, возврат одного элемента |

**Логика `StartParse.post` по `StructType`:**

| `StructType` | тело `parse()` |
|---|---|
| `ITEM` | `return { field: _parse_field(doc), ... }` |
| `LIST` | `return [ { field: _parse_field(i), ... } for i in _split_doc(doc) ]` |
| `DICT` | `return { _parse_key(i): _parse_value(i) for i in _split_doc(doc) }` |
| `FLAT` | накопить список строк через `_parse_{field}`, дедуплицировать, вернуть |
| `TABLE` | итерировать `_table_rows(doc)`, для каждой строки вызвать `_parse_{field}`, проверить sentinel, собрать dict |

### Expressions — Selectors

| узел | что генерировать | если не поддерживается |
|------|-----------------|------------------------|
| `CssSelect` | выбрать один элемент по CSS | — |
| `CssSelectAll` | выбрать все элементы по CSS | — |
| `CssRemove` | удалить элементы по CSS из дерева (side-effect), переназначить переменную | — |
| `XpathSelect` | выбрать один элемент по XPath | ⚠️ `NotImplementedError` |
| `XpathSelectAll` | выбрать все элементы по XPath | ⚠️ `NotImplementedError` |
| `XpathRemove` | удалить элементы по XPath | ⚠️ `NotImplementedError` |

`CssRemove` — **side-effect**: модифицирует дерево на месте, затем переназначает ту же переменную:
```
# псевдокод
remove_all(prv, query)
nxt = prv
```

### Expressions — Extract

| узел | DOCUMENT | LIST_DOCUMENT |
|------|----------|---------------|
| `Text` | извлечь текстовое содержимое элемента | map по списку |
| `Raw` | извлечь raw HTML/XML тег как строку | map по списку |
| `Attr` | извлечь значение атрибута(ов) | map по списку |

`Attr.keys` — кортеж: если один ключ — вернуть значение напрямую; если несколько —
пропускать отсутствующие ключи, всегда возвращать `LIST_STRING`.

### Expressions — String

Все узлы работают как map: `STRING → STRING`, `LIST_STRING → LIST_STRING`.
Исключения: `Split` (`STRING → LIST_STRING`), `Join` (`LIST_STRING → STRING`).

| узел | операция |
|------|----------|
| `Trim` | убрать пробелы / символ `substr` с обоих концов |
| `Ltrim` | убрать с левого конца |
| `Rtrim` | убрать с правого конца |
| `NormalizeSpace` | схлопнуть все пробельные символы в один пробел |
| `RmPrefix` | убрать префикс `substr` (если есть) |
| `RmSuffix` | убрать суффикс `substr` (если есть) |
| `RmPrefixSuffix` | убрать и префикс, и суффикс |
| `Fmt` | подставить строку в шаблон (`node.template`, placeholder `{}`) |
| `Repl` | заменить `node.old` на `node.new` |
| `ReplMap` | последовательная замена по словарю `node.replacements` |
| `Lower` | привести к нижнему регистру |
| `Upper` | привести к верхнему регистру |
| `Split` | разбить по разделителю `node.sep` |
| `Join` | объединить список через `node.sep` |
| `Unescape` | HTML/unicode/hex/bytes escapes → unicode |

### Expressions — Regex

| узел | accept | ret | операция |
|------|--------|-----|----------|
| `Re` | `STRING \| LIST_STRING` | same | извлечь первую capturing group |
| `ReAll` | `STRING` | `LIST_STRING` | найти все совпадения |
| `ReSub` | `STRING \| LIST_STRING` | same | заменить по шаблону |

Флаги: `node.ignore_case`, `node.dotall` — используйте соответствующие флаги целевого языка.

### Expressions — Array

| узел | операция |
|------|----------|
| `Index` | взять элемент по индексу `node.i` |
| `Slice` | срез `[node.start : node.end]` |
| `Len` | длина коллекции |
| `Unique` | дедупликация; `node.keep_order` — с сохранением порядка или нет |

### Expressions — Cast

| узел | операция |
|------|----------|
| `ToInt` | `STRING → INT`, `LIST_STRING → LIST_INT` |
| `ToFloat` | `STRING → FLOAT`, `LIST_STRING → LIST_FLOAT` |
| `ToBool` | любой тип → булево |
| `Jsonify` | `STRING → JSON`; `node.path` — опциональный dot-path для вложенного доступа |
| `Nested` | `DOCUMENT → NESTED`; `node.struct_name` — имя вложенного класса; вызов `.parse()` |

`Jsonify.path` разбирается через `jsonify_path_to_segments()` из `helpers.py`.

### Expressions — Control

| узел | операция |
|------|----------|
| `Self` | читает pre-computed значение `InitField` по имени (`self._name` / поле инстанса) |
| `Return` | внутри `PreValidate` — пустой return; иначе — `return prv` |
| `FallbackStart` | открывает try/catch блок |
| `FallbackEnd` | закрывает catch; `node.value` — возвращаемый fallback-литерал |

### Predicates

**Containers:**

| узел | что генерировать |
|------|-----------------|
| `Filter` | list comprehension / filter по условию из body |
| `Assert` | assert/throw по условию из body, затем переназначить переменную |
| `Match` | вычислить ключ строки (`_table_match_key`), проверить условие из body, при несовпадении вернуть sentinel |

**Ops** (используются внутри containers, переменная — `i`):

Все predicate ops следуют единому паттерну:
- `ctx.index == 0` → первый предикат в блоке, без логического соединителя
- `ctx.index > 0` → добавить `AND` (или `&&`, `and` и т.д. для целевого языка)

| группа | узлы | переменная | операция |
|--------|------|-----------|----------|
| CSS | `PredCss` | `i` (элемент) | элемент имеет child по CSS-query |
| XPath | `PredXpath` | `i` (элемент) | элемент имеет child по XPath ⚠️ |
| Атрибут | `PredHasAttr` | `i` | элемент имеет атрибут |
| Атрибут | `PredAttrEq/Ne/Starts/Ends/Contains/Re` | значение атрибута | сравнение значения атрибута |
| Текст | `PredTextStarts/Ends/Contains/Re` | `i.text` | сравнение текста элемента |
| Строки | `PredEq`, `PredNe` | `i` (строка) | равенство; если аргумент `int` — сравнение длины |
| Строки | `PredStarts`, `PredEnds`, `PredContains`, `PredIn` | `i` | строковые предикаты |
| Числа | `PredGt/Lt/Ge/Le` | `len(i)` | сравнение длины |
| Диапазон | `PredRange` | `len(i)` | `start < len < end` |
| Длина | `PredCountEq/Gt/Lt` | `len(i)` | только для `Assert` |
| Regex | `PredRe` | `i` | совпадение с паттерном |
| Regex | `PredReAll`, `PredReAny` | `i` (список) | все/хотя бы один совпадают |
| Логика | `LogicAnd`, `LogicOr`, `LogicNot` | — | группировка предикатов |

Для `values: tuple[str, ...]` с несколькими значениями применяется OR-семантика (`any()`),
кроме `PredNe` — там AND (`all()`).

---

## Паттерны кодогенерации

### Одна переменная — один шаг

Каждый expression-шаг читает `ctx.prv` и пишет `ctx.nxt`:

```python
@MY_CONVERTER(SomeNode)
def _(node, ctx):
    return f"{ctx.indent}{ctx.nxt} = transform({ctx.prv})"
```

`BaseConverter` автоматически вызывает `ctx.advance()` после каждого шага.

### Dispatch по accept-типу

Многие узлы работают по-разному для `DOCUMENT` vs `LIST_DOCUMENT` (или `STRING` vs `LIST_STRING`):

```python
@MY_CONVERTER(Text)
def _(node, ctx):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = get_text({ctx.prv})"
    # LIST_DOCUMENT
    return f"{ctx.indent}{ctx.nxt} = [get_text(i) for i in {ctx.prv}]"
```

### pre + post для блоков

Для узлов, которые оборачивают body (предикатные контейнеры, `Fallback`), нужен pre для открытия и post для закрытия:

```python
@MY_CONVERTER(Filter, post_callback=lambda _, ctx: ctx.deeper().indent + "]")
def _(node, ctx):
    # открываем list comprehension
    return f"{ctx.indent}{ctx.nxt} = [i for i in {ctx.prv} if "

# body (предикаты) эмитируется автоматически между pre и post
```

### Predicate ops и AND-цепочка

```python
@MY_CONVERTER(PredStarts)
def _(node, ctx):
    values = node.values
    cond = f"i.startswith({values[0]!r})" if len(values) == 1 \
        else f"any(i.startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"   # целевой язык: and / && / ...
```

---

## Вспомогательные функции

Все утилиты — в `ssc_codegen/kdl/converters/helpers.py`:

| функция | описание |
|---------|----------|
| `to_snake_case(s)` | `"myField"` / `"my-field"` → `"my_field"` |
| `to_pascal_case(s)` | `"my-field"` → `"MyField"` |
| `to_camel_case(s)` | `"MyField"` → `"myField"` |
| `to_upper_snake_case(s)` | `"myField"` → `"MY_FIELD"` |
| `jsonify_path_to_segments(path)` | `"foo.0.bar"` → `["'foo'", "0", "'bar'"]` |
| `py_pattern_re_flags(node)` | строит суффикс флагов regex для Python (переопределите для другого языка) |

Для нового backend может понадобиться своя `{lang}_pattern_re_flags(node)`.

---

## Наследование через extend()

Если новый конвертер близок к уже существующему (например, другая CSS-библиотека
для того же языка), используйте `extend()`:

```python
# базовый Python-конвертер с общими хендлерами
PY_BASE = BaseConverter()

@PY_BASE(Trim)
def _(node, ctx): ...   # общий для всех Python-бекендов

# bs4-специфичный конвертер — наследует всё, переопределяет только нужное
PY_BS4 = PY_BASE.extend()

@PY_BS4(CssSelect)
def _(node, ctx):
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select_one({node.query!r})"

# selectolax — отдельный extend от базы, не от bs4
PY_SELECTOLAX = PY_BASE.extend()

@PY_SELECTOLAX(CssSelect)
def _(node, ctx):
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css_first({node.query!r})"
```

Родительский конвертер никогда не затрагивается регистрациями дочернего.

---

## Checklist

При реализации нового конвертера убедитесь, что покрыты все пункты:

**Module level**
- [ ] `Docstring` — модульная документация
- [ ] `Imports` (pre + post) — все нужные импорты/зависимости
- [ ] `Utilities` — вспомогательные функции (`repl_map`, `normalize_text`, `unescape_text`, backport'ы и т.д.)
- [ ] `JsonDef` + `JsonDefField` — типы для JSON
- [ ] `TypeDef` + `TypeDefField` — типы возврата struct; учесть `NESTED` и `JSON` ref с `is_array`

**Struct level**
- [ ] `Struct` — объявление класса
- [ ] `StructDocstring` — опциональная документация
- [ ] `Init` — конструктор; принять `str | Document`, разобрать строку при необходимости, инициализировать `InitField`-поля
- [ ] `InitField` — заголовок метода; тело эмитируется автоматически
- [ ] `StartParse` (pre + post) — все пять `StructType`: ITEM, LIST, DICT, FLAT, TABLE
- [ ] `Field`, `TableField`, `PreValidate`, `SplitDoc`, `Key`, `Value`, `TableConfig`, `TableMatchKey`, `TableRow`

**Expressions**
- [ ] Selectors: `CssSelect`, `CssSelectAll`, `CssRemove`; XPath — `NotImplementedError` если не поддерживается
- [ ] Extract: `Text`, `Raw`, `Attr` (dispatch по DOCUMENT / LIST_DOCUMENT)
- [ ] String: все 14 узлов (map-семантика; `Split` и `Join` — исключения)
- [ ] Regex: `Re`, `ReAll`, `ReSub` с флагами `ignore_case`/`dotall`
- [ ] Array: `Index`, `Slice`, `Len`, `Unique` (с `keep_order`)
- [ ] Cast: `ToInt`, `ToFloat`, `ToBool`, `Jsonify` (с `path`), `Nested`
- [ ] Control: `Self`, `Return`, `FallbackStart`, `FallbackEnd`

**Predicates**
- [ ] Containers: `Filter`, `Assert`, `Match` (sentinel для table)
- [ ] Logic: `LogicAnd`, `LogicOr`, `LogicNot`
- [ ] Pred ops: все узлы из таблицы выше; не забыть AND-цепочку через `ctx.index`
- [ ] Атрибутные предикаты: нормализовать multi-valued атрибуты (аналог `get_attribute_list`)

**Общее**
- [ ] `PY_TYPES` / аналог для целевого языка — покрыть все `VariableType`
- [ ] `TransformCall` — если backend поддерживает transform-хендлеры
- [ ] Проверить, что XPath-узлы выбрасывают `NotImplementedError` (или реализованы)
- [ ] Добавить sentinel-объект `UNMATCHED_TABLE_ROW` (или аналог) для table struct
