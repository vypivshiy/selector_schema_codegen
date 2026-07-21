# kdlquery — CSS3-селекторы для KDL AST

**Аудитория:** мейнтейнеры
**Последнее обновление:** 2026-07-21

`kdlquery` — внешний парсер KDL 2.0, который предоставляет CSS3-подобные
селекторы поверх AST. В `ssc_codegen` используется как основа для
линтера (`core/linter.py`) и для извлечения узлов из CST.

Домашний репозиторий: `D:\PycharmProjects\kdlquery` (README + `llm.txt` —
полная справка). Здесь — выжимка самых полезных паттернов для написания
правил линтера.

## Что даёт kdlquery

- **`parse(src) -> KdlDocument`** — lossless CST-парсер KDL 2.0 с полной
  информацией о позициях (`Span`, `Position`).
- **`KdlDocument` / `KdlNode`** — мутабельное дерево с parent-ссылками,
  навигацией (`parent`, `root`, `depth()`, `siblings()`, `parents()`,
  `closest()`, `matches()`).
- **CSS3-like селекторы** — `select()`, `select_one()` на `KdlDocument`
  (всё дерево) и `KdlNode` (поддерево детей).
- **Reader API** — `Reader[T,R]` + `Walker` для трансформации CST в
  произвольные Python-объекты. В ssc_codegen не используется напрямую —
  свой walker в `core/reader.py`.

## Базовый API

```python
from kdlquery import parse, KdlDocument, KdlNode

doc = parse(src)

# Доступ к top-level узлам
for node in doc.nodes: ...

# Навигация
node.parent               # родитель (None у корня)
node.root                 # корень дерева
node.document             # владеющий KdlDocument
node.depth()              # глубина в дереве (корень = 0)
node.index()              # индекс среди siblings
node.siblings()           # tuple siblings (включая себя)
node.parents()            # список предков bottom-up
list(node.iter_descendants())

# Проверка матчей
node.matches("server[tls=#true]")    # bool
node.closest("struct")               # ближайший предшествующий предок (или None)
```

## Селекторы — паттерны для линтера

Селекторы — самый компактный способ собрать узлы под правило. `KdlDocument.select()`
ищет по всему дереву, `KdlNode.select()` — по поддереву детей.

### Top-level узлы по имени

`:root` ограничивает матч только корневыми узлами документа —
в `core/linter.py` используется для прохода по top-level объявлениям:

```python
# все top-level struct'ы
for node in doc.select("struct:root"): ...

# все top-level define
for node in doc.select("define:root"): ...

# все top-level json
for node in doc.select("json:root"): ...
```

### Negative match через `:not(...)`

Поймать неизвестные top-level узлы (всё, что не в белом списке):

```python
# прямо из core/linter.py:189
for node in doc.select(":root:not(@doc, json, struct, define, import)"):
    error(node, f"Unknown node: {node.name}", code="E200")
```

### `:has(...)` — наличие потомка

Найти всех top-level struct'ов, у которых есть поле `nested`:

```python
# прямо из core/linter.py:415
for caller in doc.select("struct:root:has(nested)"):
    for nested_op in caller.select("nested"):
        ...
```

`has(> complex)` — только прямые дети:

```python
doc.select("plugin:has(> backend)")     # plugin с прямым ребёнком backend
```

### scoped select на `KdlNode`

`node.select(...)` ищет только среди потомков — удобно для проверки тела
struct'а или блока:

```python
# есть ли в теле @request?
if node.select_one("@request") is None: ...

# все @error внутри struct'а
for err in node.select("@error"): ...

# все операции nested
for n in caller.select("nested"): ...
```

### `select_one` — первый матч или None

Идиоматичная проверка наличия:

```python
# прямо из core/linter.py:480
missing = [r for r in REQUIRED_RESERVED[struct_type]
           if node.select_one(r) is None]

# assert содержит to-bool?
if node.select_one("to-bool") is None:
    error(node, "@check must contain to-bool", code="E002")
```

## Селектор reference (краткая шпаргалка)

```
# Узлы
name                    # по имени
*                       # любой
(type)                  # по type-аннотации
(type)name              # тип + имя

# Свойства
[key]                   # свойство присутствует
[key=val]               # равно
[key^=val]              # начинается с
[key$=val]              # заканчивается на
[key~=val]              # содержит
[(type)key]             # свойство с типизированным значением
[(type)key=val]         # типизированное + значение

# Аргументы (по позиции)
[N]                     # аргумент на позиции N существует
[N=val] [N^=val] [N$=val] [N~=val]
[(type)N]               # типизированный аргумент
[*=val]                 # любой аргумент равен val

# Комбинаторы
A B                     # потомок
A > B                   # прямой ребёнок
A + B                   # соседний sibling
A ~ B                   # любой следующий sibling
A, B                    # union (с дедупом по node identity)

# Псевдо-классы
:root                   # только top-level узлы документа
:first-child            # первый среди siblings
:last-child
:nth-child(n)           # :nth-child(2n), :nth-child(2n+1)
:only-child
:empty                  # без детей
:not(compound)          # отрицание
:has(complex)           # имеет потомка
:has(> complex)         # имеет прямого ребёнка
```

> **Важно:** реализация расходится с официальным
> [KDL Query draft](https://github.com/kdl-org/kdl/blob/main/QUERY-SPEC.md)
> и следует CSS3-синтаксису. `:root` матчит только top-level узлы
> `KdlDocument` — на `KdlNode.select()` `:root` НЕ работает (в поддереве
> нет root-концепции).

## Внутренние типы, часто используемые в ssc_codegen

```python
from kdlquery import (
    parse,                    # parse(src) -> KdlDocument
    KDL2CSTParser,            # низкоуровневый CST-парсер
    KdlDocument,
    KdlNode,
    KdlValue,
    KDLParseError,            # синтаксическая ошибка KDL
    ReadDiagnostic,           # диагностика из Reader API
    Severity,                 # ERROR / WARNING / INFO
)
from kdlquery.types import Span, Position   # позиция в исходнике
from kdlquery.reader import Reader, Walker, WalkContext, parse_into
from kdlquery.dict_reader import DictReader
```

В `ssc_codegen/core/` используются:
- `parse(src)` — первичный парсинг в `core/reader.py:30`.
- `KdlNode` — передаётся во все handler'ы в `core/linter.py`, `expressions.py`,
  `predicates.py`, `struct_parser.py`, `module_handler.py`.
- `ReadDiagnostic` + `Severity` — все диагностики (обёртка над ошибками линтера).
- `Span` / `Position` — attach к AST через `ast.base.Node`.

## Когда использовать селекторы vs прямой обход

| Случай | Инструмент |
|---|---|
| Найти top-level узлы определённого типа | `doc.select("name:root")` |
| Проверить наличие поля в struct | `node.select_one("name")` |
| Собрать всех детей по условию | `node.select("[key=val]")` |
| Iter по children в порядке исходника | `for c in node.children: ...` |
| Type-annotation match | `node.select("(rest)")` |
| Сложный структурный шаблон | `:has(...)`, `:not(...)` |

Селекторы компактнее ручного цикла, но для горячих путей (циклы по
тысячам узлов) прямой `for c in node.children` быстрее — у selector engine
есть overhead на парсинг паттерна (LRU-кэширован, но всё же).

## Дополнительные материалы

- `kdlquery/README.md` — полный reference с примерами.
- `kdlquery/llm.txt` — компактная справка для LLM-контекста.
- `kdlquery/tests/test_selector.py` — кейсы-matchers для каждого pseudo-class.
