# 07. Define (переиспользование)

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

`define` помогает переиспользовать значения и блоки операций. Логика как в C:
это текстовая подстановка значений или операций.

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
