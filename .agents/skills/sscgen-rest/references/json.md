# JSON схемы и `jsonify`

**Версия DSL:** 2.2
**Последнее обновление:** 2026-08-13

`json` блоки описывают структуру JSON, который затем можно разобрать через
операцию `jsonify`.

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

Типы полей:

| Тип | Описание |
|---|---|
| `str` | Строка |
| `int` | Целое число |
| `float` | Число с плавающей точкой |
| `bool` | Логическое значение |
| `null` | Null |
| `<Name>` | Ссылка на другую `json` схему |

Модификаторы:

| Модификатор | Семантика | Python | Go | JS |
|---|---|---|---|---|
| `(array)type` | Массивное поле (`(array)str`, `(array)User`) | `List[T]` | `[]T` | `Array<T>` |
| `type?` | Nullable: ключ присутствует, значение может быть `null` | `Optional[T]` | `*T` | `T\|null` |
| `@omitempty` | Ключ может **полностью отсутствовать** в JSON (не путать с `?`) | `NotRequired[T]` | `*T` + `json:"name,omitempty"` | JSDoc `T (OMITEMPTY)` |
| `@skip` | Поле разбирается линтером, но **исключается из генерируемых типов**. Тип опционален (по умолчанию `str`) | выбрасывается из TypedDict | выбрасывается из struct | выбрасывается из JSDoc |

Различие `?` vs `@omitempty`:
- `"name": null` в реальном ответе → `name str?` (ключ есть, значение null).
- Ключ `pagination` отсутствует на первой странице → `pagination Pagination @omitempty`.
- Возможны оба состояния одновременно → `pagination Pagination? @omitempty`.

`@skip` позволяет не указывать тип — по умолчанию подставляется `str`:

```kdl
json Echo {
    debug str? @skip       # отпарсено и выброшено
    legacy_field @skip     # тип = str по умолчанию, поле выброшено
}
```

Модификаторы можно комбинировать:

```kdl
json Item {
    url str?                          // optional через суффикс
    id str @omitempty                 // поле может отсутствовать
    inner Inner
    meta Meta @skip                   // исключить из типов
    item2 Item? @omitempty            // комбо: может отсутствовать + nullable
}
```

Правила:
- `json <Name> { ... }` объявляет схему.
- `(array)json <Name>` помечает схему как массив верхнего уровня.
- `(dict)json <Name>` объявляет динамический словарь (`@key <ScalarType>`, `@value <Type>`).
- Поля могут ссылаться на другие `json` схемы по имени.

### JSON Dictionary схемы (`(dict)json` и `(dict)` поля)

Для JSON-объектов с динамическими/числовыми ключами (например, переводы по ID серий `{"1": ["jap", "dub"]}`):

```kdl
(dict)json Translations {
    @key int
    @value (array)str
}

json ApiResponse {
    id str
    translations (dict)Translations {
        @key str
        @value (array)str
    }
}
```

Типы ключей (`@key`): `str` (по умолчанию), `int`, `float`, `bool`.

#### Инлайн-блоки схем в директиве `@value`

Директива `@value` как в словарях верхнего уровня `(dict)json`, так и в инлайн-полях `(dict)` поддерживает дочерний блок полей `{ ... }`. Это позволяет описывать сложные вложенные структуры ответов REST API:

```kdl
json AnimeResponse {
    translations (dict)Translation {
        @key str
        @value TranslationValue {
            is_active bool
            episodes (dict)EpisodeMap {
                @key int
                @value EpisodeValue {
                    link str from="stream_url"
                    bitrate int?
                    secret_token @skip
                }
            }
        }
    }
}

(rest)struct AnimeAPI {
    @request response=AnimeResponse """
    GET /anime/{{id:int}} HTTP/1.1
    Host: api.example.com
    """
    @error 404 Err
}
```

Top-level словарь как схема ответа REST-запроса с инлайн-блоком:

```kdl
(dict)json AnimeTranslations {
    @key str
    @value {
        title str from="wire_title"
        active bool
    }
}

(rest)struct AnimeAPI {
    @request response=AnimeTranslations """
    GET /anime/translations HTTP/1.1
    Host: api.example.com
    """
    @error 404 Err
}
```

**Синтаксические формы `@value` с блоком:**
- Явное имя модели: `@value ModelName { ... }` или `(ModelName)@value { ... }`.
- Массивы моделей: `@value (array)ItemModel { ... }` или `(array)@value ItemModel { ... }` (указание `ItemModel` обязательно).
- Анонимный блок: `@value { ... }` автоматически синтезирует каноническое имя модели:
  - В именованном инлайн-словаре `field (dict)DictName`: `{DictName}Value` (`TranslationValueJson`).
  - В анонимном инлайн-словаре `field (dict)` под родителем `Parent`: `{Parent}{Field.to_pascal_case()}Value` (`AnimeResponseTranslationsValueJson`).
  - В словаре верхнего уровня `(dict)json DictName`: `{DictSchema}Value` (`AnimeTranslationsValueJson`).

**Рекурсивный хоистинг:** Вложенные словари и объекты компилятор поднимает post-order (снизу вверх, от листовых `EpisodeValue` к родительским `TranslationValue` и `AnimeResponse`), гарантируя топологический порядок и отсутствие циклических ссылок в сгенерированных типах (Python `TypedDict`, Go `struct`, Rust `struct`, JavaScript JSDoc `@typedef`).

**Валидация линтера:**
- Пустой блок `{}` внутри `@value` запрещён (`error[E001]`).
- `@skip` на блоке `@value` запрещён (`error[E002]`).
- Массив без имени модели элемента `(array)@value { ... }` запрещён (`error[E001]`).
- Коллизия явного имени модели с существующей схемой вызывает `error[E001]`.

