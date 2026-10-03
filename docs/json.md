# JSON схемы и `jsonify`

**Версия DSL:** 2.2  
**Последнее обновление:** 2026-09-04

`json` блоки описывают структуру JSON, который затем разбирается через
операцию `jsonify` или используется в качестве схемы ответа REST-эндпоинтов (`@request response=Schema`).

## Строгая проекция (Allowlist Projection)

Начиная с DSL v2.2, все `json` схемы работают в режиме **строгой проекции**:
- В результирующий словарь/объект попадают **только** явно объявленные в схеме поля.
- Все лишние/неописанные ключи из входящего wire JSON автоматически отбрасываются.
- Обеспечивается строгая типизация и совместимость с компилируемыми языками (Python `TypedDict`, JavaScript JSDoc, Go structs).

## Объявление JSON схем

```kdl
json Author {
    name str
    goodreads_links str
    slug str
}

(array)json Quote {
    tags (array)str
    author Author
    text str
}
```

### JSON Dictionary схемы (`(dict)json`)

Для JSON-объектов с динамическими произвольными или числовыми ключами и однородными значениями (словари переводов по ID серий, карты ресурсов, локализация) используются словарь-схемы `(dict)json`:

```kdl
(dict)json EpisodeTranslations {
    @key int
    @value (array)str
}

(dict)json ResourceCatalog {
    @key str
    @value ResourceItem
}
```

Внутри `(dict)json` разрешены только директивы `@key` и `@value`:
- `@value <Type>` — **обязательная** директива, задающая тип значений: скаляр (`str`, `int`, `float`, `bool`), массив `(array)Type`, ссылка на другую `json` схему либо инлайн-блок схемы `{ ... }`.
- `@key <ScalarType>` — **опциональная** директива, задающая скалярный тип ключа (`str`, `int`, `float`, `bool`). По умолчанию `@key str`.

Генераторы кода создают нативные типизированные словари:
- **Python**: `EpisodeTranslationsJson = Dict[int, List[str]]`
- **Go**: `type EpisodeTranslationsJson = map[int64][]string`
- **Rust**: `pub type EpisodeTranslationsJson = std::collections::HashMap<i64, Vec<String>>;`
- **JavaScript**: `/** @typedef {Record<number, string[]>} EpisodeTranslationsJson */`

При рантайм-проекции (`ssc_json_project`) проверяется, что входные данные являются словарем (иначе генерируется `SscJsonSchemaError`), а значения рекурсивно ремаппятся, если `@value` ссылается на модель с алиасами.

## Вложенные инлайн-схемы (Inline JSON Schemas)

Вместо объявления десятков плоских глобальных схем в модуле, вложенные структуры можно объявлять непосредственно внутри полей родительской `json` схемы:

1. **Анонимные объекты (`field_name { ... }`)**:
   Имя модели синтезируется компилятором по цепочке предков: `{ParentName}{FieldName}` в PascalCase (например, `AnimeResponse` + `material_data` → `AnimeResponseMaterialDataJson`).
2. **Явно именованные объекты (`field_name ModelName { ... }`)**:
   Задаёт явное имя результирующей модели (например, `franchise Franchise { ... }` → `FranchiseJson`).
3. **Именованные массивы объектов (`field_name (array)ItemModel { ... }`)**:
   Задаёт массив вложенных объектов (например, `nodes (array)Node { ... }` → `NodeJson`). Из-за грамматики KDL 2.0 указание имени модели обязательно.
4. **Инлайн-словари (`field_name (dict)DictName { ... }` или `(dict)field_name { ... }`)**:
   Объявляет словарь в поле родительской модели с директивами `@key` и `@value`. В KDL 2.0 аннотация типа должна предшествовать значению или имени узла: указывается `field_name (dict)DictName { ... }` (аналогично `(array)ItemModel`) либо префикс узла `(dict)field_name { ... }`.
5. **Инлайн-схемы в директиве `@value` (`@value ModelName { ... }` или `@value { ... }`)**:
   Директива `@value` как в словарях верхнего уровня `(dict)json`, так и во вложенных полях-словарях `(dict)` поддерживает дочерний блок полей `{ ... }`. Это позволяет описывать структуры значений словарей непосредственно по месту их использования без предварительного объявления отдельных глобальных схем.

```kdl
json AnimeResponse {
    id str

    // Явно именованный вложенный объект
    franchise Franchise {
        id str
        links (array)Links {
            id int
            relation str
        }
    }

    // Анонимный вложенный объект (AnimeResponseMaterialDataJson)
    material_data {
        anime_title str
        year int
    }

    // Инлайн словарь
    translations (dict)Translations {
        @key int
        @value (array)str
    }
}
```

Все инлайн-поля поддерживают модификаторы `from="..."`, `@omitempty`, `?` (nullable), а также `path="..."` как синоним для `from="..."` (с предупреждением `W041`).
Компилятор выполняет **хоистинг** (поднятие) инлайн-схем в топологическом порядке зависимостей выше родительской схемы.

Типы полей:

