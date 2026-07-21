# 04. Запуск на локальном HTML (`ssc-gen run`)

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-07-21

`ssc-gen run` позволяет прогнать схему сразу на HTML и получить результат.

## Пример с файлом

```bash
ssc-gen run examples/booksToScrape.kdl:MainCatalogue -l python -L bs4 -i page.html
```

Где:
- `MainCatalogue` — имя `struct`, точка входа.
- `-i` — локальный HTML файл.

## Пример со stdin

```bash
curl "https://books.toscrape.com" | ssc-gen run examples/booksToScrape.kdl:MainCatalogue
```

Это удобно для быстрого теста схемы без сохранения HTML.
