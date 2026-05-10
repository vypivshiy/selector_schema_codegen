# 12. Assert (валидация)

**Версия DSL:** 2.1
**Последнее обновление:** 2026-05-10

`assert { ... }` — операция pipeline, которая **проверяет** текущее значение
без его изменения. Если предикат не выполняется — бросается ошибка.
Это pass-through: тип на входе совпадает с типом на выходе.

```kdl
price { css ".price"; text; to-float; assert { gt 0 } }
```

## Синтаксис

```kdl
# в pipeline поля
field { ...; assert { предикаты }; ... }

# в @pre-validate (проверка документа перед парсингом)
struct Foo {
    @pre-validate {
        assert { css ".main-content" }
    }
}
```

Предикаты внутри assert пишутся через `;` (точку с запятой) — это **И**
(все должны выполняться). Для комбинирования используйте логические
операторы `not`, `and`, `or`.

## Предикаты

Assert поддерживает все предикаты из filter, плюс дополнительные,
доступные только внутри assert.

### Общие (filter + assert)

| Предикат | Описание | Пример |
|---|---|---|
| `eq <value...>` | равно любому из | `eq "foo" "bar"` |
| `ne <value...>` | не равно ни одному | `ne "" "null"` |
| `starts <value...>` | начинается с | `starts "https://"` |
| `ends <value...>` | заканчивается на | `ends ".html"` |
| `contains <value...>` | содержит | `contains "price"` |
| `in <value...>` | равен одному из | `in "code-4" "code-8"` |
| `re <pattern>` | соответствует regex | `re #"\d+\.\d+"#` |
| `css <sel>` | дочерний элемент существует | `css ".title"` |
| `xpath <sel>` | дочерний элемент существует | `xpath "//h1"` |
| `has-attr <name...>` | элемент имеет атрибут | `has-attr "href"` |
| `attr-eq <attr> <val...>` | атрибут равен | `attr-eq "class" "active"` |
| `attr-ne <attr> <val...>` | атрибут не равен | `attr-ne "class" "hidden"` |
| `attr-contains <attr> <val...>` | атрибут содержит | `attr-contains "class" "btn"` |
| `attr-starts <attr> <val...>` | атрибут начинается с | `attr-starts "href" "/api/"` |
| `attr-ends <attr> <val...>` | атрибут заканчивается на | `attr-ends "href" ".pdf"` |
| `attr-re <attr> <pattern>` | атрибут по regex | `attr-re "id" #"row-\d+"#` |
| `text-contains <val...>` | текст элемента содержит | `text-contains "price"` |
| `text-starts <val...>` | текст элемента начинается с | `text-starts "$"` |
| `text-ends <val...>` | текст элемента заканчивается на | `text-ends "USD"` |
| `text-re <pattern>` | текст элемента по regex | `text-re #"\d+"#` |
| `not { ... }` | отрицание | `not { eq "" }` |
| `and { ... }` | конъюнкция | `and { starts "a"; ends "z" }` |
| `or { ... }` | дизъюнкция | `or { eq "a"; eq "b" }` |

### Только в assert

| Предикат | Описание | Пример |
|---|---|---|
| `gt <value>` | строго больше | `gt 0` |
| `lt <value>` | строго меньше | `lt 100` |
| `ge <value>` | больше или равно | `ge 0` |
| `le <value>` | меньше или равно | `le 100` |
| `len-eq <value...>` | длина равна | `len-eq 3` |
| `len-ne <value...>` | длина не равна | `len-ne 0` |
| `len-gt <value>` | длина больше | `len-gt 0` |
| `len-lt <value>` | длина меньше | `len-lt 50` |
| `len-ge <value>` | длина >= | `len-ge 1` |
| `len-le <value>` | длина <= | `len-le 10` |
| `len-range <start> <end>` | длина в диапазоне | `len-range 3 10` |
| `re-any <pattern>` | хотя бы один элемент списка подходит | `re-any #"\d+"#` |
| `re-all <pattern>` | все элементы списка подходят | `re-all #"^[A-Z]"#` |

## Примеры

### Проверка строкового значения

```kdl
define RE-ISBN=#"\d{3}-\d{1,5}-\d{1,7}-\d{1,7}-\d{1}"#

struct Book {
    isbn { css ".isbn"; text; trim; assert { re RE-ISBN } }
}
```

Python:

```python
v1 = el.select_one(".isbn").get_text()
v2 = v1.strip()
i = v2
assert (
    bool(re.search(r"\d{3}-\d{1,5}-\d{1,7}-\d{1,7}-\d{1}", i))
)
v3 = v2  # pass-through, значение не изменилось
```

JS:

```js
let v2 = el.querySelector(".isbn").textContent.trim();
let i = v2;
if (!(new RegExp("\\d{3}-\\d{1,5}-\\d{1,7}-\\d{1,7}-\\d{1}").test(i))) { throw new Error('Assertion failed'); }
let v3 = v2;
```

### Assert + fallback

При неудаче assert бросает ошибку. Если нужен дефолт вместо ошибки —
сочетайте с `fallback`:

```kdl
price { css ".price"; text; to-float; assert { gt 0 }; fallback 0.0 }
```

Если assert не прошёл — fallback перехватывает ошибку и возвращает `0.0`.

### Логические операторы

```kdl
define RE-WORD=#"[a-zA-Z]+"#

struct Logic {
    check {
        css ".logic"
        text
        assert {
            contains "alpha"
            not { eq "forbidden" }
            or { starts "pre"; ends "suf" }
            and { re RE-WORD; contains "a" }
        }
    }
}
```

Все предикаты верхнего уровня объединяются через **И**.
Используйте `or { ... }` и `and { ... }` для явной группировки.

### assert в @pre-validate

`@pre-validate` проверяет документ до начала парсинга.
Внутри можно использовать только предикаты для DOCUMENT
(`css`, `xpath`):

```kdl
struct ProductPage {
    @pre-validate {
        assert { css ".product-card" }
        assert { css ".price" }
    }
    title { css "h1"; text }
}
```

Python:

```python
def _pre_validate(self, v):
    i = v
    assert (
        i.select_one(".product-card") is not None
    )
    i = v
    assert (
        i.select_one(".price") is not None
    )
}
```

### Предикаты для списков

`re-any` и `re-all` работают со списками:
проверяют каждый элемент по regex.

```kdl
tags { css-all ".tag"; text; assert { re-any #"^\d+$" } }
codes { css-all ".code"; text; assert { re-all #"^[A-Z]{2}\d{4}$" } }
```

`len-*` проверяют длину списка:

```kdl
items { css-all ".item"; assert { len-gt 0; len-lt 50 } }
```

## Assert vs filter

| | assert | filter |
|---|---|---|
| Действие | бросает ошибку при неудаче | убирает неподходящие элементы |
| Тип данных | любой (строка, число, список, документ) | только списки |
| Pass-through | да (вход == выход) | нет (список фильтруется) |
| Уникальные предикаты | `len-*`, `re-any`, `re-all`, `gt/lt/ge/le` | — |
| Место в pipeline | любое | любое |
| В @pre-validate | да | нет |
