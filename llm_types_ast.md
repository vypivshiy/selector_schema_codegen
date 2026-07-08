# Type System & AST Architecture

## Type System

### VariableType enum (ast/types.py)

Scalar base types only — optional/array modifiers live in `TypeInfo`, not in the enum:

```
DOCUMENT, STRING, INT, FLOAT, BOOL, NULL, NESTED, JSON, AUTO
```

- `NESTED` and `JSON` are terminal types — pipeline ends after nested/jsonify.
- `AUTO` is internal, used for type inference.
- `fallback #null` sets `TypeInfo.is_optional = True`.

### TypeInfo (ast/types.py)

Frozen dataclass — unified type container with modifiers:

| Field | Type | Meaning |
|---|---|---|
| `base` | `VariableType` | STRING, INT, FLOAT, BOOL, NULL, NESTED, JSON, DOCUMENT, AUTO |
| `is_array` | `bool` | List modifier (replaces old LIST_* enum values) |
| `is_optional` | `bool` | Optional modifier (replaces old OPT_* enum values) |
| `ref` | `str \| None` | Struct/JsonDef name for NESTED/JSON types |
| `omitempty` | `bool` | `@omitempty` — key may be absent from JSON |
| `skip` | `bool` | `@skip` — field parsed but excluded from output |

Properties: `.is_list` (alias for is_array), `.is_ref` (NESTED/JSON + has ref).

Target-language rendering is done by `PythonVisitor._resolve_type()` / `JsVisitor` class attrs.

### StructType enum

- ITEM (default): single object → dict
- LIST: repeating elements → list[dict], requires @split-doc
- DICT: key-value map → dict[str, any], requires @split-doc + @key + @value
- TABLE: HTML table → dict, requires @table + @rows + @match + @value
- FLAT: deduplicated scalars → list[str], no special fields needed
- REST: rest-api endpoint handler → json objects, uses `@request`

**Syntax**: struct types can be specified in KDL two ways:
- **Recommended**: prefix form — `(list)struct Foo { ... }`, `(dict)struct Bar { ... }`, etc.
- **Legacy** (still works): argument form — `struct Foo type="list" { ... }`

---

## AST Architecture

All nodes inherit from `Node` base class (has `body` attribute).

### Module layer
- `Module` → top-level container, holds all children. Module-level docstring lives in the `doc` field.
- `Docstring` (DEPRECATED, kept for backward-compat imports — was a body node; now `Module.doc`)
- `Utilities`, `CodeStartHook`, `CodeEndHook`

### Struct layer
- `StructBase` → base for `Struct` (HTML parser) and `StructRest` (REST API). Per-struct docstring lives in the `doc` field (position is visitor-dependent: Python emits it below `class X:`, JS emits it above).
- `Struct(name, struct_type, keep_order, doc)` → HTML parser schema
- `StructRest(name, errors, doc)` → REST API endpoint handler
- `Field(name)` → output field with pipeline of operations
- `Init` → container for `InitFieldCall` entries
- `InitFieldCall(name)` → call-site inside constructor that invokes the corresponding `InitField` method
- `InitField(name)` → precomputed value method, referenced as `@name` via `Self` node
- `PreValidate` → assert-based validation before parsing
- `CheckMethod(name)` → boolean check method. Unlike Field/PreValidate, has no `v` parameter; visitor initializes `v = self._doc`. Pipeline must contain `to-bool`.
- `SplitDoc` → split document into items (for LIST/DICT types)
- `Key`, `Value` → dict key/value extraction
- `TableConfig`, `TableRows`, `TableMatchKey` → table struct support
- `StartParse` → marker node for parser entry

### REST / transport layer
- `MethodBase` → base for REST method nodes (holds `http_request: RequestHttp`)
- `MethodFetch(name, response_path, response_join)` → HTML-parser fetch classmethod
- `MethodRest(name, response_schema, doc)` → REST endpoint method
- `RequestHttp(method, url, headers, cookies, params, body_kind, body)` → normalized HTTP config (child of MethodBase)
- `PlaceholderSpec(name, type_name, is_array, is_optional, style)` → parsed `{{...}}` token
- `ErrorResponse(status, schema_name, conditions, required_keys)` → `@error` mapping inside `type=rest` struct

### Pipeline nodes (operations within fields)
Selectors: CssSelect, CssSelectAll, XpathSelect, XpathSelectAll, CssRemove, XpathRemove
Extract: Text, Raw, Attr
String: Trim, Ltrim, Rtrim, NormalizeSpace, RmPrefix, RmSuffix, RmPrefixSuffix, Fmt, Repl, ReplMap, Lower, Upper, Split, Join, Unescape
Regex: Re, ReAll, ReSub
Array: Index, Slice, Len, Unique
Cast: ToInt, ToFloat, ToBool, Jsonify, Nested
Control: Fallback, Self, Return
Predicates: Filter, Assert, Match (containers) + PredEq/Ne/Gt/Lt/Ge/Le/Range + PredStarts/Ends/Contains/In/Re/ReAny/ReAll + PredCss/Xpath/HasAttr + PredAttr* + PredText* + PredCount* + LogicNot/And/Or

### Type definitions
- `TypeDef`, `TypeDefField` → auto-generated type annotations for structs
- `JsonDef`, `JsonDefField` → JSON schema definitions