### Вложенные инлайн-схемы (Inline JSON Schemas)

Компилятор автоматически выполняет хоистинг инлайн-блоков перед родительской схемой:
- Анонимные блоки `material_data { ... }` → синтезируют имя `{Parent}{Field}` в PascalCase (`ApiResponseMaterialDataJson`).
- Явно именованные блоки `franchise Franchise { ... }` → генерируют `FranchiseJson`.
- Именованные массивы `nodes (array)Node { ... }` → генерируют `NodeJson`.
- Блоки значений словарей `@value ModelName { ... }` / `@value { ... }` → синтезируют `{DictName}Value` / `{Parent}{Field}Value` / `{DictSchema}Value`.
- Поддерживают модификаторы `from="..."`, `@omitempty`, `?` (nullable).

### Переиспользование полей через define

Если несколько `json` схем делят одинаковый набор полей, их можно вынести в
блочный `define` и подключить по имени (без аргументов):

```kdl
define ITEM-CORE {
    id int
    name str
    created_at str
}

json Item {
    ITEM-CORE
    description str?
}

json ItemDetail {
    ITEM-CORE
    description str?
    tags (array)str
}
```

Разрешение контекстное: одни и те же дочерние узлы `define` в pipeline
(struct-поля) раскрываются как операции, в `json` — как поля.
Имя без аргументов (`ITEM-CORE`) — это define-ссылка.
Обычное поле всегда имеет аргумент-тип (`name str`), поэтому конфликта нет.

**Когда использовать:** ≥3 json-схем с ≥4 общими полями.
**Максимальный размер тела define:** 30 полей.

### Alias ключей и GJSON-пути (`from="..."`, `E403`, `E040`)

Имена полей в `json` схемах проверяются линтером (`E403`): каноническое имя поля (после удаления `?`) должно соответствовать `^[A-Za-z_][A-Za-z0-9_]*$` (`snake_case` или `camelCase`; `kebab-case` в полях `json` запрещён) и не совпадать с зарезервированными словами целевых языков.
- Частая опечатка: `url: str` с двоеточием отклоняется `E403` (в KDL имя поля и тип разделяются пробелом: `url str`).
- Ключи с дефисами или спецсимволами (`track-id`, `@context`, `@type`, `$id`, `os.version`) требуют валидного имени поля с `_` и атрибута `from="..."`:

```kdl
json Schema {
    track_id str from="track-id"
    context str from="@context"
    os_version str from="os\\.version"
    author_name str from="data.authors.0.name"
    items_count int from="items.#"
    tag_names (array)str from="tags.#.name"
}
```

Поддерживаемый GJSON-подмножество путей в `from="..."` и `jsonify path="..."` (валидируется `E040`):
- Сегменты ключей объектов (`user.profile.name`).
- Экранирование буквальной точки `\.` и обратной косой черты `\\` внутри ключа (`from="os\\.version"` читает плоский ключ `"os.version"`).
- Неотрицательные целочисленные индексы массивов (`0`, `1`, ...).
- Длина массива на конце пути (`items.#` → `int`).
- Проекция элементов массива (`tags.#.name` → извлекает `name` из каждого элемента массива `tags` в `(array)str` без промежуточной `json` схемы).

(Устаревший позиционный синтаксис `context str "@context"` вызывает предупреждение `W011`; синоним `path="..."` на поле вызывает `W041`).

### Кодогенерация JSON Projectors

В Python (`_project_<schema>`) и JavaScript (`_project<Schema>`), как и в Go (`UnmarshalJSON`) и Rust (`from_value`), для каждой `json` схемы генерируется отдельная функция-проектор:
- Проверяет тип входного контейнера (`dict` для объекта/словаря, `list` для `(array)json`), выбрасывая `SscJsonSchemaError` при `null` или примитивах.
- Для плоских ключей выполняет прямое `O(1)` чтение из словаря, а для многосегментных путей и `#` вызывает встроенный GJSON микро-интерпретатор.
- Включает квалифицированный контекст `<SchemaName>.<field_name>` в сообщения `SscJsonFieldMissingError`, `SscJsonPathError` и `SscJsonSchemaError`.

## Автоматическая генерация схем из JSON (`ssc-gen json-to-kdl`)

CLI-команда `json-to-kdl` позволяет автоматически создать `.kdl` схему из примера JSON-ответа:

```bash
ssc-gen json-to-kdl example.json -o schema.kdl
ssc-gen json-to-kdl example.json -o schema.kdl --name ApiResponse --force
```

- Генерирует единую иерархическую инлайн-схему с анонимными объектами `field { ... }` и массивами `items (array)ItemsItem { ... }`.
- Автоматически назначает `from="<raw_key>"` для нестандартных имён ключей.
- Рекурсивно объединяет множественные примеры объектов в массивах и проставляет `@omitempty` для частичных полей.
- Валидирует сгенерированный KDL через `parse_module` перед записью на диск.

## Использование `jsonify`

```kdl
struct Main {
    @init {
        raw-json { raw; re JSON-PATTERN }
    }

    all-quotes { @raw-json; jsonify Quote }
    first-author { @raw-json; jsonify Author path="0.author" }
    second-author { @raw-json; jsonify Author path="1.author" }
}
```

`jsonify` принимает один обязательный аргумент — имя целевой `json` схемы, в которую проецируется выбранный по `path` JSON-фрагмент.

### path навигация

`path` использует тот же GJSON-синтаксис (`E040`) для выбора JSON-фрагмента перед вызовом проектора схемы:

- `""` — применить схему к результату целиком
- `"0"` — индекс массива (выбранный элемент должен соответствовать целевой схеме)
- `"0.author"` — вложенный путь до объекта `Author`
- `"props.pageProps.results"` — путь внутри Next.js/SPA гидратации

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
