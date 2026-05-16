# Type System & AST Architecture

## Type System

### VariableType enum (ast/types.py)

Scalar: DOCUMENT, STRING, OPT_STRING, INT, OPT_INT, FLOAT, OPT_FLOAT, BOOL, NULL, NESTED, JSON
List: LIST_DOCUMENT, LIST_STRING, LIST_INT, LIST_FLOAT
Auto: AUTO, LIST_AUTO (internal, for type inference)

Methods: `.optional` (STRING→OPT_STRING), `.is_list`, `.scalar` (LIST_STRING→STRING), `.as_list` (STRING→LIST_STRING)

NESTED and JSON are terminal types — pipeline ends after nested/jsonify.
`fallback #null` converts STRING→OPT_STRING, INT→OPT_INT, FLOAT→OPT_FLOAT.

### StructType enum

- ITEM (default): single object → dict
- LIST: repeating elements → list[dict], requires @split-doc
- DICT: key-value map → dict[str, any], requires @split-doc + @key + @value
- TABLE: HTML table → dict, requires @table + @rows + @match + @value
- FLAT: deduplicated scalars → list[str], no special fields needed
- REST: rest-api endpoint handler → json objects, uses `@request`

**Syntax**: struct types can be specified in KDL two ways:
- **Recommended**: prefix form — `(list)struct Foo { ... }`, `(dict)struct Bar { ... }`, etc.
- **Legacy** (still works): property form — `struct name="Foo" type="list" { ... }`

---

## AST Architecture

All nodes inherit from `Node` base class (has `body` attribute).

### Module layer
- `Module` → top-level container, holds all children
- `Docstring`, `Imports`, `Utilities`, `CodeStartHook`, `CodeEndHook`

### Struct layer
- `Struct(name, struct_type, keep_order)` → parser schema
- `Field(name)` → output field with pipeline of operations
- `Init` → container for `InitField` cached values
- `InitField(name)` → precomputed value, referenced as `@name` via `Self` node
- `PreValidate` → assert-based validation before parsing
- `CheckMethod(name)` → boolean check method, runs pipeline, returns bool
- `SplitDoc` → split document into items (for LIST/DICT types)
- `Key`, `Value` → dict key/value extraction
- `TableConfig`, `TableRow`, `TableMatchKey` → table struct support
- `RequestConfig(raw_payload, response_path, response_join, name, response_schema, doc)` → transport layer config; `placeholders` → `list[PlaceholderSpec]` (typed: `{{name[:type][[]][?][|style]}}`)
- `PlaceholderSpec(name, type_name, is_array, is_optional, style)` → parsed `{{...}}` token
- `ErrorResponse(status, schema_name, conditions)` → `@error` mapping inside `type=rest` struct
- `StartParse` → marker node for parser entry

### Pipeline nodes (operations within fields)
Selectors: CssSelect, CssSelectAll, XpathSelect, XpathSelectAll, CssRemove, XpathRemove
Extract: Text, Raw, Attr
String: Trim, Ltrim, Rtrim, NormalizeSpace, RmPrefix, RmSuffix, RmPrefixSuffix, Fmt, Repl, ReplMap, Lower, Upper, Split, Join, Unescape
Regex: Re, ReAll, ReSub
Array: Index, Slice, Len, Unique
Cast: ToInt, ToFloat, ToBool, Jsonify, Nested
Control: Fallback, FallbackStart, FallbackEnd, Self, Return
Predicates: Filter, Assert, Match (containers) + PredEq/Ne/Gt/Lt/... + LogicNot/And/Or

### Type definitions
- `TypeDef`, `TypeDefField` → auto-generated type annotations for structs
- `JsonDef`, `JsonDefField` → JSON schema definitions

### Transforms
- `TransformDef` → module-level reusable transform with per-language implementations
- `TransformTarget` → single language implementation (imports + code template)
- `TransformCall` → invoke transform in pipeline
