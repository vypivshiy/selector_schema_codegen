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

### Alias ключей

Если ключ в JSON неудобен как имя поля, можно задать alias через атрибут `from="..."`:

```kdl
json Schema {
    context str from="@context"
}
```

`context` — имя поля в схеме, `@context` — реальный ключ в JSON. (Устаревший позиционный синтаксис `context str "@context"` вызывает предупреждение W011).

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
    first-quote { @raw-json; jsonify Quote path="0" }
    author-slug { @raw-json; jsonify Quote path="2.author.slug" }
}
```

`jsonify` принимает один обязательный аргумент — имя схемы.

### path навигация

`path` позволяет перейти к элементам или полям:

- `""` — применить схему к результату целиком
- `"0"` — индекс массива
- `"field"` — доступ к полю
- `"0.author.slug"` — комбинированный путь

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
