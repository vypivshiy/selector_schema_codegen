# Transforms и `dsl`

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Два способа добавить пользовательский код:

- `transform` — мультиязычная трансформация.
- `dsl` — короткий однозадачный блок для одного языка.

## transform

```kdl
transform to-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = str(b64decode({{PRV}}))"
    }
    js {
        code "const {{NXT}} = btoa({{PRV}});"
    }
}
```

Правила:
- `accept` и `return` обязательны.
- `accept` и `return` не могут быть `AUTO` или `LIST_AUTO`.
- Блоки языков содержат `import` и `code` строки.
- Используйте маркеры `{{PRV}}` (вход) и `{{NXT}}` (выход).

Вызов в pipeline:

```kdl
title {
    css "title"
    text
    transform to-base64
}
```

## dsl

```kdl
dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}
```

Правила:
- `lang` обязателен.
- `accept` и `return` опциональны, но ограничены набором типов.
- Внутри блока разрешены только `import` и `code`.
- Используйте маркеры `{{PRV}}` и `{{NXT}}` в `code`.

Вызов через `expr`:

```kdl
title {
    css "title"
    text
    expr upper-py
}
```

## expr

`expr` может ссылаться на:
- `dsl` блок;
- блочный `define` (эквивалентно явному вызову define).

Скалярные `define` нельзя использовать в `expr`.
