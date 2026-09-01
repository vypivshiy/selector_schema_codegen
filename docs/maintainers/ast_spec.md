# Спецификация AST-узлов и руководство по кодогенерации

**Назначение:** Полный справочник по промежуточному представлению (AST `ssc_codegen.ast`), контракту обхода (`traversal/`) и правилам генерации кода для всех поддерживаемых и новых target-бэкендов (Python, JavaScript, Go и др.).  
**Версия DSL:** 2.1  
**Связанные документы:** [converters.md](converters.md), [types.md](../types.md), [operations.md](../operations.md), [predicates.md](../predicates.md), [CONTEXT.md](../../CONTEXT.md)

---

## Содержание

1. [Архитектура кодогенератора](#1-архитектура-кодогенератора)
   - [BaseWalker и три режима обхода](#basewalker-и-три-режима-обхода)
   - [WalkContext и модель переменных](#walkcontext-и-модель-переменных)
   - [ModuleBuilder (накопитель импортов и хелперов)](#modulebuilder)
   - [Соглашения по Helper-коду (sscruntime) и префиксам ssc/Ssc](#соглашения-по-helper-коду-sscruntime-и-префиксам-sscssc)
   - [Двухпроходная генерация (Two-pass codegen)](#двухпроходная-генерация-two-pass-codegen)
2. [Checklist: Создание нового Backend с нуля](#2-checklist-создание-нового-backend-с-нуля)
3. [Глубокий разбор сложных подсистем](#3-глубокий-разбор-сложных-подсистем)
   - [1. Fallback (try/catch и синхронизация переменных)](#1-fallback-trycatch-и-синхронизация-переменных)
   - [2. ExtensionCall (пользовательские операции)](#2-extensioncall-пользовательские-операции)
   - [3. Таблицы (TableConfig, TableRows, Match, UNMATCHED_TABLE_ROW)](#3-таблицы-tableconfig-tablerows-match-unmatched_table_row)
   - [4. REST и транспортная модель (@request, Result-артефакты)](#4-rest-и-транспортная-модель-request-result-артефакты)
   - [5. Nested и Jsonify (вложенные структуры и JSON)](#5-nested-и-jsonify-вложенные-структуры-и-json)
4. [Каталог AST-узлов](#4-каталог-ast-узлов)
   - [Группа 1: Модульный уровень](#группа-1-модульный-уровень)
   - [Группа 2: Определения типов и схем](#группа-2-определения-типов-и-схем)
   - [Группа 3: Структуры и методы](#группа-3-структуры-и-методы)
   - [Группа 4: Табличные узлы](#группа-4-табличные-узлы)
   - [Группа 5: HTTP и REST артефакты](#группа-5-http-и-rest-артефакты)
   - [Группа 6: Пользовательские расширения](#группа-6-пользовательские-расширения)
   - [Группа 7: Селекторы DOM](#группа-7-селекторы-dom)
   - [Группа 8: Извлечение данных](#группа-8-извлечение-данных)
   - [Группа 9: Строковые трансформации](#группа-9-строковые-трансформации)
   - [Группа 10: Регулярные выражения](#группа-10-регулярные-выражения)
   - [Группа 11: Массивы и срезы](#группа-11-массивы-и-срезы)
   - [Группа 12: Приведение типов](#группа-12-приведение-типов)
   - [Группа 13: Управление потоком](#группа-13-управление-потоком)
   - [Группа 14: Предикаты и логические условия](#группа-14-предикаты-и-логические-условия)

---

## 1. Архитектура кодогенератора

Пайплайн компиляции KDL-схемы в исполняемый код:

```
KDL schema -> kdlquery -> core/reader -> Module AST -> BaseWalker (Visitor) -> Target Code
```

Генератор не занимается синтаксическим анализом KDL или проверкой типов — он получает полностью валидированное дерево `Module` AST, где каждый узел снабжен информацией о типах (`TypeInfo`).

---

### BaseWalker и три режима обхода

Базовый класс обхода `BaseWalker` (`ssc_codegen/traversal/walker.py`) содержит таблицу диспетчеризации `_DISPATCH: dict[type[Node], str]`, которая сопоставляет класс узла AST с именем метода-обработчика `visit_*`.

Каждый обработчик возвращает:
- `list[str]` — готовые строки сгенерированного кода;
- `str` — одиночную строку (автоматически упаковывается в `[str]`);
- `None` — узел не генерирует строковый вывод (например, технические маркеры или декларации, обрабатываемые на другом этапе).

Обход дочерних узлов `node.body` выполняется методом `walk_children(node, ctx)` в одном из **трех режимов**:

| Режим | Классы узлов | Поведение контекста | Назначение |
|---|---|---|---|
| **Container** | `Module`, `StructBase`, `JsonDef`, `TypeDef`, `Init` | `depth + 1`, `index = 0`. Дочерние узлы выполняются на одном уровне, индекс не сдвигается между соседями. | Определение классов, модулей, структур, JSON-схем. |
| **Pipeline** | `Field`, `InitField`, `PreValidate`, `CheckMethod`, `SplitDoc`, `Key`, `Value`, `Table*`, `FunctionDef` | `depth + 1`. Делегируется в `walk_pipeline(body, ctx)`. Индекс `ctx.index` автоматически инкрементируется (`ctx.advance()`) после каждой операции. | Последовательная трансформация данных (`v -> v1 -> v2`). |
| **Predicate** | `Filter`, `Assert`, `Match`, `LogicAnd`, `LogicOr`, `LogicNot` | `depth + 1`, `index = 0`. Индекс инкрементируется между условиями. | Формирование составных логических выражений (`cond1 and cond2`). |

---

### WalkContext и модель переменных

`WalkContext` (`ssc_codegen/traversal/context.py`) — неизменяемый (`@dataclass(frozen=...)`) объект состояния обхода:

| Поле / Свойство | Тип | Описание |
|---|---|---|
| `index` | `int` | Текущий номер промежуточной переменной (0, 1, 2...). |
| `depth` | `int` | Уровень вложенности отступа. |
| `var_name` | `str` | Базовое имя переменной (по умолчанию `"v"`). |
| `indent_char` | `str` | Строка отступа (`"    "` для Python, `"  "` для JS, `"\t"` для Go). |
| `meta` | `dict` | Контекстные опции сборки (`http_client`, `package`, `runtime_module` и др.). |
| `ctx.prv` | `str` (prop) | Имя входной переменной: `"v"` при `index == 0`, иначе `f"v{index}"` (`"v1"`, `"v2"`). |
| `ctx.nxt` | `str` (prop) | Имя выходной переменной: `f"v{index + 1}"` (`"v1"`, `"v2"`, `"v3"`). |
| `ctx.indent` | `str` (prop) | Строка текущего отступа (`indent_char * depth`). |
| `ctx.advance()` | Метод | Возвращает новый контекст с `index + 1`. |
| `ctx.advance_n(n)`| Метод | Возвращает новый контекст с `index + n`. |
| `ctx.deeper()` | Метод | Возвращает новый контекст с `depth + 1`. |
| `ctx.reset_index()`| Метод | Возвращает новый контекст с `index = 0`. |

#### Модель передачи данных в Pipeline

Внутри pipeline-узла каждая операция трансформирует `ctx.prv` в `ctx.nxt`:
```
Операция 1 (index=0):   v1 = transform(v)        -> ctx.advance()
Операция 2 (index=1):   v2 = transform(v1)       -> ctx.advance()
Операция 3 (index=2):   v3 = transform(v2)       -> ctx.advance()
Завершение:             return v3
```

---

### ModuleBuilder

`ModuleBuilder` (`ssc_codegen/generation/builder.py`) — централизованный накопитель импортов и вспомогательных функций (std-helpers). Исключает дублирование кода и побочные эффекты.

Методы регистрации (все идиомпотентны):
- `require_import(line: str)` — регистрирует строку импорта;
- `require_std(name: str, *, code: str, imports: list[str] | None = None)` — регистрирует стандартную служебную функцию компилятора;
- `require_runtime(name: str, *, code: str, imports: list[str] | None = None)` — регистрирует пользовательскую функцию из `extension`;
- `reset()` — очищает состояние перед следующим модулем.

---

### Соглашения по Helper-коду (sscruntime) и префиксам ssc/Ssc

При генерации парсеров и REST-клиентов часто требуется вспомогательный код: исключения, валидаторы, декодеры, сопоставители ошибок и диспетчеры HTTP.

#### 1. Обязательный префикс именования
Все вспомогательные классы, исключения и функции runtime **обязаны** использовать префикс `ssc<name>` / `Ssc<Name>` / `ssc_<name>` (или `std_<name>` / `std<Name>` для стандартных встроенных функций):
- **Исключения:** `SscAssertionError`, `SscRegexError`, `SscTransportError`
- **Маркеры:** `UnmatchedTableRow` / `UNMATCHED_TABLE_ROW` / `SscUnmatchedTableRow`
- **Функции общего назначения:**
  - **Python:** `std_assert`, `std_re_search`, `std_repl_map`, `std_normalize_text`, `std_unescape_text`, `std_rm_prefix`, `std_rm_suffix`, `ssc_remap_json_keys`, `ssc_dispatch_err`, `ssc_rest_call`, `ssc_rest_call_async`
  - **JavaScript:** `sscAssert`, `sscReSearch`, `sscReplMap`, `sscNormalizeText`, `sscUnescapeText`, `sscRmPrefix`, `sscRmSuffix`, `sscRemapJsonKeys`, `sscRestCall`, `sscRestCallAxios`
  - **Go:** `stdAssert`, `stdReSearch`, `stdReplMap`, `stdNormalizeText`, `stdUnescapeText`, `stdRmPrefix`, `stdRmSuffix`, `stdUnique`, `stdFallback`, `stdRemapJSONKeys`, `stdDispatchErr`, `stdRestCall`

#### 2. Зачем нужен префикс
- **Изоляция от пользовательской схемы:** Пользователь может назвать поле `assert`, `url`, `type`, `fetch`, `normalize`, `key` и т.д. Префикс `ssc` / `std_` исключает коллизии имен в сгенерированном классе или модуле.
- **Изоляция от глобального скоупа языка:** Предотвращает конфликты со встроенными функциями целевого языка и внешними библиотеками.
- **Прозрачность аудита:** Сразу видно, какая строчка кода сгенерирована по правилам схемы, а какая относится к инфраструктурному runtime-слою.

#### 3. Когда выносить логику в Helper
- **Повторяющаяся нетривиальная логика:** Если операция требует более 2-3 строк кода и может встречаться в нескольких полях (например, декодирование HTML-сущностей `std_unescape_text`, словарная замена `std_repl_map`, поиск по регулярному выражению с проверкой совпадения `std_re_search`).
- **Специализированные исключения:** Выбрасывание типизированного `SscAssertionError` при сбое `assert { ... }` или `SscRegexError` при отсутствии совпадения `re "..."`.
- **Ремаппинг JSON:** Преобразование алиасов ключей `json` схем (`ssc_remap_json_keys`).
- **REST-диспетчеризация:** Обработка HTTP-статусов, сопоставление `ErrMatcher` и упаковка в монадические типы `Ok[T]` / `Err[E]`.

#### 4. Режимы размещения: Inlined vs Separate Runtime (`-R`)
- **Без флага `-R` (по умолчанию):** Посещаемые AST-узлы регистрируют требуемые хелперы через `self._builder.require_std(name, code=..., imports=...)`. В сгенерированный файл попадают только те хелперы, которые реально используются в текущей схеме.
- **С флагом `--separate-runtime` / `-R`:** Хелперы собираются в отдельный общий модуль `sscgen_runtime.<ext>` (`generation/runtime.py`). Сгенерированные файлы парсеров не инлайнят код хелперов, а импортируют их:
  - Python: `from sscgen_runtime import std_assert, SscAssertionError, ...`
  - JS: `const { sscAssert, SscAssertionError } = require("./sscgen_runtime");`
  - Go: размещаются в том же пакете (файл `sscgen_runtime.go`), видимы без импорта.

---

### Двухпроходная генерация (Two-pass codegen)

Для предотвращения проблем с порядком объявлений (forward references) и точной сборки заголовка файла генерация выполняется в два прохода:

1. **Pass 1 (Collection Pass):** `_walk_module(node)` обходит AST без вывода в итоговый файл. Обработчики узлов регистрируют необходимые импорты и std-хелперы в `self._builder`.
2. **Pass 2 (Emission Pass):** `_walk_module(node)` генерирует целевой исходный код. Заголовок формируется на основе зафиксированного содержимого `ModuleBuilder` (`builder.imports`, `builder.std_defs`).

---

## 2. Checklist: Создание нового Backend с нуля

При добавлении нового целевого языка (например, `Ruby`, `Rust`, `C#`, `PHP`):

1. **Структура пакета:** Создать директорию `ssc_codegen/targets/<lang>/` с файлами `__init__.py`, `visitor.py`, `runtime.py`.
2. **Наследование от BaseWalker:** В `visitor.py` объявить класс `class LangVisitor(BaseWalker):`.
3. **Таблица сопоставления типов:** Задать классовые атрибуты:
   ```python
   TYPES = {
       VariableType.STRING: "string",
       VariableType.INT: "int",
       VariableType.FLOAT: "float",
       VariableType.BOOL: "bool",
       VariableType.DOCUMENT: "HtmlNode",
   }
   ARRAY_TYPE_FMT = "List[{}]"
   OPTIONAL_TYPE_FMT = "Optional[{}]"
   ```
4. **Конструктор и состояние:** Инициализировать `self._builder = ModuleBuilder()`.
5. **Реализация `visit_module`:** Реализовать двухпроходный сбор (`Pass 1 -> Pass 2`) с генерацией docstring, imports, std-helpers, типов, структур и hook-вставок.
6. **Реализация узлов разметки (DOM):** Реализовать селекторы (`visit_css_select`, `visit_xpath_select`, `visit_text`, `visit_attr`, `visit_raw`) под выбранную библиотеку DOM целевого языка (или вынести в аналог `DomSpelling`).
7. **Реализация скалярных узлов:** Реализовать обработчики строковых (`Trim`, `RmPrefix`, `Fmt`, `Repl`), регулярных (`Re`, `ReAll`, `ReSub`) и массивных (`Index`, `Slice`, `Unique`) операций.
8. **Реализация предикатов:** Реализовать `visit_filter`, `visit_assert`, `visit_match` и все предикаты `visit_predicate_*`.
9. **Реализация сложных подсистем:** Реализовать `visit_fallback`, `visit_extension_call`, `visit_jsondef`, `visit_jsonify`, `visit_nested`, `visit_table_*`.
10. **Регистрация в Resolver:** В `ssc_codegen/targets/resolver.py` добавить функцию `_resolve_<lang>(spec)` и зарегистрировать фабрику создания конвертера.
11. **Тестирование:** Добавить набор интеграционных тестов в `tests/<lang>/`.

---

## 3. Глубокий разбор сложных подсистем

### 1. Fallback (try/catch и синхронизация переменных)

Узел `Fallback` оборачивает предшествующие операции поля в защитный блок.

#### AST-структура
- `Fallback.body`: содержит список узлов `Node`, которые предшествовали `fallback` в DSL.
- `Fallback.value`: значение по умолчанию (`None`, `""`, `0`, `[]` и т.д.).

#### Семантика обхода
1. В `walk_pipeline` появление `Fallback` перехватывается: узел сам управляет обходом своего `body`.
2. Генератор эмитирует `try` (или аналог).
3. Внутри `try` вызывается `self.walk_pipeline(node.body, ctx.deeper())`.
4. В блоке `except / catch` переменной `v_target` присваивается `Fallback.value`.
5. Внешний контекст `ctx` продвигается на `len(node.body)` шагов: `ctx = ctx.advance_n(len(node.body))`.

#### Примеры кодогенерации

**Python:**
```python
try:
    v1 = v.select_one(".price")
    v2 = v1.get_text(strip=True)
    v3 = int(v2)
    return v3
except Exception:
    return 0
```

> **Важно:** `Fallback` перехватывает **все** исключения (`except Exception:` в Python, `catch (e)` в JavaScript, перехват паники/ошибок через `stdFallback` в Go). Это гарантирует, что любая непредвиденная ошибка в цепочке вычислений (элемент не найден, не сработал regex, не сошелся `assert`, ошибка парсинга JSON или приведения типов) безопасно приводит к возврату заданного fallback-значения.

**JavaScript:**
```javascript
try {
  const v1 = v.querySelector(".price");
  const v2 = v1.textContent.trim();
  const v3 = parseInt(v2, 10);
  return v3;
} catch (e) {
  return 0;
}
```

**Go:**
```go
v3 := stdFallback(func() (int, error) {
    v1 := v.Find(".price").First()
    v2 := strings.TrimSpace(v1.Text())
    return strconv.Atoi(v2)
}, 0)
```

---

### 2. ExtensionCall (пользовательские операции)

Узел `ExtensionCall` представляет вызов пользовательской операции `!Namespace.op-name`.

#### Механизм работы
1. Узел содержит `definition: ExtensionDef`.
2. По целевому языку выбирается секция `definition.targets[lang]`.
3. В `ModuleBuilder` регистрируются импорты (`target.imports`) и вспомогательные функции (`target.helpers`).
4. Шаблонная строка `target.emit` рендерится с заменой плейсхолдеров:
   - `{{in}}` -> `ctx.prv`
   - `{{out}}` -> `ctx.nxt`
   - `{{in_type}}` -> строковое представление типа входа
   - `{{out_type}}` -> строковое представление типа выхода

#### Пример
KDL:
```kdl
extension StringUtils {
    slugify {
        sig str str
        py {
            import "import re"
            emit #"{{out}} = re.sub(r'[\s_]+', '-', {{in}}.lower())"#
        }
    }
}
```
Генерируемый Python:
```python
v2 = re.sub(r'[\s_]+', '-', v1.lower())
```

---

### 3. Таблицы (TableConfig, TableRows, Match, UNMATCHED_TABLE_ROW)

Генерация парсеров таблиц основана на сопоставлении строк таблицы парам "ключ-значение".

#### Поток выполнения
1. `TableConfig` задает базовый корневой элемент таблицы.
2. `TableRows` извлекает список строк (элементов `<tr>` или контейнеров).
3. Поле структуры `type=table` использует операцию `match { ... }` (узел `Match`).
4. Для каждой строки вычисляется ключ строки (`TableMatchKey`). Если предикаты `Match` истинны, вычисляется значение (`Value`).
5. Если ни одна строка не подошла, возвращается специальный маркер `UNMATCHED_TABLE_ROW` (или генерируется исключение при отсутствии `fallback`).

#### Пример (Python):
```python
class SpecsTable:
    def __init__(self, document: Any) -> None:
        self._doc = document
        self._rows = self._doc.select("table.specs tr")

    def ram(self) -> str:
        for row in self._rows:
            key_el = row.select_one("th")
            if key_el is None:
                continue
            k = key_el.get_text(strip=True)
            if k == "RAM":
                val_el = row.select_one("td")
                return val_el.get_text(strip=True)
        return ""
```

---

### 4. REST и транспортная модель (@request, Result-артефакты)

REST-структуры (`(rest)struct`) компилируются в клиенты API с типизированными эндпоинтами и монадическими результатами (`Result[T, E]`).

#### Синтезируемые AST-узлы (core/rest_artifacts.py):
1. `ResultVariantDef`: описание класса ошибки (например, `class GetUser404Err(Err[ErrorJson]): ...`).
2. `ResultAliasDef`: псевдоним типа результата метода (`GetUserResult = Union[Ok[UserJson], GetUser404Err, UnknownErr, TransportErr]`).
3. `MatcherListDef`: реестр сопоставителей ошибок `ErrMatcher(status=404, conditions=..., factory=GetUser404Err)`.

#### Структура `RequestHttp`:
Поля URL, заголовков, параметров и тела хранятся в виде токенизированных шаблонов `PlaceholderTemplate`, содержащих литеральные строки и объекты `PlaceholderSpec`.
- Имена плейсхолдеров преобразуются в конвенцию целевого языка (`to_snake_case` для Python, `to_camel_case` для JS/Go) через метод `with_renamed_placeholders()`.
- Никакого ручного парсинга regex'ами в конвертерах не производится.

---

### 5. Nested и Jsonify (вложенные структуры и JSON)

#### `Nested`
Передает текущий DOM-элемент (`ctx.prv`) в конструктор другой структуры:
- **Python:** `v2 = OtherStruct(v1).parse()`
- **JS:** `const v2 = new OtherStruct(v1).parse();`
- **Go:** `v2 := NewOtherStruct(v1).Parse()`

#### `Jsonify`
Десериализует JSON-строку в типизированный словарь/объект согласно определению `JsonDef`:
- Если задан `path="data.items"`, извлекается вложенный узел.
- При наличии `from="..."` (алиасов) генерируется код ремаппинга ключей источника в канонические имена полей схемы.

---

## 4. Каталог AST-узлов

---

### Группа 1: Модульный уровень

#### 1.1 `Module`
- **Класс:** `ssc_codegen.ast.Module` | **Метод:** `visit_module`
- **Категория:** Container
- **Поля:**
  - `doc: str` — документация уровня модуля.
  - `source_file: str` — базовое имя исходного `.kdl` файла.
  - `extensions: dict[str, ExtensionDef]` — реестр объявленных расширений.
  - `body: list[Node]` — дочерние элементы модуля (JsonDef, TypeDef, Struct, Hooks).
- **Кодогенерация:**
  - **Python:** Эмитирует docstring модуля `"""..."""`, импорты из `_builder.imports`, std-хелперы из `_builder.std_defs`, затем обходит дочерние узлы.
  - **JS:** Эмитирует JSDoc-комментарий, хелперы, классы/функции, секцию `module.exports` / `export`.
  - **Go:** Эмитирует `package <name>`, блок `import (...)`, типы и структуры.

#### 1.2 `FunctionDef`
- **Класс:** `ssc_codegen.ast.FunctionDef` | **Метод:** `visit_function_def`
- **Категория:** Pipeline
- **Поля:** `name: str`, `is_raw: bool`, `doc: str`, `accept_type_info: TypeInfo`, `ret_type_info: TypeInfo`.
- **KDL:** `fn parse_title { css "h1"; text; }` или `(raw)fn clean_id { trim; rm-prefix "id_"; }`
- **Кодогенерация:**
  - **Python:** `def parse_title(document: Any) -> str:`
  - **JS:** `function parseTitle(document) { ... }`
  - **Go:** `func ParseTitle(document *goquery.Selection) string { ... }`

#### 1.3 `CodeStartHook` / `CodeEndHook`
- **Классы:** `CodeStartHook`, `CodeEndHook` | **Методы:** `visit_code_start_hook`, `visit_code_end_hook`
- **Категория:** Leaf / Raw
- **Поля:** `body: list[Node]`
- **Назначение:** Прямая вставка пользовательского кода в начало или конец сгенерированного файла.

#### 1.4 `Utilities`
- **Класс:** `ssc_codegen.ast.Utilities` | **Метод:** `visit_utilities`
- **Категория:** Leaf
- **Назначение:** Технический узел-маркер точки вставки std-хелперов.

---

### Группа 2: Определения типов и схем

#### 2.1 `TypeDef` & `TypeDefField`
- **Классы:** `TypeDef`, `TypeDefField` | **Методы:** `visit_typedef`, `visit_typedef_field`
- **Категория:** Container
- **Поля `TypeDef`:** `name: str`, `struct_type: StructType`, `body: list[TypeDefField]`.
- **Поля `TypeDefField`:** `name: str`, `ret_type_info: TypeInfo`.
- **Кодогенерация:**
  - **Python:**
    ```python
    class ArticleItem(TypedDict):
        title: str
        price: Optional[int]
    ```
  - **JS (JSDoc):**
    ```javascript
    /**
     * @typedef {Object} ArticleItem
     * @property {string} title
     * @property {number|null} [price]
     */
    ```
  - **Go:**
    ```go
    type ArticleItem struct {
        Title string `json:"title"`
        Price *int   `json:"price,omitempty"`
    }
    ```

#### 2.2 `JsonDef` & `JsonDefField`
- **Классы:** `JsonDef`, `JsonDefField` | **Методы:** `visit_jsondef`, `visit_jsondef_field`
- **Категория:** Container
- **Поля `JsonDef`:** `name: str`, `is_array: bool`, `path: str`, `body: list[JsonDefField]`.
- **Поля `JsonDefField`:** `name: str`, `type_name: str`, `alias: str`, `doc: str`, `ret_type_info: TypeInfo`.
- **KDL:**
  ```kdl
  json User {
      id int
      fullName str from="full_name"
  }
  ```
- **Кодогенерация:**
  Генерирует тип схемы данных, а при наличии алиасов (`from="..."`) — вспомогательную функцию/метод ремаппинга ключей.

---

### Группа 3: Структуры и методы

#### 3.1 `Struct`
- **Класс:** `ssc_codegen.ast.Struct` | **Метод:** `visit_struct`
- **Категория:** Container
- **Поля:** `name: str`, `struct_type: StructType`, `keep_order: bool`, `doc: str`, `body: list[Node]`.
- **KDL:** `(item)struct Product { ... }`, `(list)struct Catalog { ... }`, `(table)struct Specs { ... }`
- **Кодогенерация:**
  Генерирует класс парсера с конструктором `__init__(self, document)`, приватным полем `self._doc` и методами парсинга полей.

#### 3.2 `StructRest`
- **Класс:** `ssc_codegen.ast.StructRest` | **Метод:** `visit_struct_rest`
- **Категория:** Container
- **Поля:** `name: str`, `errors: list[ErrorResponse]`, `doc: str`, `body: list[Node]`.
- **KDL:** `(rest)struct UsersClient { @request ... }`
- **Кодогенерация:**
  Генерирует класс REST-клиента API с методами HTTP-эндпоинтов, поддержкой sync/async выполнения, валидацией параметров и возвратом типизированных `Result[T, E]`.

#### 3.3 `Field`
- **Класс:** `ssc_codegen.ast.Field` | **Метод:** `visit_field`
- **Категория:** Pipeline
- **Поля:** `name: str`, `body: list[Node]`.
- **KDL:**
  ```kdl
  title {
      css "h1"
      text
  }
  ```
- **Семантика Context:** Начинается с `ctx.index = 0`, `ctx.prv = "v"`. Входное значение `v` инициализируется как `self._doc`. После завершения цепочки возвращается финальный `v_last`.

#### 3.4 `Init` & `InitField` & `InitFieldCall`
- **Классы:** `Init`, `InitField`, `InitFieldCall` | **Методы:** `visit_init`, `visit_init_field`, `visit_init_field_call`
- **KDL:**
  ```kdl
  @init {
      container {
          css ".main-box"
      }
  }
  ```
- **Назначение:** Предварительное вычисление промежуточных значений в конструкторе. `InitField` генерирует приватный метод расчета, `InitFieldCall` вызывает его в `__init__` и сохраняет в `self._container`, а `Self` (синтаксис `@container`) считывает значение в поле.

#### 3.5 `PreValidate`
- **Класс:** `ssc_codegen.ast.PreValidate` | **Метод:** `visit_pre_validate`
- **Категория:** Pipeline
- **Поля:** `body: list[Node]`, `accept_type_info: TypeInfo`, `ret_type_info: TypeInfo`.
- **KDL (референс из `examples/booksToScrape.kdl`):**
  ```kdl
  struct ProductInfo type=table {
      @table { css "table" }
      @rows { css-all "tr" }
      @match { css "th"; text; trim; lower }
      @value { css "td"; text }

      @pre-validate {
          assert { css "table tr" }
      }

      upc {
          match { eq "upc" }
      }
  }
  ```
- **Назначение:** Предварительная валидация документа перед началом парсинга. Генерирует приватный метод валидации `_pre_validate(self, v)` (принимающий корневой документ `self._doc`), который вызывается первой строкой внутри `parse()`:
  - **Python:**
    ```python
    def _pre_validate(self, v: Any) -> None:
        std_assert(bool(v.select("table tr")), "ProductInfo.@pre-validate assertion failed")
    ```
    И в методе `parse()`:
    ```python
    def parse(self) -> ProductInfoItem:
        self._pre_validate(self._doc)
        return {
            "upc": self.upc(),
        }
    ```
  - **JavaScript:**
    ```javascript
    _preValidate(v) {
      sscAssert(v.querySelectorAll("table tr").length > 0, "ProductInfo.@pre-validate assertion failed");
    }
    ```
  - **Go:**
    ```go
    func (p *ProductInfo) preValidate(v *goquery.Selection) error {
        if !stdAssert(v.Find("table tr").Length() > 0) {
            return errors.New("ProductInfo.@pre-validate assertion failed")
        }
        return nil
    }
    ```

#### 3.6 `CheckMethod`
- **Класс:** `ssc_codegen.ast.CheckMethod` | **Метод:** `visit_check_method`
- **Категория:** Pipeline
- **KDL:**
  ```kdl
  @check is_available {
      css ".in-stock"
      to-bool
  }
  ```
- **Назначение:** Генерация булевого метода-предиката проверки состояния страницы.

#### 3.7 `SplitDoc`
- **Класс:** `ssc_codegen.ast.SplitDoc` | **Метод:** `visit_split_doc`
- **Категория:** Pipeline
- **KDL:**
  ```kdl
  @split-doc {
      css-all ".item"
  }
  ```
- **Назначение:** Разделение документа на элементы для `(list)struct` или `(dict)struct`.

#### 3.8 `Key` & `Value`
- **Классы:** `Key`, `Value` | **Методы:** `visit_key`, `visit_value`
- **Категория:** Pipeline
- **KDL:**
  ```kdl
  @key { css ".name"; text; }
  @value { css ".val"; text; }
  ```
- **Назначение:** Извлечение ключа и значения для каждого элемента `(dict)struct`.

#### 3.9 `StartParse`
- **Класс:** `ssc_codegen.ast.StartParse` | **Метод:** `visit_start_parse`
- **Назначение:** Генерация основного метода `parse()`, агрегирующего все поля в итоговый словарь/объект.

---

### Группа 4: Табличные узлы

#### 4.1 `TableConfig`
- **Класс:** `TableConfig` | **Метод:** `visit_table_config`
- **Категория:** Pipeline
- **KDL:** `@table { css "table.data"; }`
- **Назначение:** Выбирает корневой DOM-элемент таблицы.

#### 4.2 `TableRows`
- **Класс:** `TableRows` | **Метод:** `visit_table_rows`
- **Категория:** Pipeline
- **KDL:** `@rows { css-all "tr"; }`
- **Назначение:** Извлекает список строк таблицы.

#### 4.3 `TableMatchKey`
- **Класс:** `TableMatchKey` | **Метод:** `visit_table_match_key`
- **Категория:** Pipeline
- **KDL:** `@match { css "th"; text; }`
- **Назначение:** Пайплайн извлечения ключа из строки таблицы.

#### 4.4 `Match`
- **Класс:** `Match` | **Метод:** `visit_match`
- **Категория:** Predicate Container
- **KDL:**
  ```kdl
  cpu {
      match {
          eq "Processor"
      }
  }
  ```
- **Назначение:** Фильтрация строки таблицы по условию на ключ с последующим возвратом значения `@value`.

---

### Группа 5: HTTP и REST артефакты

#### 5.1 `MethodFetch`
- **Класс:** `MethodFetch` | **Метод:** `visit_method_fetch`
- **Поля:** `name: str`, `http_request: RequestHttp`, `response_path: str`, `response_join: str`.
- **Назначение:** Генерация `fetch()` и `async_fetch()` методов для HTML-структур.

#### 5.2 `MethodRest`
- **Класс:** `MethodRest` | **Метод:** `visit_method_rest`
- **Поля:** `name: str`, `http_request: RequestHttp`, `response_schema: str`, `doc: str`, `result_alias_name: str`.
- **Назначение:** Генерация метода REST-клиента, возвращающего `ResultAlias`.

#### 5.3 `ErrorResponse`
- **Класс:** `ErrorResponse` | **Метод:** `visit_error_response`
- **Поля:** `status: int`, `schema_name: str`, `conditions: dict[str, Any]`, `required_keys: list[str]`.
- **KDL:** `@error 404 schema=ErrorJson { body-matches ... }`
- **Назначение:** Декларация сопоставления HTTP-ошибки в `(rest)struct`. Используется на этапе построения AST для синтеза `ResultVariantDef` и `MatcherListDef`.

#### 5.4 `ResultVariantDef`
- **Класс:** `ResultVariantDef` | **Метод:** `visit_result_variant_def`
- **Поля:** `name: str`, `status: int`, `schema_name: str`, `schema_is_array: bool`.
- **Кодогенерация (Python):**
  ```python
  @dataclass
  class GetUser404Err(Err[ErrorJson]):
      status: Literal[404] = 404
  ```

#### 5.5 `ResultAliasDef`
- **Класс:** `ResultAliasDef` | **Метод:** `visit_result_alias_def`
- **Поля:** `name: str`, `response_schema: str`, `response_is_array: bool`, `err_variants: list[str]`.
- **Кодогенерация (Python):**
  ```python
  GetUserResult = Union[Ok[UserJson], GetUser404Err, UnknownErr, TransportErr]
  ```

#### 5.6 `MatcherListDef`
- **Класс:** `MatcherListDef` | **Метод:** `visit_matcher_list_def`
- **Поля:** `struct_name: str`, `entries: list[MatcherEntry]`.
- **Кодогенерация (Python):**
  ```python
  _users_matchers = [
      ErrMatcher(404, lambda _b: True, GetUser404Err),
  ]
  ```

---

### Группа 6: Пользовательские расширения

#### 6.1 `ExtensionCall`
- **Класс:** `ExtensionCall` | **Метод:** `visit_extension_call`
- **Поля:** `qualified_name: str`, `definition: ExtensionDef`.
- **KDL:** `!Utils.slugify`
- **Семантика:** Подстановка шаблона `target.emit` с регистрацией зависимостей в `ModuleBuilder`.

---

### Группа 7: Селекторы DOM

| Узел | Метод | KDL | Типы | Python (bs4) | JS | Go (goquery) |
|---|---|---|---|---|---|---|
| `CssSelect` | `visit_css_select` | `css ".title"` | `DOC -> DOC` | `v1 = v.select_one(".title")` | `const v1 = v.querySelector(".title");` | `v1 := v.Find(".title").First()` |
| `CssSelectAll` | `visit_css_select_all`| `css-all ".item"` | `DOC -> LIST_DOC` | `v1 = v.select(".item")` | `const v1 = Array.from(v.querySelectorAll(".item"));` | `v1 := v.Find(".item")` |
| `CssRemove` | `visit_css_remove` | `css-remove ".ads"` | `DOC -> DOC` | `for el in v.select(".ads"): el.decompose()` | `v.querySelectorAll(".ads").forEach(e => e.remove());` | `v.Find(".ads").Remove()` |
| `XpathSelect` | `visit_xpath_select` | `xpath "//h1"` | `DOC -> DOC` | `v1 = v.xpath("//h1")[0]` | (Библиотечный XPath) | (XPath хелпер) |
| `XpathSelectAll`| `visit_xpath_select_all`| `xpath-all "//a"` | `DOC -> LIST_DOC`| `v1 = v.xpath("//a")` | (Библиотечный XPath) | (XPath хелпер) |
| `XpathRemove` | `visit_xpath_remove` | `xpath-remove "//script"`| `DOC -> DOC` | `for el in v.xpath("//script"): ...` | (XPath remove) | (XPath remove) |

---

### Группа 8: Извлечение данных

| Узел | Метод | KDL | Типы | Python | JS | Go |
|---|---|---|---|---|---|---|
| `Text` | `visit_text` | `text` | `DOC -> STR` | `v1 = v.get_text(strip=True)` | `const v1 = v.textContent.trim();` | `v1 := strings.TrimSpace(v.Text())` |
| `Raw` | `visit_raw` | `raw` / `raw inner` | `DOC -> STR` | `v1 = str(v)` / `v1 = "".join(str(c) for c in v.children)` | `const v1 = v.outerHTML;` / `v.innerHTML;` | `v1, _ := goquery.OuterHtml(v)` / `v.Html()` |
| `Attr` | `visit_attr` | `attr "href"` | `DOC -> STR` | `v1 = v.get("href", "")` | `const v1 = v.getAttribute("href") || "";` | `v1, _ := v.Attr("href")` |

---

### Группа 9: Строковые трансформации

Все строковые трансформации поддерживают **Map semantics**: если на вход подан `LIST_STRING`, операция применяется к каждому элементу списка.

| Узел | Метод | KDL | Поля | Python | JS | Go |
|---|---|---|---|---|---|---|
| `Trim` | `visit_trim` | `trim` | `substr: str` | `v1 = v.strip()` | `const v1 = v.trim();` | `v1 := strings.TrimSpace(v)` |
| `Ltrim` | `visit_l_trim` | `ltrim` | `substr: str` | `v1 = v.lstrip()` | `const v1 = v.trimStart();` | `v1 := strings.TrimLeft(v, " ")` |
| `Rtrim` | `visit_r_trim` | `rtrim` | `substr: str` | `v1 = v.rstrip()` | `const v1 = v.trimEnd();` | `v1 := strings.TrimRight(v, " ")` |
| `NormalizeSpace`| `visit_norm_space` | `normalize-space`| — | `v1 = " ".join(v.split())` | `const v1 = v.replace(/\s+/g, ' ').trim();` | `v1 := strings.Join(strings.Fields(v), " ")` |
| `RmPrefix` | `visit_rm_prefix` | `rm-prefix "id:"` | `substr: str` | `v1 = v.removeprefix("id:")` | `const v1 = v.startsWith("id:") ? v.slice(3) : v;` | `v1 := strings.TrimPrefix(v, "id:")` |
| `RmSuffix` | `visit_rm_suffix` | `rm-suffix ".html"`| `substr: str` | `v1 = v.removesuffix(".html")` | `const v1 = v.endsWith(".html") ? v.slice(0, -5) : v;`| `v1 := strings.TrimSuffix(v, ".html")` |
| `RmPrefixSuffix`| `visit_rm_prefix_suffix`| `rm-prefix-suffix "_"`| `substr: str` | `v1 = v.removeprefix("_").removesuffix("_")` | `...` | `...` |
| `Fmt` | `visit_format` | `fmt "https://site.com/{}"` | `template: str` | `v1 = f"https://site.com/{v}"` | `const v1 = \`https://site.com/${v}\`;` | `v1 := fmt.Sprintf("https://site.com/%s", v)` |
| `Repl` | `visit_repl` | `repl "old" "new"` | `old, new: str` | `v1 = v.replace("old", "new")` | `const v1 = v.replaceAll("old", "new");` | `v1 := strings.ReplaceAll(v, "old", "new")` |
| `ReplMap` | `visit_repl_map` | `repl { "a" "b" }` | `replacements: dict` | `v1 = repl_map(v, {...})` | `const v1 = replMap(v, {...});` | `v1 := stdReplMap(v, ...)` |
| `Lower` | `visit_lower` | `lower` | — | `v1 = v.lower()` | `const v1 = v.toLowerCase();` | `v1 := strings.ToLower(v)` |
| `Upper` | `visit_upper` | `upper` | — | `v1 = v.upper()` | `const v1 = v.toUpperCase();` | `v1 := strings.ToUpper(v)` |
| `Split` | `visit_split` | `split ","` | `sep: str` | `v1 = v.split(",")` | `const v1 = v.split(",");` | `v1 := strings.Split(v, ",")` |
| `Join` | `visit_join` | `join ", "` | `sep: str` | `v1 = ", ".join(v)` | `const v1 = v.join(", ");` | `v1 := strings.Join(v, ", ")` |
| `Unescape` | `visit_unescape` | `unescape` | — | `v1 = html.unescape(v)` | `const v1 = unescapeHtml(v);` | `v1 := html.UnescapeString(v)` |

---

### Группа 10: Регулярные выражения

| Узел | Метод | KDL | Описание / Поведение |
|---|---|---|---|
| `Re` | `visit_re` | `re #"ID: (\d+)"#` | Извлекает первую capturing group. Если совпадений нет, выбрасывает ошибку (перехватываемую `Fallback`). |
| `ReAll` | `visit_re_all` | `re-all #"\d+"#` | Возвращает список всех совпадений (`LIST_STRING`). |
| `ReSub` | `visit_re_sub` | `re-sub #"\s+"# "-"` | Заменяет совпадения по регулярному выражению на строку подстановки. |

---

### Группа 11: Массивы и срезы

| Узел | Метод | KDL | Поля | Python | JS | Go |
|---|---|---|---|---|---|---|
| `Index` | `visit_index` | `index 0` / `first` / `last` | `i: int` | `v1 = v[0]` | `const v1 = v[0];` | `v1 := v[0]` |
| `Slice` | `visit_slice` | `slice 0 5` | `start, end: int` | `v1 = v[0:5]` | `const v1 = v.slice(0, 5);` | `v1 := v[0:5]` |
| `Len` | `visit_len` | `len` | — | `v1 = len(v)` | `const v1 = v.length;` | `v1 := len(v)` |
| `Unique` | `visit_unique` | `unique` | `keep_order: bool` | `v1 = list(dict.fromkeys(v))` | `const v1 = Array.from(new Set(v));` | `v1 := stdUnique(v)` |

---

### Группа 12: Приведение типов

| Узел | Метод | KDL | Поля | Python | JS | Go |
|---|---|---|---|---|---|---|
| `ToInt` | `visit_to_int` | `to-int` | — | `v1 = int(v)` | `const v1 = parseInt(v, 10);` | `v1, _ := strconv.Atoi(v)` |
| `ToFloat` | `visit_to_float` | `to-float` | — | `v1 = float(v)` | `const v1 = parseFloat(v);` | `v1, _ := strconv.ParseFloat(v, 64)` |
| `ToBool` | `visit_to_bool` | `to-bool` | — | `v1 = bool(v)` | `const v1 = Boolean(v);` | `v1 := bool(len(v) > 0)` |
| `Jsonify` | `visit_jsonify` | `jsonify Schema` | `schema_name, path` | `v1 = json.loads(v)` + remap | `const v1 = JSON.parse(v);` | `gjson.Get(...)` / `json.Unmarshal` |
| `Nested` | `visit_nested` | `nested Item` | `struct_name` | `v1 = Item(v).parse()` | `const v1 = new Item(v).parse();` | `v1 := NewItem(v).Parse()` |

---

### Группа 13: Управление потоком

#### 13.1 `Self`
- **Класс:** `Self` | **Метод:** `visit_self`
- **KDL:** `@container`
- **Назначение:** Чтение предвычисленного значения: `v1 = self._container`.

#### 13.2 `Return`
- **Класс:** `Return` | **Метод:** `visit_return`
- **Назначение:** Неявный терминальный узел pipeline. Эмитирует `return ctx.prv`.

#### 13.3 `Fallback`
- **Класс:** `Fallback` | **Метод:** `visit_fallback`
- **Назначение:** Обработка ошибок в pipeline (см. детальный разбор в [разделе 3.1](#1-fallback-trycatch-и-синхронизация-переменных)).

---

### Группа 14: Предикаты и логические условия

#### 14.1 Контейнеры предикатов
- **`Filter` (`visit_filter`):** Фильтрация массива: `v1 = [x for x in v if condition(x)]`.
- **`Assert` (`visit_assert`):** Проверка условия: `if not condition(v): raise AssertionError(...)`.
- **`Match` (`visit_match`):** Сопоставление строки таблицы.

#### 14.2 Логические связки
- **`LogicAnd` (`visit_logic_and`):** Объединение условий через `and` / `&&`.
- **`LogicOr` (`visit_logic_or`):** Объединение условий через `or` / `||`.
- **`LogicNot` (`visit_logic_not`):** Инверсия условия `not (...)` / `!(...)`.

#### 14.3 Скалярные предикаты
| Узел | Метод | KDL | Смысл |
|---|---|---|---|
| `PredEq` | `visit_predicate_eq` | `eq "val"` / `eq 5` | Равенство значению или длине строки. |
| `PredNe` | `visit_predicate_ne` | `ne "val"` | Неравенство значению или длине строки. |
| `PredStarts` | `visit_predicate_starts` | `starts "http"` | `v.startswith(...)` |
| `PredEnds` | `visit_predicate_ends` | `ends ".png"` | `v.endswith(...)` |
| `PredContains` | `visit_predicate_contains` | `contains "test"` | `"test" in v` |
| `PredRe` | `visit_predicate_re` | `re #"\d+"#` | `bool(re.search(pattern, v))` |
| `PredReAny` | `visit_predicate_re_any` | `re-any #"\d+"#` | Хотя бы один элемент списка удовлетворяет regex. |
| `PredReAll` | `visit_predicate_re_all` | `re-all #"\d+"#` | Все элементы списка удовлетворяют regex. |

#### 14.4 DOM предикаты
| Узел | Метод | KDL | Смысл |
|---|---|---|---|
| `PredCss` | `visit_predicate_css` | `css ".active"` | Наличие дочернего элемента по CSS. |
| `PredXpath` | `visit_predicate_xpath` | `xpath ".//span"` | Наличие дочернего элемента по XPath. |
| `PredHasAttr` | `visit_predicate_has_attr` | `has-attr "disabled"` | Наличие атрибута у элемента. |
| `PredAttrEq` / `Ne` | `visit_predicate_attr_eq` | `attr-eq "type" "submit"` | Сравнение значения атрибута. |
| `PredAttrStarts` / `Ends` / `Contains` | `visit_predicate_attr_starts` | `attr-starts "href" "/item"` | Проверка префикса/суффикса атрибута. |
| `PredAttrRe` | `visit_predicate_attr_re` | `attr-re "class" #"btn-.*"` | Регулярное выражение на атрибут. |
| `PredTextStarts` / `Ends` / `Contains` / `Re` | `visit_predicate_text_*` | `text-contains "Success"` | Проверка содержимого текста элемента. |
| `PredCountEq` / `Ne` / `Gt` / `Lt` / `Ge` / `Le` / `Range` | `visit_predicate_count_*` | `count > 5`, `count != 0`, `count 1..10` | Проверка количества элементов в списке (`len(v)`). |
