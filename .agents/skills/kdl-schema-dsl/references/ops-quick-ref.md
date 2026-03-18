# KDL Operations — Quick Reference

## Type System

| Type | Description |
|------|-------------|
| `DOCUMENT` | HTML element node |
| `LIST_DOCUMENT` | List of HTML nodes |
| `STRING` | String value |
| `LIST_STRING` | List of strings |
| `INT` | Integer |
| `FLOAT` | Float |
| `BOOL` | Boolean |

## Type Flow Table

| Operation | Accept | Return |
|-----------|--------|--------|
| `css "sel"` | DOCUMENT | DOCUMENT |
| `css-all "sel"` | DOCUMENT | LIST_DOCUMENT |
| `css-remove "sel"` | DOCUMENT | DOCUMENT |
| `text` | DOCUMENT | STRING |
| `text` | LIST_DOCUMENT | LIST_STRING |
| `attr "n"` | DOCUMENT | STRING |
| `attr "n"` | LIST_DOCUMENT | LIST_STRING |
| `raw` | DOCUMENT | STRING |
| `raw` | LIST_DOCUMENT | LIST_STRING |
| `trim/ltrim/rtrim` | STRING | STRING |
| `trim/ltrim/rtrim` | LIST_STRING | LIST_STRING |
| `lower/upper` | STRING | STRING |
| `normalize-space` | STRING | STRING |
| `rm-prefix "x"` | STRING | STRING |
| `rm-suffix "x"` | STRING | STRING |
| `fmt DEFINE` | STRING | STRING |
| `split "delim"` | STRING | LIST_STRING |
| `join "delim"` | LIST_STRING | STRING |
| `re #"(g)"#` | STRING | STRING |
| `re #"(g)"#` | LIST_STRING | LIST_STRING |
| `re-all #"p"#` | STRING | LIST_STRING |
| `re-sub #"p"# "r"` | STRING | STRING |
| `re-sub #"p"# "r"` | LIST_STRING | LIST_STRING |
| `repl "f" "t"` | STRING | STRING |
| `REPL-DEFINE` | STRING | STRING |
| `to-int` | STRING | INT |
| `to-float` | STRING | FLOAT |
| `to-bool` | DOCUMENT | BOOL |
| `to-bool` | STRING | BOOL |
| `first` | LIST_* | (item type) |
| `last` | LIST_* | (item type) |
| `index N` | LIST_* | (item type) |
| `slice N M` | LIST_* | LIST_* |
| `len` | LIST_* | INT |
| `len` | STRING | INT |
| `unique` | LIST_* | LIST_* |
| `nested Name` | DOCUMENT | (struct result) |
| `filter { pred }` | LIST_DOCUMENT | LIST_DOCUMENT |
| `filter { pred }` | LIST_STRING | LIST_STRING |
| `assert { pred }` | any | same |
| `match { pred }` | STRING | STRING (table field only) |

## Predicates

Used inside `filter { }`, `assert { }`, `match { }`:

```
eq "val"               ne "val"
starts "val"           ends "val"
contains "val"         re #"pat"#
has-attr "name"        attr-eq "name" "val"
attr-starts "n" "v"    attr-ends "n" "v"
attr-contains "n" "v"  attr-re "n" #"pat"#
text-contains "val"    text-starts "val"
text-ends "val"        text-re #"pat"#
css ".sel"             (element has child matching selector)
gt N  lt N  ge N  le N  range N M  in "a" "b"
and { ... }  or { ... }  not { ... }
```

## Struct Special Fields

| Field | Used in | Purpose |
|-------|---------|---------|
| `@doc "..."` | all | Documentation |
| `@init { ... }` | all | Precompute shared values |
| `@split-doc { ... }` | list, flat, dict | Split document into items |
| `@pre-validate { ... }` | all | Assert before parsing |
| `@table { ... }` | table | Select the table element |
| `@rows { ... }` | table | Select rows |
| `@match { ... }` | table | Pipeline for key extraction |
| `@value { ... }` | table | Pipeline for value extraction |
| `@key { ... }` | dict | Key extraction pipeline |
| `@value { ... }` | dict | Value extraction pipeline |

## Fallback Values

```kdl
fallback #null    // None / null
fallback #true    // True / true
fallback #false   // False / false
fallback 0        // integer zero
fallback 0.0      // float zero
fallback ""       // empty string
```

## @init Pattern

```kdl
struct Main {
    @init {
        raw-html { css ".content"; raw }
    }
    
    // reference with @name
    content {
        @raw-html
        re #"<p>(.*?)</p>"#
    }
}
```
