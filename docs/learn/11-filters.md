# 11. Filter (фильтрация списков)

**Версия DSL:** 2.1
**Последнее обновление:** 2026-05-10

`filter { ... }` — операция pipeline, которая **отфильтровывает** список,
оставляя только элементы, подходящие под предикат.

Работает только с **LIST_DOCUMENT** и **LIST_STRING** — типами,
которые создаются операциями `css-all`, `xpath-all` или `split`.

```kdl
links { css-all "a"; filter { attr-eq "data-kind" "nav" }; attr "href" }
```

## Синтаксис

```kdl
field { css-all "selector"; filter { предикаты }; ... }
```

Предикаты внутри filter пишутся через `;` — это **И**
(элемент должен подходить под все). Для комбинирования используйте
логические операторы `not`, `and`, `or`.

## Предикаты

| Предикат | Описание | Пример |
|---|---|---|
| `eq <value...>` | равен любому из | `eq "active"` |
| `ne <value...>` | не равен ни одному | `ne "" "null"` |
| `starts <value...>` | начинается с | `starts "https://"` |
| `ends <value...>` | заканчивается на | `ends ".html"` |
| `contains <value...>` | содержит | `contains "price"` |
| `in <value...>` | равен одному из | `in "nav" "cta"` |
| `re <pattern>` | соответствует regex | `re #"^\d+$"#` |
| `css <sel>` | дочерний элемент существует | `css ".icon"` |
| `xpath <sel>` | дочерний элемент существует | `xpath "//span"` |
| `has-attr <name...>` | элемент имеет атрибут | `has-attr "href"` |
| `attr-eq <attr> <val...>` | атрибут равен | `attr-eq "class" "active"` |
| `attr-ne <attr> <val...>` | атрибут не равен | `attr-ne "rel" "nofollow"` |
| `attr-contains <attr> <val...>` | атрибут содержит | `attr-contains "class" "btn"` |
| `attr-starts <attr> <val...>` | атрибут начинается с | `attr-starts "href" "/"` |
| `attr-ends <attr> <val...>` | атрибут заканчивается на | `attr-ends "href" ".html"` |
| `attr-re <attr> <pattern>` | атрибут по regex | `attr-re "href" #"^https?://"#` |
| `text-contains <val...>` | текст элемента содержит | `text-contains "docs"` |
| `text-starts <val...>` | текст элемента начинается с | `text-starts "Go"` |
| `text-ends <val...>` | текст элемента заканчивается на | `text-ends "more"` |
| `text-re <pattern>` | текст элемента по regex | `text-re #"guide|docs"#` |
| `not { ... }` | отрицание | `not { eq "hidden" }` |
| `and { ... }` | конъюнкция | `and { starts "a"; ends "z" }` |
| `or { ... }` | дизъюнкция | `or { eq "a"; eq "b" }` |

Дополнительные предикаты (`len-*`, `re-any`, `re-all`, `gt/lt/ge/le`)
доступны только в `assert` — см. [12-asserts.md](12-asserts.md).

## Примеры

### Фильтрация по значению

```kdl
define RE-CODE=#"^code"#

(list)struct Example {
    @split-doc { css-all ".item" }
    codes {
        css ".code"
        text
        split ","
        filter { re RE-CODE }
    }
}
```

Python:

```python
v1 = [el.get_text() for el in el.select_all(".code")]
v2 = []
for v0 in v1:
    v2.extend(v0.split(","))
v3 = [i for i in v2 if re.search(r"^code", i)]
```

JS:

```js
let v1 = [...el.querySelectorAll(".code")].map(e => e.textContent);
let v2 = v1.flatMap(v0 => v0.split(","));
let v3 = v2.filter(i => (new RegExp("^code").test(i)));
```

### Фильтрация элементов по атрибутам

```kdl
define CSS-LINK="a[href]"
define RE-HREF=#"https?://|/"#

(list)struct Links {
    @split-doc { css-all ".card" }
    nav-links {
        css-all CSS-LINK
        filter {
            css ".icon"
            has-attr "href" "data-kind"
            attr-eq "data-kind" "nav" "cta"
            attr-ne "rel" "nofollow" "sponsored"
            attr-starts "href" "/" "https://"
            attr-ends "href" ".html" "/"
            attr-re "href" RE-HREF
        }
        attr "href"
    }
}
```

Python:

```python
v1 = [el for el in el.select_all("a[href]")]
v2 = [i for i in v1 if
    i.select_one(".icon")
    and any(hasattr(i, n) and i[n] is not None for n in ("href", "data-kind"))
    and i.get("data-kind") in ("nav", "cta")
    and i.get("rel") not in ("nofollow", "sponsored")
    and any(i.get("href", "").startswith(p) for p in ("/", "https://"))
    and any(i.get("href", "").endswith(p) for p in (".html", "/"))
    and re.search(r"https?://|/", i.get("href", ""))
]
v3 = [i.get("href") for i in v2]
```

JS:

```js
let v1 = [...el.querySelectorAll("a[href]")];
let v2 = v1.filter(i => (
    i.querySelector(".icon") !== null
    && ["href", "data-kind"].some(n => i.hasAttribute(n))
    && ["nav", "cta"].includes(i.getAttribute("data-kind"))
    && !["nofollow", "sponsored"].includes(i.getAttribute("rel"))
    && ["/", "https://"].some(p => i.getAttribute("href").startsWith(p))
    && [".html", "/"].some(p => i.getAttribute("href").endsWith(p))
    && new RegExp("https?://|/").test(i.getAttribute("href"))
));
let v3 = v2.map(i => i.getAttribute("href"));
```

### Фильтрация с логическими операторами

```kdl
(list)struct Data {
    @split-doc { css-all ".row" }
    active {
        css-all ".tag"
        text
        filter {
            not { eq "deprecated" }
            or { starts "new-"; contains "beta" }
        }
    }
}
```

Python:

```python
v1 = [el.get_text() for el in el.select_all(".tag")]
v2 = [i for i in v1 if
    not (i == "deprecated")
    and ("new-" in i or "beta" in i)
]
```

### filter + fallback {}

Если после фильтрации список может оказаться пустым —
используйте `fallback {}`:

```kdl
tags { css-all ".tag"; text; filter { ne "" }; fallback {} }
```

## Filter vs assert

| | filter | assert |
|---|---|---|
| Действие | убирает неподходящие элементы | бросает ошибку при неудаче |
| Типы данных | LIST_DOCUMENT, LIST_STRING | любой |
| Pass-through | нет (список фильтруется) | да (вход == выход) |
| Уникальные предикаты | — | `len-*`, `re-any`, `re-all`, `gt/lt/ge/le` |

Подробнее про assert см. в [12-asserts.md](12-asserts.md).
