# KDL Schema DSL — Operations & Types Reference

## Table of Contents

1. [Types](#1-types)
2. [Selectors](#2-selectors)
3. [Extract](#3-extract)
4. [String](#4-string)
5. [Regex](#5-regex)
6. [Array](#6-array)
7. [Cast](#7-cast)
8. [Filter ops](#8-filter-ops)
9. [Assert ops](#9-assert-ops)
10. [Control](#10-control)

---

## 1. Types

### Scalar types

| type | description |
|------|-------------|
| `DOCUMENT` | HTML element (parsed node) |
| `STRING` | string value |
| `INT` | integer |
| `FLOAT` | float |
| `BOOL` | boolean |
| `NULL` | null value |
| `NESTED` | result of a nested struct parser |
| `JSON` | deserialized JSON structure |

### List types

| type | description |
|------|-------------|
| `LIST_DOCUMENT` | list of HTML elements |
| `LIST_STRING` | list of strings |
| `LIST_INT` | list of integers |
| `LIST_FLOAT` | list of floats |

### Special types

| type | description |
|------|-------------|
| `AUTO` | resolved from context at AST build time (scalar) |
| `LIST_AUTO` | resolved from context at AST build time (list) |

`AUTO` / `LIST_AUTO` — concrete type is resolved during AST construction, not at runtime.

Examples:
- `to-bool` accepts `AUTO` — can cast any scalar
- `index` accepts `LIST_AUTO`, returns `AUTO` — element type follows list type
- `fallback` accepts `AUTO` — ret type set by the literal provided

### Pipeline type rules

- Every field pipeline starts with `DOCUMENT` (or type of `-init` value when using `self`).
- Each operation receives the `ret` type of the previous operation as its `accept` type.
- `AUTO` / `LIST_AUTO` is compatible with any concrete type — resolved at AST build time.
- Incompatible types (e.g. `STRING` → operation expecting `DOCUMENT`) are a build-time error.
- Unknown `self` reference (name not declared in `-init`) is a build-time error.

---

## 2. Selectors

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `css` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | |
| `css-all` | `query: str` | — | `DOCUMENT` | `LIST_DOCUMENT` | |
| `xpath` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | |
| `xpath-all` | `query: str` | — | `DOCUMENT` | `LIST_DOCUMENT` | |
| `css-remove` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | mutates document in-place, removes matched elements |
| `xpath-remove` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | mutates document in-place, removes matched elements |

---

## 3. Extract

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `text` | — | — | `DOCUMENT` \| `LIST_DOCUMENT` | `STRING` \| `LIST_STRING` | ret follows input type |
| `raw` | — | — | `DOCUMENT` \| `LIST_DOCUMENT` | `STRING` \| `LIST_STRING` | ret follows input type |
| `attr` | `key: str` (one or more) | — | `DOCUMENT` \| `LIST_DOCUMENT` | `STRING` \| `LIST_STRING` | single key: error if not found; multiple keys: missing skipped, always returns `LIST_STRING` |

---

## 4. String

All string operations support both `STRING` and `LIST_STRING`.
When input is `LIST_STRING` the operation is applied to each element (map semantics).

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `trim` | — | — | `STRING` \| `LIST_STRING` | same | strips leading and trailing whitespace |
| `ltrim` | — | — | `STRING` \| `LIST_STRING` | same | strips leading whitespace |
| `rtrim` | — | — | `STRING` \| `LIST_STRING` | same | strips trailing whitespace |
| `normalize-space` | — | — | `STRING` \| `LIST_STRING` | same | collapses inner whitespace to single space, then trims |
| `rm-prefix` | `substr: str` | — | `STRING` \| `LIST_STRING` | same | removes prefix if present |
| `rm-suffix` | `substr: str` | — | `STRING` \| `LIST_STRING` | same | removes suffix if present |
| `rm-prefix-suffix` | `substr: str` | — | `STRING` \| `LIST_STRING` | same | removes both prefix and suffix if present |
| `fmt` | `template: str` | — | `STRING` \| `LIST_STRING` | same | `{{}}` is replaced with current value |
| `repl` | `old: str, new: str` | — | `STRING` \| `LIST_STRING` | same | replaces all occurrences of old with new |
| `repl` (map) | — | — | `STRING` \| `LIST_STRING` | same | map form via children block `{ "old" "new" }` |
| `lower` | — | — | `STRING` \| `LIST_STRING` | same | converts to lowercase |
| `upper` | — | — | `STRING` \| `LIST_STRING` | same | converts to uppercase |
| `split` | `sep: str` | — | `STRING` | `LIST_STRING` | splits string into list by separator |
| `join` | `sep: str` | — | `LIST_STRING` | `STRING` | joins list into single string |
| `unescape` | — | — | `STRING` \| `LIST_STRING` | same | unescapes HTML entities and unicode escapes |

`args` may be a `define` name — substituted at parse time.

---

## 5. Regex

All regex operations support both `STRING` and `LIST_STRING`.
When input is `LIST_STRING` the operation is applied to each element (map semantics).

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `re` | `pattern: str` | — | `STRING` \| `LIST_STRING` | same | returns first match per element |
| `re-all` | `pattern: str` | — | `STRING` | `LIST_STRING` | returns all matches; scalar input only |
| `re-sub` | `pattern: str, repl: str` | — | `STRING` \| `LIST_STRING` | same | replaces all matches per element |

`pattern` may be a `define` name — substituted at parse time.
Raw KDL strings `#"..."#` recommended to avoid double-escaping.

---

## 6. Array

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `index` | `i: int` | — | `LIST_AUTO` | `AUTO` | negative index counts from end |
| `first` | — | — | `LIST_AUTO` | `AUTO` | shortcut for `index 0` |
| `last` | — | — | `LIST_AUTO` | `AUTO` | shortcut for `index -1` |
| `slice` | `start: int, end: int` | — | `LIST_AUTO` | `LIST_AUTO` | returns sublist `[start:end]` |
| `len` | — | — | `LIST_AUTO` | `INT` | returns list length |
| `unique` | — | `keep-order=#true\|#false` | `LIST_STRING` | `LIST_STRING` | removes duplicates; order not guaranteed unless `keep-order=#true` |

---

## 7. Cast

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `to-int` | — | — | `STRING` \| `LIST_STRING` | `INT` \| `LIST_INT` | list type preserved |
| `to-float` | — | — | `STRING` \| `LIST_STRING` | `FLOAT` \| `LIST_FLOAT` | list type preserved |
| `to-bool` | — | — | `AUTO` | `BOOL` | accepts any scalar |
| `jsonify` | `schema: str` | `path="..."` | `STRING` | `JSON` | deserializes JSON string via named `json` mapping; optional `path` extracts by dotted key e.g. `path="0.text"` |
| `nested` | `name: str` | — | `DOCUMENT` | `NESTED` | passes document to another struct parser, returns its result |

---

## 8. Filter ops

Used inside `filter { }` blocks. Applied to each element of a list independently.
Multiple ops in a block are combined with AND by default.

Predicate keywords are shared across `filter`, `assert`, and `match` — the container determines semantics.

### Predicate ops

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `eq` | `value: str\|int` (one or more) | — | `STRING` | `STRING` | int arg → compare len; multiple args use OR |
| `ne` | `value: str\|int` (one or more) | — | `STRING` | `STRING` | int arg → compare len; multiple args use OR |
| `gt` | `value: int` | — | `STRING` | `STRING` | len > value |
| `lt` | `value: int` | — | `STRING` | `STRING` | len < value |
| `ge` | `value: int` | — | `STRING` | `STRING` | len >= value |
| `le` | `value: int` | — | `STRING` | `STRING` | len <= value |
| `range` | `start: int, end: int` | — | `STRING` | `STRING` | shortcut for `gt start` + `lt end` |
| `starts` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `ends` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `contains` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `in` | `value: str` (one or more) | — | `STRING` | `STRING` | str must equal one of values |
| `re` | `pattern: str` | — | `STRING` | `STRING` | element matches pattern |
| `has-attr` | `name: str` | — | `DOCUMENT` | `DOCUMENT` | element has the attribute |
| `css` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | element contains matching child |
| `xpath` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | element contains matching child |

### Logic ops

| keyword | args | properties | children | notes |
|---------|------|------------|----------|-------|
| `not` | — | — | predicate ops | inverts result of inner block |
| `and` | — | — | predicate ops | explicit AND grouping (default behaviour) |
| `or` | — | — | predicate ops | OR grouping |

---

## 9. Assert ops

Used inside `assert { }` blocks. Do not modify the value.
Multiple ops in a block are combined with AND by default.
Uses the same predicate keywords as `filter`.

### Value comparison

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `eq` | `value: str\|int\|float` (one or more) | — | `STRING\|INT\|FLOAT` | same | multiple args use OR |
| `ne` | `value: str\|int\|float` (one or more) | — | `STRING\|INT\|FLOAT` | same | multiple args use OR |
| `gt` | `value: int\|float` | — | `INT\|FLOAT` | same | |
| `lt` | `value: int\|float` | — | `INT\|FLOAT` | same | |
| `ge` | `value: int\|float` | — | `INT\|FLOAT` | same | |
| `le` | `value: int\|float` | — | `INT\|FLOAT` | same | |

### String predicates

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `starts` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `ends` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `contains` | `value: str` (one or more) | — | `STRING` | `STRING` | multiple args use OR |
| `in` | `value: str` (one or more) | — | `STRING` | `STRING` | str must equal one of values |

### Regex

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `re` | `pattern: str` | — | `STRING` | `STRING` | string matches pattern |
| `re-any` | `pattern: str` | — | `LIST_STRING` | `LIST_STRING` | at least one element matches |
| `re-all` | `pattern: str` | — | `LIST_STRING` | `LIST_STRING` | all elements match |

### Document

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `css` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | asserts element exists |
| `xpath` | `query: str` | — | `DOCUMENT` | `DOCUMENT` | asserts element exists |
| `has-attr` | `name: str` | — | `DOCUMENT` | `DOCUMENT` | asserts attribute present |

### List

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `count eq` | `value: int` | — | `LIST_AUTO` | `LIST_AUTO` | asserts len == value |
| `count gt` | `value: int` | — | `LIST_AUTO` | `LIST_AUTO` | asserts len > value |
| `count lt` | `value: int` | — | `LIST_AUTO` | `LIST_AUTO` | asserts len < value |

### Logic

| keyword | args | properties | children | notes |
|---------|------|------------|----------|-------|
| `not` | — | — | assert ops | inverts result of inner block |

---

## 10. Control

### self

References a pre-computed value from `-init`. Must be the first operation in the field.
Resolved statically at AST build time — unknown name is a build-time error.

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `self` | `name: str` | — | — | type of `-init` field | only valid as first operation; name must exist in `-init` |

### **fallback**

Returns a literal value if any error occurs anywhere in the pipeline.
Must be the last operation in a field pipeline.

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `fallback` | `value: literal` | — | `AUTO` | type of literal | literal types: `int`, `float`, `str`, `#true\|#false`, `#null`, `{}` (empty list) |

### match

Used in `table`-type struct fields only.
Selects the row whose key cell (from `-match` pipeline) satisfies all conditions,
then passes the value cell (from `-value` pipeline) as `STRING` to the rest of the pipeline.
Predicates are combined with AND.

| keyword | args | properties | children | accept | ret | notes |
|---------|------|------------|----------|--------|-----|-------|
| `match` | — | — | predicate ops | `DOCUMENT` | `STRING` | only valid in `table` struct fields |

```kdl
upc   { match { eq "UPC" } }
price { match { starts "Price" }; re RE_PRICE; to-float; fallback 0.0 }
```

---

## 11. Transform (pipeline op)

Calls a named `transform` defined at module level.
`accept` and `ret` are taken from the transform definition — validated at AST build time.

| keyword | args | properties | accept | ret | notes |
|---------|------|------------|--------|-----|-------|
| `transform` | `name: str` | — | per definition | per definition | build-time error if name not declared or types mismatch |