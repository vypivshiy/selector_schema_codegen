# Быстрый старт

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Этот документ показывает минимальный рабочий путь от `.kdl` файла до
сгенерированного парсера.

## Установка

```bash
uv tool install git+https://github.com/vypivshiy/selector_schema_codegen@features-kdl
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
ssc-gen generate simple.kdl -t py-bs4
```

Проверка (линтер):

```bash
ssc-gen check simple.kdl
```

## Пример со списком

```kdl
struct Book type=list {
    @split-doc { css-all ".book" }
    title { css ".title"; text; trim }
    price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
}
```

## Генерация с помощью LLM

LLM-агент (Claude, ChatGPT и др.) может генерировать и отлаживать `.kdl` схемы
автоматически. Для этого:

1. **Скормите LLM системный промпт** из `SYSTEM_PROMPT.md` (или `docs2/llm.txt`
   как компактную альтернативу).
2. **Передайте HTML-страницу** и опишите, какие данные нужно извлечь.
3. LLM сгенерирует `.kdl` файл.
4. **Прогоните линтер** для валидации:
   ```bash
   ssc-gen check schema.kdl -f json
   ```
5. Если есть ошибки — передайте JSON-вывод обратно LLM, он исправит.
6. Повторяйте до чистого прохода линтера.
7. **Сгенерируйте код** парсера:
   ```bash
   ssc-gen generate schema.kdl -t py-bs4
   ```

В IDE с поддержкой агентов (Claude Code, Cursor и т.д.) этот цикл может быть
полностью автоматизирован через skill `.agents/skills/kdl-schema-dsl`.

## Где смотреть живые примеры

См. каталог `examples/` в репозитории:
- `booksToScrape.kdl`
- `quotesToScrape.kdl`
- `transformExample.kdl`

Они отражают актуальные возможности реализации.
