# 08. Transform и DSL

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

Extensions — продвинутая фича, когда стандартных операций не хватает и нужна
специфичная трансформация данных.

Два способа добавить пользовательский код:

- `transform` — мультиязычная операция.
- `dsl` — короткий блок для одного языка.

## Transform

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

struct Main {
    titleb64 { css "title"; text; transform to-base64 }
}
```

Правила:
- `accept` и `return` обязательны.
- `accept` и `return` не могут быть `AUTO`/`LIST_AUTO`.
- `import` опционален и нужен только если есть зависимости.
- Используйте `{{PRV}}` и `{{NXT}}` в `code`.

Допустимые типы `accept`/`return`:

`DOCUMENT`, `LIST_DOCUMENT`, `STRING`, `LIST_STRING`, `INT`, `LIST_INT`,
`FLOAT`, `LIST_FLOAT`, `BOOL`, `NULL`, `OPT_STRING`, `OPT_INT`, `OPT_FLOAT`.

## DSL

```kdl
dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

struct Main {
    title { css "title"; text; expr upper-py }
}
```

Правила:
- `lang` обязателен.
- `accept`/`return` опциональны, но ограничены допустимыми типами.
- Внутри `dsl` разрешены только `import` и `code`.
- `import` опционален и нужен только если есть зависимости.
- Используйте `{{PRV}}` и `{{NXT}}` в `code`.

## Маркеры `{{PRV}}` и `{{NXT}}`

- `{{PRV}}` — значение на входе операции.
- `{{NXT}}` — переменная для результата.
