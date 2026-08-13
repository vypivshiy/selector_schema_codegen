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
- Поля могут ссылаться на другие `json` схемы по имени.

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

Если ключ в JSON неудобен как имя поля, можно задать alias:

```kdl
json Schema {
    context str "@context"
}
```

`context` — имя поля в схеме, `@context` — реальный ключ в JSON.

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
