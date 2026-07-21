# 07. Define (переиспользование)

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-07-21

`define` помогает переиспользовать значения и блоки операций. Логика как в C:
это текстовая подстановка значений или операций.

## Именование

Имя define **обязательно** в UPPER_CASE: `[A-Z_][A-Z0-9_-]*`.

```kdl
define BASE-URL="https://example.com"     // OK
define REQUEST-SEARCH="curl ..."           // OK
define my-var="value"                      // ОШИБКА: lowercase
define MyVar="value"                       // ОШИБКА: mixedCase
```

## Скалярные define

**Скалярный define** — это значение. Используется только как аргумент.
Это подстановка строки/числа/regex в место аргумента.

Использование:

```kdl
define BASE-URL="https://books.toscrape.com/catalogue/{{}}"
define RE-PRICE=#"(\d+\.\d+)"#

struct Book {
    link { css "a"; attr "href"; fmt BASE-URL }
    price { css ".price_color"; text; re RE-PRICE; to-float }
}
```

Правило: скалярный `define` нельзя использовать как pipeline-операцию.

## Подстановка define в define

В значении скалярного define можно ссылаться на другой define через `{{NAME}}`:

```kdl
define BASE-URL="https://example.com"
define API-URL="{{BASE-URL}}/api/v1"
```

Синтаксис `{{NAME}}` — это подстановка UPPER_CASE define-значений.
Lowercase `{{name}}` **не разрешается** и передаётся как есть — это placeholder для `@request`
(см. [10-request.md](10-request.md)).

## Блочные define

**Блочный define** — это набор операций. Используется как выражение в pipeline.
Это подстановка блока операций в место вызова.

Пример:

```kdl
define EXTRACT-HREF {
    css "a"
    attr "href"
}

struct Links {
    first { EXTRACT-HREF; first }
}
```

## Когда использовать

- общий селектор/шаблон (`fmt`, `re`);
- повторяющиеся блоки операций;
- библиотека общих define в отдельном файле + `import`.

Подробнее про импорты см. в [09-imports.md](09-imports.md).

## Блочные define в json

Блочный define можно использовать не только в pipeline, но и внутри `json { ... }`.
Если json-блок содержит имя define без аргументов — дочерние узлы подставляются как json-поля:

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

Разрешение контекстное: одни и те же дочерние узлы define в pipeline раскрываются как операции, в json — как поля.
Имя без аргументов (`ITEM-CORE`) — это define-ссылка. Обычное поле всегда имеет аргумент-тип (`name str`), поэтому конфликта нет.
