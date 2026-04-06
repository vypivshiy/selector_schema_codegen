# Линтер: как добавлять правила

**Аудитория:** мейнтейнеры  
**Последнее обновление:** 2026-04-07

Этот документ описывает, где и как добавлять встроенные правила линтера.
Это не пользовательское расширение.

## Где находится код

Каталог: `ssc_codegen/linter/`

Ключевые файлы:
- `__init__.py` — публичный API, импорт правил.
- `_kdl_lang.py` — tree-sitter loader.
- `base.py` — AstLinter, контексты, обход.
- `rules.py` — аргументы и синтаксис операций.
- `rules_struct.py` — правила структур и модульного уровня.
- `rule_keywords.py` — `dsl`, `expr`, `define`.
- `type_rules.py` — вывод типов и проверки совместимости.
- `types.py` — ошибки, коды, структуры метаданных.

## Модель выполнения

1. Парсинг и проверка синтаксиса tree-sitter.
2. Сбор метаданных (`define`, `transform`, `dsl`, `json`, `struct`).
3. Обход CST с применением правил по контексту.
4. Отдельная фаза типизации pipeline.

## Где размещать правило

- `rules.py` — локальные проверки операций и аргументов.
- `rules_struct.py` — правила структуры модуля и struct.
- `rule_keywords.py` — ключевые слова DSL (`dsl`, `expr`, `define`).
- `type_rules.py` — типы и проверка цепочек.

## Регистрация правила

```python
@LINTER.rule("css", "css-all")
def rule_css_like(node, ctx):
    ...
```

Замена существующего:

```python
@LINTER.rule("css", replace=True)
def rule_css_override(node, ctx):
    ...
```

## Диагностики

```python
ctx.error(
    node,
    code=ErrorCode.MISSING_ARGUMENT,
    message="'css' requires one argument",
    hint='example: css ".item"',
)
```

## Полезные утилиты контекста

`ctx.get_args(node)`, `ctx.get_prop(node, "key")`, `ctx.get_children_nodes(node)`,
`ctx.has_empty_block(node)`, `ctx.current_path`.
