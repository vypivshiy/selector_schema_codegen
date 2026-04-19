# KDL Operations — Quick Reference

## Type System

| Type | Description |
|------|-------------|
| `DOCUMENT` | HTML element node |
| `LIST_DOCUMENT` | List of HTML nodes |
| `STRING` | String value |
| `LIST_STRING` | List of strings |
| `INT` | Integer |
| `LIST_INT` | List of integers |
| `FLOAT` | Float |
| `LIST_FLOAT` | List of floats |
| `BOOL` | Boolean |
| `OPT_STRING` | STRING \| null (via `fallback #null`) |
| `OPT_INT` | INT \| null |
| `OPT_FLOAT` | FLOAT \| null |
| `NESTED` | Nested struct result (terminal — pipeline ends) |
| `JSON` | JSON deserialized result (terminal — pipeline ends) |

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
| `attr "n1" "n2" ...` | DOCUMENT | LIST_STRING |
| `attr "n1" "n2" ...` | LIST_DOCUMENT | LIST_STRING |
| `raw` | DOCUMENT | STRING |
| `raw` | LIST_DOCUMENT | LIST_STRING |
| `trim/ltrim/rtrim` | STRING | STRING |
| `trim/ltrim/rtrim` | LIST_STRING | LIST_STRING |
| `lower/upper` | STRING | STRING |
| `lower/upper` | LIST_STRING | LIST_STRING |
| `normalize-space` | STRING | STRING |
| `rm-prefix "x"` | STRING | STRING |
| `rm-suffix "x"` | STRING | STRING |
| `rm-prefix-suffix "x"` | STRING | STRING |
| `fmt DEFINE` | STRING | STRING |
| `unescape` | STRING | STRING |
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
| `to-bool` | any scalar | BOOL |
| `first` | LIST_* | (scalar type) |
| `last` | LIST_* | (scalar type) |
| `index N` | LIST_* | (scalar type) |
| `slice N M` | LIST_* | LIST_* |
| `len` | LIST_* | INT |
| `unique` | LIST_STRING | LIST_STRING |
| `nested Name` | DOCUMENT | NESTED |
| `jsonify Name` | STRING | JSON |
| `filter { pred }` | LIST_* | LIST_* (same) |
| `assert { pred }` | any | same |
| `match { pred }` | DOCUMENT | STRING (table field only) |
| `fallback <val>` | any | same / OPT_* |
| `fallback {}` | LIST_* | LIST_* |
| `transform Name` | by accept | by return |
| `expr Name` | by define/dsl | by define/dsl |

## Predicates

Used inside `filter { }`, `assert { }`, `match { }`:

### String predicates
```
eq "val" [val2 ...]         ne "val" [val2 ...]
starts "val" [val2 ...]     ends "val" [val2 ...]
contains "val" [val2 ...]   in "val" [val2 ...]
re #"pat"#
```

### Numeric predicates (assert only)
```
gt N    lt N    ge N    le N
```

### Length predicates
```
len-eq N [N2 ...]    len-ne N [N2 ...]
len-gt N             len-lt N
len-ge N             len-le N
len-range MIN MAX
```

### Attribute predicates
```
has-attr "name" [name2 ...]
attr-eq "name" "val" [val2 ...]
attr-ne "name" "val" [val2 ...]
attr-starts "name" "val" [val2 ...]
attr-ends "name" "val" [val2 ...]
attr-contains "name" "val" [val2 ...]
attr-re "name" #"pat"#
```

### Text predicates
```
text-starts "val" [val2 ...]
text-ends "val" [val2 ...]
text-contains "val" [val2 ...]
text-re #"pat"#
```

### Element predicates
```
css ".sel"            (element has child matching CSS selector)
xpath "//path"        (element has child matching XPath)
```

### Regex predicates (assert only)
```
re-all #"pat"#        (all elements match)
re-any #"pat"#        (at least one matches)
```

### Logic containers
```
and { ... }    or { ... }    not { ... }
```

## Struct Special Fields

| Field | Used in | Purpose |
|-------|---------|---------|
| `@doc "..."` | all | Documentation |
| `@request "..."` | all | Optional HTTP constructor (needs `--http-client` at codegen) |
| `@init { ... }` | all | Precompute shared values |
| `@split-doc { ... }` | list, dict | Split document into items |
| `@pre-validate { ... }` | all | Assert before parsing |
| `@table { ... }` | table | Select the table element |
| `@rows { ... }` | table | Select rows |
| `@match { ... }` | table | Pipeline for key extraction |
| `@value { ... }` | table, dict | Pipeline for value extraction |
| `@key { ... }` | dict | Key extraction pipeline |

## Fallback Values

```kdl
fallback #null    // None / null -> makes type OPT_*
fallback #true    // True / true
fallback #false   // False / false
fallback 0        // integer zero
fallback 0.0      // float zero
fallback ""       // empty string
fallback {}       // empty list (for LIST_* types)
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

## Define Patterns

### Scalar defines (substituted as argument values)
```kdl
define BASE-URL="https://example.com"
define FMT-URL="https://example.com/{{}}"
define RE-PRICE=#"(\d+(?:\.\d+)?)"#
```

### Block defines (used as pipeline operations)
```kdl
define EXTRACT-HREF {
    css "a"
    attr "href"
}

define REPL-RATING {
    repl { One "1"; Two "2"; Three "3"; Four "4"; Five "5" }
}
```

Usage:
```kdl
link { EXTRACT-HREF; trim }
// or explicitly:
link { expr EXTRACT-HREF; trim }
```