| Тип | Описание |
|---|---|
| `str` | Строка |
| `int` | Целое число (`int` в Python, `number` в JS, `int64` в Go) |
| `float` | Число с плавающей точкой (`float` в Python, `number` в JS, `float64` в Go) |
| `bool` | Логическое значение |
| `null` | Null |
| `<Name>` | Ссылка на другую `json` схему |

Модификаторы:
- `(array)type` — массивное поле, например `(array)str` или `(array)Author`.
- `type?` — nullable/optional поле (значение или `null`/`None`), например `str?`.
- `@omitempty` — поле может отсутствовать в JSON (при отсутствии ключ опускается из выходного словаря).
- `@skip` — полностью исключить поле из генерации.

### Инлайн-схемы значений словарей (`@value` с дочерним блоком)

Директива `@value` внутри словарей верхнего уровня `(dict)json` и инлайн-словарей `(dict)` поддерживает объявление дочернего блока полей `{ ... }`. Это позволяет описывать сложные вложенные структуры значений словарей без необходимости предварительного объявления глобальных схем.

#### Варианты синтаксиса

1. **Явное имя модели**:
   - Позиционный аргумент: `@value ModelName { ... }`
   - Префиксная аннотация типа: `(ModelName)@value { ... }`
   Оба варианта создают модель с заданным именем (например, `TranslationValueJson`).

2. **Массивы объектов в качестве значений словаря**:
   - Аргумент с аннотацией массива: `@value (array)ItemModel { ... }`
   - Префиксная аннотация типа: `(array)@value ItemModel { ... }`
   *Примечание:* По грамматике KDL 2.0 указание имени модели элемента (`ItemModel`) обязательно. Анонимный блок массива `(array)@value { ... }` запрещён и вызывает ошибку `error[E001]`.

3. **Анонимные блоки значений (`@value { ... }`)**:
   Если имя модели опущено, компилятор автоматически синтезирует каноническое имя модели в PascalCase по следующим правилам:
   - **Инлайн-словарь с явным именем типа** (`translations (dict)Translation { @value { ... } }`):  
     `{DictName}Value` → `TranslationValue` (`TranslationValueJson`).
   - **Анонимный инлайн-словарь в поле родительской модели** (`translations (dict) { @value { ... } }` внутри `json AnimeResponse`):  
     `{Parent}{Field.to_pascal_case()}Value` → `AnimeResponseTranslationsValue` (`AnimeResponseTranslationsValueJson`).
   - **Словарь верхнего уровня** (`(dict)json Translations { @value { ... } }`):  
     `{DictSchema}Value` → `TranslationsValue` (`TranslationsValueJson`).

4. **Модификаторы опциональности значений**:
   Блок `@value` поддерживает суффикс `?` для nullable-значений словаря (`@value TranslationValue? { ... }`, `(TranslationValue?)@value { ... }`, `@value? TranslationValue { ... }`, `@value? { ... }`).

#### Многоуровневые вложенные словари и рекурсивный хоистинг

Внутри блока `@value` разрешены любые допустимые поля JSON-схем: обычные скаляры, алиасы `from="..."`, `@omitempty`, nullable `?`, `@skip`, вложенные объекты (`field { ... }`), а также **дальнейшие вложенные словари** `(dict)` со своими блоками `@value`.

Пример многоуровневой иерархии (ответ медиа-агрегатора с переводами и картой эпизодов):

```kdl
json AnimeResponse {
    translations (dict)Translation {
        @key str
        @value TranslationValue {
            is_active bool
            season int
            type str
            viewers int
            watch_seconds int

            // Вложенный словарь эпизодов внутри значения словаря переводов
            episodes (dict)EpisodeMap {
                @key int
                @value EpisodeValue {
                    link str from="stream_url"
                    bitrate int?
                    screenshots @skip
                }
            }
        }
    }
}
```

Компилятор выполняет **рекурсивный хоистинг (post-order)**:
1. Сначала компилируются и поднимаются в `module.body` самые глубокие листовые схемы: `EpisodeValue`.
2. Затем поднимается содержащая их схема: `TranslationValue`.
3. В конце объявляется корневая схема `AnimeResponse`.

В сгенерированном коде модели объявляются строго в порядке зависимостей:
- **Python**: `EpisodeValueJson` (TypedDict) → `TranslationValueJson` (TypedDict) → `AnimeResponseJson` (TypedDict).
- **Go**: `type EpisodeValueJson struct` → `type TranslationValueJson struct` → `type AnimeResponseJson struct`.
- **Rust**: `pub struct EpisodeValueJson` → `pub struct TranslationValueJson` → `pub struct AnimeResponseJson`.
- **JavaScript**: JSDoc `@typedef {Object} EpisodeValueJson` → `TranslationValueJson` → `AnimeResponseJson`.

Рантайм-проекция (`ssc_json_project` в Python и `sscJsonProject` в JS) автоматически проецирует записи каждого словаря на всех уровнях вложенности, применяя ремаппинг ключей (`from="..."`), фильтрацию неописанных полей и отбрасывание `@skip`.

#### Top-level `(dict)json` с инлайн-блоком `@value`

Инлайн-блоки значений также поддерживаются в словарях верхнего уровня:

