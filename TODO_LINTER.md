# TODO: Linter & LSP improvements

## 1. Улучшение ошибок линтера

### 1.1 "Did you mean?" для опечаток

- [ ] Добавить fuzzy-matching (difflib.get_close_matches) в `rules_struct.py` — wildcard rule для unknown operations
- [ ] Предлагать ближайшие совпадения из: встроенные операции, define, dsl-блоки, transform
- [ ] Порог: расстояние Левенштейна ≤ 2 или ratio ≥ 0.6

```
error[E200]: unknown operation 'csss'
  --> schema.kdl:5:5
    |
  5 |     csss ".item"
    |     ^^^^ unknown operation
    |
    = help: did you mean 'css' or 'css-all'?
```

### 1.2 Type mismatch: показывать pipeline trace

- [ ] В `type_rules.py` при ошибке типа собирать историю типов пайплайна
- [ ] Показывать цепочку преобразований до точки ошибки в `notes=`

```
error[E100]: 'trim' expects STRING or LIST_STRING, got DOCUMENT
  --> schema.kdl:8:5
    |
  8 |     trim
    |     ^^^^ type mismatch
    |
    = pipeline: css ".item" → DOCUMENT
                trim        → ✗ (expects STRING)
    = help: add 'text' before 'trim' to extract text content
```

### 1.3 Type mismatch: предлагать операции-мосты

- [ ] Расширить `_type_mismatch_hint()` в `type_rules.py`
- [ ] Таблица "мостов" между типами:
  - DOCUMENT → STRING: `text`, `raw`, `attr "..."`
  - DOCUMENT → LIST_DOCUMENT: `css-all "..."`, `xpath-all "..."`
  - LIST_DOCUMENT → LIST_STRING: `text`, `raw`, `attr "..."`
  - LIST_* → scalar: `index N`, `first`, `last`
  - STRING → LIST_STRING: `split "..."`, `re-all "..."`
  - LIST_STRING → STRING: `join "..."`, `index N`, `first`

### 1.4 Контекстные подсказки для struct type

- [ ] При E401 (missing special field) показывать минимальный шаблон структуры

```
error[E401]: struct type=dict requires '@key' and '@value' fields
  --> schema.kdl:3:1
    |
  3 | struct Meta type=dict {
    | ^^^^^^ missing required fields
    |
    = help: add required fields:
        @split-doc { css-all "..." }
        @key { attr "property" }
        @value { attr "content" }
```

### 1.5 Предупреждения о потенциальных проблемах

- [ ] Пустой `fallback ""` после `to-int` / `to-float` — вероятно ошибка (тип не совпадает)
- [ ] `css-all` + `index 0` — предложить `css` вместо
- [ ] `re-all` + `first` — предложить `re` вместо
- [ ] Дублирующиеся операции подряд (`trim; trim`)

---

## 2. LSP-сервер

### 2.1 Инфраструктура

- [ ] Добавить зависимость `pygls` (Python LSP framework)
- [ ] Создать `ssc_codegen/lsp/` пакет
- [ ] Точка входа: `ssc_codegen/lsp/server.py`
- [ ] CLI: `ssc-lsp` или `python -m ssc_codegen.lsp`

### 2.2 Diagnostics (приоритет 1)

- [ ] Маппинг `LintError` → LSP `Diagnostic` (line/col/end_line/end_col уже есть)
- [ ] Линтинг при сохранении файла (`textDocument/didSave`)
- [ ] Линтинг при изменении (`textDocument/didChange`) с debounce
- [ ] Severity mapping: `error` → DiagnosticSeverity.Error, `warning` → DiagnosticSeverity.Warning

### 2.3 Hover (приоритет 2)

- [ ] Показывать тип на текущем шаге пайплайна: `STRING → LIST_STRING`
- [ ] Для операций: краткое описание + сигнатура (accept → return)
- [ ] Для `define` / `transform`: показывать определение
- [ ] Для `@init`-полей: показывать pipeline и выведенный тип

### 2.4 Autocomplete (приоритет 2)

- [ ] Операции, допустимые для текущего типа в пайплайне
  - После `css` (DOCUMENT): `text`, `raw`, `attr`, `css`, `css-all`, `css-remove`, `assert`, `nested`...
  - После `text` (STRING): `trim`, `lower`, `upper`, `re`, `split`, `fmt`, `to-int`...
  - После `css-all` (LIST_DOCUMENT): `text`, `attr`, `filter`, `index`, `first`...
- [ ] Имена `define`, `transform`, `@init`-полей
- [ ] Сниппеты для struct type (`type=list` → вставить `@split-doc {}`)
- [ ] Предикаты внутри `filter {}` / `assert {}`

### 2.5 Go to Definition (приоритет 3)

- [ ] `define NAME` → переход к объявлению
- [ ] `transform NAME` → переход к объявлению
- [ ] `nested StructName` → переход к struct
- [ ] `self field` / `@field` → переход к `@init` полю
- [ ] `import "file.kdl"` → открыть файл

### 2.6 Document Symbols (приоритет 3)

- [ ] `struct` → Class symbol
- [ ] Поля struct → Field symbols
- [ ] `define` → Constant symbol
- [ ] `transform` / `dsl` → Function symbol
- [ ] `json` → Interface symbol

### 2.7 Rename / References (приоритет 4)

- [ ] Rename `define` / `transform` / struct — обновить все ссылки
- [ ] Find references для `define`, `transform`, `@init`-полей

---

## 3. IDE-плагины

### 3.1 VS Code extension (приоритет 1)

- [ ] Language configuration: `.kdl` file association (scope: ssc-kdl)
- [ ] TextMate grammar для подсветки синтаксиса KDL + DSL-ключевых слов
- [ ] Запуск LSP-сервера
- [ ] Сниппеты: `struct`, `define`, `transform`, `@split-doc`, `fallback`

### 3.2 JetBrains plugin (приоритет 4)

- [ ] LSP-клиент через LSP API (IntelliJ 2023.2+)
- [ ] Или TextMate bundle для базовой подсветки
