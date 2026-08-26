# Быстрый старт

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-07-21

Этот документ показывает минимальный рабочий путь от `.kdl` файла до
сгенерированного парсера.

## Установка

```bash
uv tool install ssc_codegen
```

Или из git (для разработки):

```bash
uv tool install git+https://github.com/vypivshiy/selector_schema_codegen
```

## Минимальный пример

`simple.kdl`:

```kdl
struct Simple {
    title { css "title"; text }
}
```

Генерация:

```bash
ssc-gen generate python simple.kdl -L bs4
```

Проверка (линтер):

```bash
ssc-gen check simple.kdl
```

## Пример со списком

```kdl
(list)struct Book {
    @split-doc { css-all ".book" }
    title { css ".title"; text; trim }
    price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
}
```

## Пример: парсинг простого текста (raw)

Для документов без HTML (JS-файлы, URL, текстовые данные):

```kdl
(raw)struct PlayerScript {
    playlist_url { re #"file:\s*[\"']([^\"']+)[\"']"#
}
```

Документ — строка, HTML-операции запрещены. См. [syntax.md](syntax.md#rawstruct--парсинг-простого-текста).

## Генерация с помощью LLM

LLM-агент (Claude, ChatGPT и др.) может генерировать и отлаживать `.kdl` схемы
автоматически. Для этого:

1. **Передайте HTML-страницу или описание API** и опишите, какие данные нужно извлечь.
2. LLM сгенерирует `.kdl` файл.
3. **Прогоните линтер** для валидации:
   ```bash
   ssc-gen check schema.kdl -f json
   ```
4. Если есть ошибки — передайте JSON-вывод обратно LLM, он исправит.
5. Повторяйте до чистого прохода линтера.
6. **Сгенерируйте код** парсера:
   ```bash
   ssc-gen generate python schema.kdl -L bs4
   ```

Проект работает через связку `agents + skills`. В IDE с поддержкой агентов
(Claude Code, Cursor, opencode и т.д.) этот цикл может быть автоматизирован
через skills из `.agents/skills/`:
`sscgen-dsl` (HTML scraping) and `sscgen-rest` (REST API). OpenAPI/Swagger can
serve as external API contract information, but CLI does not convert it
automatically; describe resulting KDL manually with `sscgen-rest`.

## Где смотреть живые примеры

См. каталог `examples/` в репозитории:
- `booksToScrape.kdl` — HTML-скрапинг (list)
- `quotesToScrape.kdl` — HTML-скрапинг (flat)
- `rawParser.kdl` — парсинг простого текста (raw struct)
- `restApiLike.kdl` — REST API клиент

Они отражают актуальные возможности реализации.