```kdl
(dict)json AnimeTranslations {
    @key str
    @value TranslationValue {
        title str from="wire_title"
        active bool
        episodes (dict)EpisodeMap {
            @key int
            @value EpisodeValue {
                link str from="stream_url"
                bitrate int?
            }
        }
    }
}
```

Либо в анонимной форме (синтезирует модель `AnimeTranslationsValueJson`):

```kdl
(dict)json AnimeTranslations {
    @key str
    @value {
        title str from="wire_title"
        active bool
    }
}
```

## Dot-Path навигация и Alias ключей (`from="..."`)

Свойство `from="..."` позволяет задавать как плоские алиасы ключей, так и глубокую точечную навигацию по объектам и массивам (`a.0.b`):

```kdl
json UserProfile {
    user_id     str
    display_name str  from="profile.name"           // вложенный объект
    avatar_url   str? from="profile.avatar.url"      // безопасный null при отсутствии
    top_badge    str? from="badges.0.icon"          // доступ по числовому индексу массива
    legacy_id    int  @omitempty from="meta.legacy_id" // опускается, если ключ отсутствует
}
```

- **Буквенно-цифровые сегменты** (`profile`, `avatar`, `url`) обращаются к ключам объекта.
- **Числовые сегменты** (`0`, `1`, `10`) обращаются к элементам массива по 0-based индексу.

### Fail-Fast Контракт

- **Обязательные поля** (без `?` и без `@omitempty`): если путь не может быть пройден, отсутствует в JSON или равен `null`, генерируется ошибка контракта:
  - Python: `SscJsonFieldMissingError` / `SscJsonPathError` (наследники `SscJsonError`)
  - JavaScript: `SscJsonFieldMissingError` / `SscJsonPathError` (наследники `SscJsonError`)
  - Go: возврат `fmt.Errorf(...)` из `UnmarshalJSON`
- **Nullable поля (`type?`)**: при отсутствии пути или `null` значении на проводе поле получает значение `None` / `null`.
- **Omit-empty поля (`@omitempty`)**: при отсутствии пути ключ не добавляется в результирующий словарь/объект.

## Правила линтера (`ssc-gen check`)

| Код | Уровень | Описание |
|---|---|---|
| `E001` | `error` | Пустой инлайн-блок `{}` в `@value`; массив `(array)@value { ... }` без имени модели элемента; коллизия имени модели с существующей схемой. |
| `E002` | `error` | Использование модификатора `@skip` на директиве `@value` с дочерним блоком полей. |
| `E040` | `error` | Некорректный синтаксис dot-path (пустые сегменты `a..b`, ведущие/замыкающие точки `.a` / `a.`). |
| `E041` | `error` | Коллизия алиасов (два поля ссылаются на один и тот же путь источника). |
| `E300` | `error` | Ссылка на необъявленную схему внутри блока `@value` или поля родительской модели. |
| `W040` | `warning` | Необрезанные пробелы в начале/конце `from="..."`. |
| `W041` | `warning` | Использование `path="..."` вместо `from="..."` для алиаса JSON поля. |
| `W011` | `warning` | Устаревший позиционный алиас (рекомендуется использовать `from="..."`). |

### Прерывание переноса строк в KDL (`\`) комментариями

В спецификации KDL 2.0 однострочные комментарии `//` захватывают символ новой строки `\n`. Если при форматировании многострочных выражений (например, длинного HTTP-запроса в `@request`) поместить комментарий после обратного слеша `\`:

```kdl
(rest)struct MyApi {
    @request "curl 'https://api.example.com'" \ // комментарий прерывает перенос строки!
    "-H 'Authorization: Bearer token'"
}
```

перенос строки аннулируется, и следующая строка парсится как изолированное поле структуры. Линтер отслеживает такие поля (имена, начинающиеся с сигнатур `curl `, `http://`, `https://`, `GET `, `POST `, `-H `) и выдаёт защитный хинт:

```
hint: KDL line continuation ('\') cannot be followed by single-line comments ('//'); move comments outside multi-line requests
```

## Использование `jsonify`

```kdl
struct Main {
    @init {
        raw-json { raw; re JSON-PATTERN }
    }

    all-quotes { @raw-json; jsonify Quote }
    first-quote { @raw-json; jsonify Quote path="0" }
    author { @raw-json; jsonify Author path="2.author" }
}
```

`jsonify` принимает один обязательный аргумент — имя схемы, и опциональное свойство `path="..."` для извлечения поддерева перед применением схемы.
Путь выбирает **фрагмент входного JSON**, а не поле внутри объявленной схемы:
кардинальность результата всегда берётся из объявления `json` / `(array)json`.
Например, `(array)json Quote` с `path="data.quotes"` возвращает `Vec<QuoteJson>`,
а `json Author` с `path="data.author"` возвращает один `AuthorJson`.

## JSON в атрибуте/свойстве HTML

JSON может лежать в атрибуте:

```kdl
struct DataState {
    json {
        css "#app"
        attr "data-state"
        // Важно: jsonify не делает unescape автоматически.
        // Если JSON экранирован HTML-энтитями, добавьте unescape перед jsonify.
        unescape
        jsonify AppState
    }
}
```
