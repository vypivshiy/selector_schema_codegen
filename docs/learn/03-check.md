# 03. Валидация схемы (`ssc-gen check`)

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-04-07

`ssc-gen check` проверяет синтаксис и типы pipeline до запуска.

## Пример

```bash
ssc-gen check examples/booksToScrape.kdl
```

## Что проверяется

- корректность синтаксиса KDL;
- аргументы операций (`css`, `attr`, `re`, и т.д.);
- совместимость типов между операциями;
- обязательные поля для типов структур.

## Зачем это нужно

Ошибки обнаруживаются до генерации/запуска. Это быстрее и надежнее, чем ловить
исключения в runtime.

## Пример

```kdl
// error-sc.kdl
struct Failed {
    // magic field err
    @split-doc { css-all div }
    // type error
    price { css ".price"; to-float }
    default-err { css "a"; text; fallback 100 }
    // expr syntax error
    expr-err { csss ".foo"; raw }
}
```

```bash
ssc-gen check error-sc.kdl
```

out:

```
error[E001]: '@split-doc' is not allowed in struct type='item'
  --> error_sc.kdl:3:5
  |
2 |     // magic field err
3 |     @split-doc { css-all div }
  |     ^^^^^^^^^^ missing argument
4 |     // type error
  |
  = scope: struct > struct Failed
  = help: '@split-doc' is only valid in: dict, list

error[E100]: 'to-float' does not accept DOCUMENT; expected STRING | LIST_STRING
  --> error_sc.kdl:5:11
  |
4 |     // type error
5 |     price { css ".price"; to-float }
  |           ^ type mismatch
6 |     default-err { css "a"; text; fallback 100 }
  |
  = scope: struct > struct Failed > price
  = help: add 'text', 'raw', or 'attr' before this operation to extract a string

error[E100]: 'fallback' value type INT does not match pipeline type STRING
  --> error_sc.kdl:6:17
  |
5 |     price { css ".price"; to-float }
6 |     default-err { css "a"; text; fallback 100 }
  |                 ^ type mismatch
7 |     // expr syntax error
  |
  = scope: struct > struct Failed > default-err
  = help: use a string literal, or #null to make the field optional

error[E200]: unknown operation 'csss'
  --> error_sc.kdl:8:16
  |
7 |     // expr syntax error
8 |     expr-err { csss ".foo"; raw }
  |                ^^^^ unknown operation
9 | }
  |
  = scope: struct > expr-err > csss
  = help: check spelling or declare it: define csss { ... }

Lint failed: 4 errors

Found 4 error(s) in 1 file(s).
```

or unvalid kdl syntax:

```kdl
struct a {
    foo {
}
```

```
error[E000]: invalid KDL syntax: unexpected end of input
  --> error_sc.kdl:2:1
  |
1 | 
2 | struct a {
  | ^^^^^^ unexpected end of input
3 |     foo {
  |
  = scope: syntax
  = help: close all opened strings, braces, and blocks before semantic linting
  = note: parser could not recover from: struct a {\n foo {\n}

Lint failed: 1 error

Found 1 error(s) in 1 file(s).
```