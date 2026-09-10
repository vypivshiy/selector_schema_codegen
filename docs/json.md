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
