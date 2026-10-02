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
- `@value <Type>` — **обязательная** директива, задающая тип значений: скаляр (`str`, `int`, `float`, `bool`), массив `(array)Type` или ссылка на другую `json` схему.
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
| `E040` | `error` | Некорректный синтаксис dot-path (пустые сегменты `a..b`, ведущие/замыкающие точки `.a` / `a.`). |
| `E041` | `error` | Коллизия алиасов (два поля ссылаются на один и тот же путь источника). |
| `W040` | `warning` | Необрезанные пробелы в начале/конце `from="..."`. |
| `W041` | `warning` | Использование `path="..."` вместо `from="..."` для алиаса JSON поля. |
| `W011` | `warning` | Устаревший позиционный алиас (рекомендуется использовать `from="..."`). |

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
