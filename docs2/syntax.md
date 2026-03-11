# KDL Schema DSL — Syntax Reference

## Table of Contents

1. [Module level](#1-module-level)
2. [Structs](#2-structs)
3. [Reserved fields](#3-reserved-fields)
4. [Regular fields](#4-regular-fields)
5. [Pipeline](#5-pipeline)
6. [define](#6-define)
7. [transform](#7-transform)
8. [dsl / expr](#8-dsl--expr)
9. [json mapping](#9-json-mapping)

---

## 1. Module level

| keyword | args | properties | children |
|---------|------|------------|----------|
| `doc` | `text: str` | — | — |
| `define` | — | `NAME=value` | `ops...` (optional) |
| `struct` | `name: str` | `type=item\|list\|dict\|table\|flat` | fields... |
| `json` | `name: str` | `array=#true\|#false` (default `#false`) | fields... |
| `transform` | `name: str` | `accept=TYPE return=TYPE` | lang blocks... |
| `dsl` | `name: str` | `lang=LANG`, `accept=TYPE` (opt), `return=TYPE` (opt) | `import`, `code` |

```kdl
doc "module description"

define FMT_URL="https://example.com/{{}}"
define RE_ID=#"(\d+)"#

struct Book type=list { ... }
json Author { ... }
transform to-base64 accept=STRING return=STRING { ... }
dsl STRIP lang="py" { code "{{NXT}} = {{PRV}}.strip()" }
```

---

## 2. Structs

### Types

| type | description | required reserved fields |
|------|-------------|--------------------------|
| `item` (default) | document → single object | — |
| `list` | document → list of objects | `-split-doc` |
| `dict` | document → key/value pairs | `-key`, `-value` |
| `table` | HTML `<table>` → typed fields by row match | `-table`, `-rows`, `-match`, `-value` |
| `flat` | document → flat deduplicated `LIST_STRING` | — |

### item

```kdl
struct ProductPage {
    title { css "h1"; text }
}
```

### list

```kdl
struct BookList type=list {
    -split-doc { css-all ".item" }
    title { css "h2"; text }
}
```

### dict

`-key` must return `STRING`. `-value` can return any type.

```kdl
struct Meta type=dict {
    -key   { css "th"; text }
    -value { css "td"; text; to-int }   // any ret type allowed
}
```

### table

Each field uses `match { }` to select a row by its key cell value.
`-match` defines how to extract the key string from a row.
`-value` defines how to extract the value string from the matched row.

```kdl
struct ProductInfo type=table {
    -table { css "table.info" }
    -rows   { css-all "tr" }
    -match { css "th"; text; trim }
    -value { css "td"; text; trim }

    upc   { match { eq "UPC" } }
    price { match { starts "Price" }; re RE_PRICE; to-float; fallback 0.0 }
}
```

### flat

All fields must return `LIST_STRING`. Results are merged into a single flat `LIST_STRING`.
Duplicates are removed. Use `keep-order` property to control ordering.

```kdl
struct GitUrls type=flat keep-order=#true {
    github { css-all "a"; attr "href"; filter { contains "github.com" } }
    gitlab { css-all "a"; attr "href"; filter { contains "gitlab.com" } }
}
```

---

## 3. Reserved fields

Start with `-`. Control struct behaviour, not output.

| keyword | args | children result | description | available in |
|---------|------|-----------------|-------------|--------------|
| `-doc` | `text: str` | — | Struct docstring | all |
| `-pre-validate` | — | any | Validate document before parsing. Error if fails. | all |
| `-init` | — | named pipelines | Pre-computed named values, cached before field parsing | all |
| `-split-doc` | — | `LIST_DOCUMENT` | Split document into items | `list` |
| `-key` | — | `STRING` | Key extraction pipeline | `dict` |
| `-value` | — | `AUTO` | Value extraction pipeline (`dict`: any type; `table`: `STRING`) | `dict`, `table` |
| `-table` | — | `DOCUMENT` | Select table element | `table` |
| `-row` | — | `LIST_DOCUMENT` | Select table rows | `table` |
| `-match` | — | `STRING` | Extract key cell text for row matching | `table` |

### -pre-validate

```kdl
-pre-validate { assert { css ".item" } }
```

### -init

Defines named pre-computed values cached before field parsing begins.
Each entry is a named pipeline of any type.
Referenced in fields via `self name` as the first operation.
Resolves statically at AST build time — unknown names are a build-time error.

Execution order in `parse()`: `-pre-validate` → `-split-doc` → `-init` entries → fields.

```kdl
-init {
    hrefs    { css-all "a" }
    raw-urls { raw; re-all #"(https?://[^\s]+)"# }
}
```

Usage in fields:

```kdl
urls {
    self hrefs
    attr "href"
}
git-urls {
    self raw-urls
    filter { contains "github" "gitlab" }
}
```

---

## 4. Regular fields

```kdl
field-name {
    op1
    op2
}
```

Field name becomes the output key. `-` is converted to `_` or camelCase by codegen.

### nested

Passes the current document to another struct parser and returns its result.
Target struct can be of any type.

```kdl
struct Main {
    books { nested BookList }
    meta  { nested MetaTable }
}
```

### self

References a pre-computed value from `-init`. Must be the first operation in the field.

```kdl
git-urls {
    self raw-urls
    filter { contains "github" "gitlab" }
}
```

### Table field

Uses `match { }` to select a row by key, then continues pipeline on extracted value:

```kdl
upc   { match { eq "UPC" } }
price { match { starts "Price" }; re RE_PRICE; to-float; fallback 0.0 }
```

---

## 5. Pipeline

Operations execute left-to-right. Each receives output of the previous.
Starting type is always `DOCUMENT` (or type of `-init` value when using `self`).

### fallback

Catches any pipeline error, returns a literal value instead.
Must be the last operation.

| literal | type |
|---------|------|
| `0` | `INT` |
| `0.0` | `FLOAT` |
| `"text"` | `STRING` |
| `#true` / `#false` | `BOOL` |
| `#null` | `NULL` |
| `{}` | empty list |

```kdl
price { css ".price"; text; to-float; fallback 0.0 }
next  { css ".next a"; attr "href"; fallback #null }
tags  { css-all ".tag"; text; fallback {} }
```

### assert

Validates current value without modifying it.
Raises error if fails (caught by `fallback` if present).
Can appear multiple times in a pipeline.

```kdl
title { css "title"; text; assert { ne "404" }; fallback "unknown" }
```

### filter

Filters a list, removing non-matching elements.
Supports `not { }` for inversion and `define` references.

```kdl
images {
    css-all "img"; attr "src"
    filter { ends ".png" ".jpg"; not { ends ".webp" } }
}
```

---

## 6. define

Macro substitution — inlined into AST at parse time, similar to C `#define`.

### Scalar constant

Substituted as an argument value in any operation.

```kdl
define FMT_URL="https://example.com/{{}}"
define RE_PRICE=#"(\d+(?:\.\d+)?)"#
```

```kdl
url   { css "a"; attr "href"; fmt FMT_URL }
price { css ".price"; text; re RE_PRICE; to-float }
```

### Operation block

Any sequence of DSL operations — inlined directly into a field pipeline or `filter { }`.

```kdl
define EXTRACT-HREF { css "a"; attr "href" }
define F-IMAGE-EXT  { ends ".png" ".jpg" }
```

```kdl
link   { EXTRACT-HREF; fmt FMT_URL }
images { css-all "img"; attr "src"; filter { F-IMAGE-EXT } }
```

---

## 7. transform

Defines a named code snippet for a specific target language.
Declared at module level, called inside field pipelines via `transform name`.

```kdl
transform name accept=TYPE return=TYPE {
    py {
        import "import1" "import2"   // optional, multiple as args
        code "line1" "line2"         // each arg = one line; codegen adds indentation
    }
    js {
        code "line1" "line2"
    }
}
```

**Markers in `code`:**

| marker | description |
|--------|-------------|
| `{{PRV}}` | variable holding the previous pipeline value (input) |
| `{{NXT}}` | variable that will hold the result (output) |

`accept` and `return` must be explicit `VariableType` values — `AUTO` is not allowed.

Supported target languages: `py`, `js`, `go`, `lua`, `ts`.

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

transform to-list-base64 accept=LIST_STRING return=LIST_STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = [str(b64decode(i)) for i in {{PRV}}]"
    }
    js {
        code "const {{NXT}} = {{PRV}}.map(i => btoa(i));"
    }
}
```

Usage in field pipeline:

```kdl
struct Demo {
    item  { css "a[href]"; attr "href"; transform to-base64 }
    items { css-all "a[href]"; attr "href"; transform to-list-base64 }
}
```

---

## 8. dsl / expr

`dsl` declares a named inline code block for a specific target language at module level.
`expr` calls a named `dsl` block (or block `define`) from inside a field pipeline.

### dsl

| keyword | args        | properties                        | children     |
|---------|-------------|-----------------------------------|--------------|
| `dsl`   | `name: str` | `lang=LANG`, `accept=TYPE` (opt), `return=TYPE` (opt) | `import`, `code` |

`lang` must be one of: `py`, `js`, `go`, `lua`, `ts`.

Children block:
- `import "line1" "line2"` — optional; each arg is one import statement.
- `code "line1" "line2"` — required; each arg is one line of code.

**Markers in `code`:**

| marker    | description                                          |
| --------- | ---------------------------------------------------- |
| `{{PRV}}` | variable holding the previous pipeline value (input) |
| `{{NXT}}` | variable that will hold the result (output)          |

```kdl
dsl STRIP lang="py" {
    code "{{NXT}} = {{PRV}}.strip()"
}

dsl DECODE_B64 lang="py" {
    import "from base64 import b64decode"
    code "{{NXT}} = b64decode({{PRV}}).decode()"
}

dsl TO_INT lang="js" {
    code "const {{NXT}} = parseInt({{PRV}}, 10);"
}
```

### expr

| keyword | args        | properties | children |
|---------|-------------|------------|----------|
| `expr`  | `name: str` | —          | —        |

`name` must refer to a `dsl` block or a block `define` declared at module level.
Scalar `define` values cannot be used as `expr` targets.

```kdl
struct Demo {
    title   { css "h1"; expr STRIP }
    encoded { css ".b64"; attr "data-val"; expr DECODE_B64 }
}
```

---

## 9. json mapping

Schema for deserializing a JSON string extracted from HTML.
Used together with the `jsonify` operation.

```kdl
json Name {
    field type
    field type?         // optional (= type | null)
    field type {}       // array of primitives
    field OtherJson     // nested reference
}

json Name array=#true { ... }   // top-level array (default: array=#false)
```

### Field types

| type | description |
|------|-------------|
| `str` / `int` / `float` / `bool` | primitives |
| `OtherJson` | reference to another `json` definition |
| `?` suffix | optional field (value or null) |
| `{}` suffix | array of that type |

```kdl
json Author { name str; slug str }

json Quote array=#true {
    tags   str {}
    author Author
    text   str?
}
```

Used with `jsonify`:

```kdl
data       { raw; re RE_PAT; jsonify Quote }
first-text { raw; re RE_PAT; jsonify Quote path="0.text" }
```