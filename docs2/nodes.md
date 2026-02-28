# KDL Schema DSL — AST Nodes Reference

## Table of Contents

- [KDL Schema DSL — AST Nodes Reference](#kdl-schema-dsl--ast-nodes-reference)
  - [Table of Contents](#table-of-contents)
  - [1. Tree structure](#1-tree-structure)
  - [2. Module level](#2-module-level)
  - [3. TypeDef](#3-typedef)
  - [4. JsonDef](#4-jsondef)
  - [5. Struct](#5-struct)
  - [6. Pipeline — Selectors](#6-pipeline--selectors)
  - [7. Pipeline — Extract](#7-pipeline--extract)
  - [8. Pipeline — String](#8-pipeline--string)
  - [9. Pipeline — Regex](#9-pipeline--regex)
  - [10. Pipeline — Array](#10-pipeline--array)
  - [11. Pipeline — Cast](#11-pipeline--cast)
  - [12. Pipeline — Control](#12-pipeline--control)
  - [13. Predicate containers](#13-predicate-containers)
  - [14. Predicate ops](#14-predicate-ops)
    - [Comparison](#comparison)
    - [String](#string)
    - [Regex](#regex)
    - [Document](#document)
    - [List (assert only)](#list-assert-only)
    - [Logic](#logic)
  - [14. Transform](#14-transform)
  - [15. Node count summary](#15-node-count-summary)

---

## 1. Tree structure

```
Module
├── Docstring
├── Imports
├── Utilities
├── JsonDef
│   └── JsonDefField
├── TypeDef                   ← generated from Struct, inserted before Struct
│   └── TypeDefField
└── Struct
    ├── StructDocstring
    ├── PreValidate
    │   └── pipeline nodes...
    ├── Init
    │   └── InitField         ← named, cacheable pipeline
    │       └── pipeline nodes...
    ├── SplitDoc              (list)
    │   └── pipeline nodes...
    ├── Key                   (dict)
    │   └── pipeline nodes...
    ├── Value                 (dict / table)
    │   └── pipeline nodes...
    ├── TableConfig           (table)
    │   └── pipeline nodes...
    ├── TableRow              (table)
    │   └── pipeline nodes...
    ├── TableMatchKey         (table)
    │   └── pipeline nodes...
    └── Field
        └── pipeline nodes...
```

**Build order in Module.body:**
1. `CodeStartHook`
2. `Docstring`, `Imports`, `Utilities`
3. `JsonDef` entries
4. `TypeDef` entries (generated from Structs, one per Struct)
5. `Struct` entries
6. `CodeEndHook`

**Field pipeline execution order:**
`PreValidate` → `Init` fields → `SplitDoc` → regular `Field` entries

---

## 2. Module level

| node | fields | description |
|------|--------|-------------|
| `Module` | `body: list[Node]` | root node |
| `CodeStartHook` | `body: list[Node]` | user code insertion point before generated code |
| `Docstring` | `value: str` | module docstring |
| `Imports` | `body: list[Node]` | generated import statements |
| `Utilities` | `body: list[Node]` | generated helper functions |
| `CodeEndHook` | `body: list[Node]` | user code insertion point after all generated structs |

**DSL → node mapping:**

```kdl
doc "text"    → Docstring(value="text")
// define resolved at parse time — no AST node produced
```

---

## 3. TypeDef

Generated from `Struct` after AST construction. Inserted before corresponding `Struct` in `Module.body`.

| node | fields | description |
|------|--------|-------------|
| `TypeDef` | `name: str`, `struct_type: StructType`, `body: list[TypeDefField]` | type annotation for a struct |
| `TypeDefField` | `name: str`, `ret_type: VariableType`, `nested_ref: str \| None`, `json_ref: str \| None` | single field type |

`nested_ref` — set when `ret_type == NESTED`, holds the target struct name.
`json_ref` — set when `ret_type == JSON`, holds the target JsonDef name.

---

## 4. JsonDef

| node | fields | description |
|------|--------|-------------|
| `JsonDef` | `name: str`, `is_array: bool`, `body: list[JsonDefField]` | JSON mapping definition |
| `JsonDefField` | `name: str`, `type_name: str`, `is_optional: bool`, `is_array: bool`, `ref_name: str \| None` | single field in JSON mapping |

**DSL → node mapping:**

```kdl
json Author { name str; slug str? }
→ JsonDef(name="Author", is_array=False, body=[
    JsonDefField(name="name", type_name="str", is_optional=False, is_array=False),
    JsonDefField(name="slug", type_name="str", is_optional=True,  is_array=False),
  ])

json Quote array=#true { tags str {}; author Author }
→ JsonDef(name="Quote", is_array=True, body=[
    JsonDefField(name="tags",   type_name="str",    is_array=True,  ref_name=None),
    JsonDefField(name="author", type_name="Author", is_array=False, ref_name="Author"),
  ])
```

---

## 5. Struct

| node | fields | description |
|------|--------|-------------|
| `Struct` | `name: str`, `struct_type: StructType`, `body: list[Node]` | parser schema |
| `StructDocstring` | `value: str` | struct-level docstring |
| `PreValidate` | `body: list[Node]` | validation pipeline before parsing |
| `Init` | `body: list[InitField]` | pre-computed named values |
| `InitField` | `name: str`, `body: list[Node]` | single named cached pipeline |
| `SplitDoc` | `body: list[Node]` | split document into items (`list`) |
| `Key` | `body: list[Node]` | key extraction pipeline (`dict`) |
| `Value` | `body: list[Node]` | value extraction pipeline (`dict` / `table`) |
| `TableConfig` | `body: list[Node]` | select table element (`table`) |
| `TableRow` | `body: list[Node]` | select table rows (`table`) |
| `TableMatchKey` | `body: list[Node]` | extract key cell text for row matching (`table`) |
| `Field` | `name: str`, `body: list[Node]` | regular output field |

`StructType` enum: `ITEM | LIST | DICT | TABLE | FLAT`

**DSL → node mapping:**

```kdl
struct Book type=list { ... }
→ Struct(name="Book", struct_type=LIST, body=[...])

-doc "text"        → StructDocstring(value="text")
-pre-validate { }  → PreValidate(body=[...])
-init { hrefs { css-all "a" } }
→ Init(body=[InitField(name="hrefs", body=[CssSelectAll(query="a")])])
-split-doc { }     → SplitDoc(body=[...])
-key { }           → Key(body=[...])
-value { }         → Value(body=[...])
-table { }         → TableConfig(body=[...])
-row { }           → TableRow(body=[...])
-match { }         → TableMatchKey(body=[...])
title { css "h1"; text }
→ Field(name="title", body=[CssSelect(query="h1"), Text()])
```

---

## 6. Pipeline — Selectors

| node | fields | accept | ret |
|------|--------|--------|-----|
| `CssSelect` | `query: str` | `DOCUMENT` | `DOCUMENT` |
| `CssSelectAll` | `query: str` | `DOCUMENT` | `LIST_DOCUMENT` |
| `XpathSelect` | `query: str` | `DOCUMENT` | `DOCUMENT` |
| `XpathSelectAll` | `query: str` | `DOCUMENT` | `LIST_DOCUMENT` |
| `CssRemove` | `query: str` | `DOCUMENT` | `DOCUMENT` |
| `XpathRemove` | `query: str` | `DOCUMENT` | `DOCUMENT` |

---

## 7. Pipeline — Extract

| node | fields | accept | ret |
|------|--------|--------|-----|
| `Text` | — | `DOCUMENT \| LIST_DOCUMENT` | `STRING \| LIST_STRING` |
| `Raw` | — | `DOCUMENT \| LIST_DOCUMENT` | `STRING \| LIST_STRING` |
| `Attr` | `keys: tuple[str, ...]` | `DOCUMENT \| LIST_DOCUMENT` | `STRING \| LIST_STRING` |

`Attr`: single key → error if not found; multiple keys → missing skipped, always `LIST_STRING`.

---

## 8. Pipeline — String

All string nodes accept `STRING | LIST_STRING`, return same type (map semantics).

| node | fields |
|------|--------|
| `Trim` | — |
| `Ltrim` | — |
| `Rtrim` | — |
| `NormalizeSpace` | — |
| `RmPrefix` | `substr: str` |
| `RmSuffix` | `substr: str` |
| `RmPrefixSuffix` | `substr: str` |
| `Fmt` | `template: str` |
| `Repl` | `old: str`, `new: str` |
| `ReplMap` | `replacements: dict[str, str]` |
| `Lower` | — |
| `Upper` | — |
| `Split` | `sep: str` |
| `Join` | `sep: str` |
| `Unescape` | — |

Exceptions:
- `Split`: accept `STRING` → ret `LIST_STRING`
- `Join`: accept `LIST_STRING` → ret `STRING`

---

## 9. Pipeline — Regex

| node | fields | accept | ret |
|------|--------|--------|-----|
| `Re` | `pattern: str` | `STRING \| LIST_STRING` | same |
| `ReAll` | `pattern: str` | `STRING` | `LIST_STRING` |
| `ReSub` | `pattern: str`, `repl: str` | `STRING \| LIST_STRING` | same |

---

## 10. Pipeline — Array

| node | fields | accept | ret |
|------|--------|--------|-----|
| `Index` | `i: int` | `LIST_AUTO` | `AUTO` |
| `First` | — | `LIST_AUTO` | `AUTO` |
| `Last` | — | `LIST_AUTO` | `AUTO` |
| `Slice` | `start: int`, `end: int` | `LIST_AUTO` | `LIST_AUTO` |
| `Len` | — | `LIST_AUTO` | `INT` |
| `Unique` | `keep_order: bool` | `LIST_STRING` | `LIST_STRING` |

---

## 11. Pipeline — Cast

| node | fields | accept | ret |
|------|--------|--------|-----|
| `ToInt` | — | `STRING \| LIST_STRING` | `INT \| LIST_INT` |
| `ToFloat` | — | `STRING \| LIST_STRING` | `FLOAT \| LIST_FLOAT` |
| `ToBool` | — | `AUTO` | `BOOL` |
| `Jsonify` | `schema_name: str`, `path: str \| None` | `STRING` | `JSON` |
| `Nested` | `struct_name: str` | `DOCUMENT` | `NESTED` |

---

## 12. Pipeline — Control

| node | fields | accept | ret | notes |
|------|--------|--------|-----|-------|
| `Self` | `name: str` | — | type of `InitField` | must be first op; name resolved at AST build time |
| `Fallback` | `value: Any` | `AUTO` | type of value | must be last op |
| `Return` | — | `AUTO` | `AUTO` | implicit last node of every pipeline; carries final `ret_type` |

---

## 13. Predicate containers

| node | fields | accept | ret | notes |
|------|--------|--------|-----|-------|
| `Filter` | `body: list[Node]` | `LIST_STRING \| LIST_DOCUMENT` | same | removes non-matching elements |
| `Assert` | `body: list[Node]` | `AUTO` | same | raises error if any predicate fails |
| `Match` | `body: list[Node]` | `DOCUMENT` | `STRING` | selects table row; only in `table` Field |

---

## 14. Predicate ops

Used inside `Filter`, `Assert`, `Match` body. Combined with AND by default.

### Comparison

| node | fields | notes |
|------|--------|-------|
| `PredEq` | `values: tuple[str \| int, ...]` | int → compare len; multiple values use OR |
| `PredNe` | `values: tuple[str \| int, ...]` | int → compare len; multiple values use OR |
| `PredGt` | `value: int` | len > value |
| `PredLt` | `value: int` | len < value |
| `PredGe` | `value: int` | len >= value |
| `PredLe` | `value: int` | len <= value |
| `PredRange` | `start: int`, `end: int` | shortcut for Gt + Lt |

### String

| node | fields | notes |
|------|--------|-------|
| `PredStarts` | `values: tuple[str, ...]` | multiple values use OR |
| `PredEnds` | `values: tuple[str, ...]` | multiple values use OR |
| `PredContains` | `values: tuple[str, ...]` | multiple values use OR |
| `PredIn` | `values: tuple[str, ...]` | str must equal one of values |

### Regex

| node | fields | notes |
|------|--------|-------|
| `PredRe` | `pattern: str` | matches pattern |
| `PredReAny` | `pattern: str` | at least one element matches (assert only) |
| `PredReAll` | `pattern: str` | all elements match (assert only) |

### Document

| node | fields | notes |
|------|--------|-------|
| `PredCss` | `query: str` | element contains matching child |
| `PredXpath` | `query: str` | element contains matching child |
| `PredHasAttr` | `name: str` | element has the attribute |

### List (assert only)

| node | fields | notes |
|------|--------|-------|
| `PredCountEq` | `value: int` | len == value |
| `PredCountGt` | `value: int` | len > value |
| `PredCountLt` | `value: int` | len < value |

### Logic

| node | fields | notes |
|------|--------|-------|
| `LogicNot` | `body: list[Node]` | inverts result of inner block |
| `LogicAnd` | `body: list[Node]` | explicit AND grouping (default behaviour) |
| `LogicOr` | `body: list[Node]` | OR grouping |

---

## 14. Transform

Declared at module level. Called in field pipelines via `TransformCall`.

| node | fields | description |
|------|--------|-------------|
| `TransformDef` | `name: str`, `accept: VariableType`, `ret: VariableType`, `body: list[TransformTarget]` | module-level transform definition |
| `TransformTarget` | `lang: str`, `imports: tuple[str, ...]`, `code: tuple[str, ...]` | per-language implementation |
| `TransformCall` | `name: str`, `accept: VariableType`, `ret: VariableType` | pipeline op — calls named transform |

`TransformCall.accept` and `ret` are copied from `TransformDef` at AST build time.
Build-time error if name not found or types mismatch with pipeline cursor.

```
TransformDef(name="to-base64", accept=STRING, ret=STRING)
└── TransformTarget(lang="py",
        imports=("from base64 import b64decode",),
        code=("{{NXT}} = str(b64decode({{PRV}})))",))
└── TransformTarget(lang="js",
        imports=(),
        code=("const {{NXT}} = btoa({{PRV}});",))
```

---

## 15. Node count summary

| group | count |
|-------|-------|
| Module level | 6 |
| Transform | 3 |
| TypeDef | 2 |
| JsonDef | 2 |
| Struct | 12 |
| Selectors | 6 |
| Extract | 3 |
| String | 15 |
| Regex | 3 |
| Array | 6 |
| Cast | 5 |
| Control | 3 |
| Predicate containers | 3 |
| Predicate ops | 20 |
| **Total** | **87** |