# Конвертеры: как писать новый backend

**Назначение:** архитектура и контракт конвертера  
**Последнее обновление:** 2026-04-07

Конвертер принимает AST (`ssc_codegen.kdl.parser`) и генерирует исходный код
для целевого runtime.

## Основной контракт

```
KDL schema -> AST -> converter -> generated source code
```

Конвертер отвечает за:
- модули и импорты;
- объявления типов и структур;
- реализацию pipeline операций;
- вызовы nested/jsonify/transform;
- интеграцию с runtime DOM API.

Конвертер не отвечает за:
- парсинг KDL;
- семантическую валидацию;
- вывод типов и линтинг.

## Базовые классы

Код расположен в:
- `ssc_codegen/kdl/converters/base.py`
- `ssc_codegen/kdl/converters/helpers.py`

Ключевые типы:
- `BaseConverter`
- `ConverterContext`

## Модель обхода

Типы узлов, которые различает конвертер:

- Контейнеры: JSON defs, structs, init, typedefs. Обход идет глубже, pipeline индекс сбрасывается.
- Pipeline узлы: Field, InitField, SplitDoc, Key, Value, Table* поля. Обработчик должен вызвать `_emit_pipeline(...)`.
- Предикаты: Filter/Assert/Match и логические контейнеры.

## ConverterContext

`ConverterContext` управляет текущими именами переменных и отступами:
- `ctx.prv` — входное значение pipeline.
- `ctx.nxt` — выходное значение pipeline.
- `ctx.indent` — текущий отступ.

Индекс pipeline увеличивается после каждого выражения.
