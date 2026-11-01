# HTML & Plain-Text (`(raw)struct`) Reference (DSL v2.1)

## 1. Unified `TypeInfo` Model & Directives

- **Scalar Base Types**: `DOC` (`DOCUMENT`), `STR` (`STRING`), `INT` (64-bit), `FLOAT` (64-bit), `BOOL`, `NULL`, `NESTED` (terminal), `JSON` (terminal).
- **Modifiers**: `T[]` (`is_array=True`), `T?` (`is_optional=True`, produced by `fallback #null` on `STR`/`INT`/`FLOAT` or `?` in `json`), `dict[K, V]` (in `json`).
- **Pipeline Start Type**: `DOC` in HTML structs/`fn`; `STR` in `(raw)struct`/`(raw)fn`; or `TypeOf(name)` when starting with `@<name>`.
- **Struct Directives** (for `item`, `list`, `table`, `dict`, `flat`, `raw`):
  - `@init { <name> { <pipeline> }; ... }` — precomputes & caches values on instance; referenced as **first op** in fields via `@<name>` (`E301` if undeclared; `self <name>` is deprecated).
  - `@pre-validate { assert ["<msg>"] { <predicates> } }` — validates input before `parse()`; raises `SscAssertionError`.
  - `@check <name> { <pipeline>; to-bool; [fallback #false] }` — emits public boolean method (`is_ok()` / `isOk()` / `IsOk()`); pipeline must end in `BOOL` (`E100`).
  - `@request [response-path="..."] [response-join="\n"] "<curl_or_http>"` — emits `fetch` / `async_fetch` constructor (requires `--http-client` at `generate`).

---

## 2. Complete Pipeline Operations Reference

| Category | Signature (`InType -> OutType`) | Rules & Map Semantics |
|---|---|---|
| **Selectors** | `css "<q>" \| css { "<q1>"; "<q2>"; ... } : DOC -> DOC` | Block form requires $\ge 2$ queries (no positional arg); returns first match |
| | `css-all "<q>" \| css-all { "<q1>"; "<q2>"; ... } : DOC -> DOC[]` | Block form ($\ge 2$ queries) returns first non-empty element list |
| | `css-remove "<q>" : DOC -> DOC` | Mutates DOM in-place; single positional arg only |
| | `xpath "<q>" \| xpath { "<q1>"; "<q2>"; ... } : DOC -> DOC` | Block form $\ge 2$ queries; forbidden in `slax` |
| | `xpath-all "<q>" \| xpath-all { "<q1>"; "<q2>"; ... } : DOC -> DOC[]` | Block form $\ge 2$ queries; forbidden in `slax` |
| | `xpath-remove "<q>" : DOC -> DOC` | Mutates DOM in-place; single arg only |
| **Extract** | `text : DOC -> STR, DOC[] -> STR[]` | Element text content |
| | `raw [outer\|inner] : DOC -> STR, DOC[] -> STR[]` | Default `outer` (includes element tag); `inner` extracts inner HTML only |
| | `attr "<k>" : DOC -> STR, DOC[] -> STR[]` | Single attribute value |
| | `attr "<k1>" "<k2>" ... : DOC -> STR[], DOC[] -> STR[]` | Multi-attribute extraction ($\ge 2$ args always returns `STR[]`) |
| **String** *(map over `STR` & `STR[]`)* | `trim ["<chars>"] \| ltrim ["<chars>"] \| rtrim ["<chars>"] : STR -> STR, STR[] -> STR[]` | Strips whitespace or custom character set |
| | `normalize-space : STR -> STR, STR[] -> STR[]` | Collapses whitespace runs to single space and trims |
| | `fmt "<template>" : STR -> STR, STR[] -> STR[]` | Replaces `{{}}` placeholder with current string (or `{{DEFINE_NAME}}`) |
| | `repl "<old>" "<new>" \| repl { "<k1>" "<v1>"; ... } : STR -> STR, STR[] -> STR[]` | Single replacement or ordered multi-pair replacement block |
| | `lower \| upper \| unescape : STR -> STR, STR[] -> STR[]` | ASCII case conversion / HTML entity decoding |
| | `rm-prefix "<s>" \| rm-suffix "<s>" \| rm-prefix-suffix "<s>" : STR -> STR, STR[] -> STR[]` | Strips literal prefix and/or suffix |
| | `split "<sep>" : STR -> STR[]` | Scalar `STR` input only |
| | `join "<sep>" : STR[] -> STR` | Array `STR[]` input only |
| **Regex** | `re "<pattern>" : STR -> STR, STR[] -> STR[]` | Requires **exactly 1** capture group (`E002`). Raises `SscRegexError` on no-match (caught by `fallback`). Portable flags: `(?i)`, `(?m)`, `(?s)`, `(?x)`, `(?xs)` |
| | `re-all "<pattern>" : STR -> STR[]` | Scalar `STR` only; requires **exactly 1** capture group (`E002`) |
| | `re-sub "<pattern>" "<repl>" : STR -> STR, STR[] -> STR[]` | Regex substitution (0+ capture groups) |
| **Array** | `index <i:int> \| first \| last : T[] -> T` | Supports negative indices (`first` = `0`, `last` = `-1`) |
| | `slice <start:int> <end:int> : T[] -> T[]` | Sub-list slice; supports negative bounds |
| | `len : T[] \| STR -> INT` | Array or string length |
| | `unique [keep-order=#true] : STR[] -> STR[]` | Deduplicates string list |
| **Conversions** | `to-int : STR -> INT, STR[] -> INT[]` | 64-bit integer |
| | `to-float : STR -> FLOAT, STR[] -> FLOAT[]` | 64-bit float |
| | `to-bool : Any -> BOOL` | Scalar truthiness (mandatory in `@check`) |
| **Structured** | `nested <StructName> : DOC -> NESTED, DOC[] -> NESTED[], STR -> NESTED` | Terminal op. Target must be declared above caller (`E302`). `STR` input valid only when target is `(raw)struct` |
| | `jsonify <SchemaName> [path="<gjson>"] : STR -> JSON, STR[] -> JSON[]` | Terminal op. Projects JSON via `<SchemaName>` (declared above caller, `E302`) |
| **Control** | `filter { <predicates> } : T[] -> T[]` | Retains elements matching all predicates (implicit `AND`) |
| | `assert ["<msg>"] { <predicates> } : T -> T` | Raises `SscAssertionError` on failure (survives `python -O`; caught by `fallback`) |
| | `match { <predicates> } : DOC -> STR` | **Must be first op** in `(table)struct` fields (`E203`) |
| | `fallback <literal \| #null \| {}> : T -> T \| T?` | **Must be last op**. `#null` marks scalar `STR`/`INT`/`FLOAT` optional (`T?`); `{}` requires `T[]` |
| | `@<name> : -> TypeOf(name)` | **Must be first op**; reads cached `@init` field (`E301` if undeclared) |
| | `!<Namespace>.<op> : sig In -> Out` | Invokes typed user extension (`E300` if unknown, `E100` on type mismatch) |

---

## 3. Predicates & Dual-Purpose Keywords (`match {}` vs `filter {}` vs `assert {}`)

Top-level children of `filter`, `assert`, `match`, `and`, and `not` combine via implicit `AND`; children of `or` combine via `OR`. Multi-value args (`eq "a" "b"`) match if **any** value matches.

| Category | Predicate Signatures | `match {}` | `filter {}` | `assert {}` | Input Type |
|---|---|:---:|:---:|:---:|---|
| **String** | `eq <v...>`, `ne <v...>`, `starts <v...>`, `ends <v...>`, `contains <v...>`, `in <v...>`, `re "<pat>"` (0 groups required) | ✓ | ✓ | ✓ | `STR` (`eq`/`ne` also `INT`/`FLOAT`) |
| **Attribute** | `has-attr <a...>`, `attr-eq <a> <v...>`, `attr-ne <a> <v...>`, `attr-starts <a> <v...>`, `attr-ends <a> <v...>`, `attr-contains <a> <v...>`, `attr-re <a> "<pat>"` | ✗ | ✓ | ✓ | `DOC` / `DOC[]` |
| **Text / DOM** | `text-starts <v...>`, `text-ends <v...>`, `text-contains <v...>`, `text-re "<pat>"`, `css "<sel>"`, `xpath "<sel>"` | ✗ | ✓ | ✓ | `DOC` / `DOC[]` |
| **Length** | `len-eq <n...>`, `len-ne <n...>`, `len-gt <n>`, `len-lt <n>`, `len-ge <n>`, `len-le <n>`, `len-range <min> <max>` | ✗ | ✗ | ✓ (`E203` elsewhere) | `STR` or `T[]` |
| **Numeric** | `gt <n>`, `lt <n>`, `ge <n>`, `le <n>` | ✗ | ✗ | ✓ (`E203` elsewhere) | `INT`, `FLOAT`, `STR`, or `T[]` |
| **List Regex** | `re-any "<pat>"` (at least one item matches), `re-all "<pat>"` (every item matches) | ✗ | ✗ | ✓ (`E203` elsewhere) | `STR[]` |

---

## 4. `ssc-gen scout` Workflow & Structural Recipes (`(list)struct`, `(table)struct`, `(dict)struct`, `struct type=item`, `jsonify`, `(raw)struct`)

### 4.1 Mapping `ssc-gen scout` Output to KDL Constructs

Run `ssc-gen scout -i page.html` (or `-f json`; add `--full` to disable default truncation limits; `--discover` is a deprecated no-op alias). To probe specific text or attributes, pass `--text`, `--attr`, `--css`, or `--tag` (with `-I` / `-F`): `scout` enters **Zoom-in Mode**, matches the deepest minimal DOM node (including text split across inline tags), auto-expands the enclosing container, and marks matched fields with `<-- MATCH` (`"matched": true` in JSON). Never pass removed legacy flags (`--up`, `--down`, `--next`, `--prev`, `--fields`).

All `samples` in `scout` output are whitespace-normalized (`sample_normalized: true`); never write regexes expecting raw newlines or multi-space runs from a sample.

| `scout` Section (`json` key / `text` header) | Target KDL Construct | How to Map Verified Selectors & Signals |
|---|---|---|
| `repeating_lists` (`=== REPEATING LISTS & DOM SKELETON ===`) | `(list)struct Name` | Copy `selector` into `@split-doc { css-all "<selector>" }`. For each entry in `fields`: use `css` as the relative selector (`kind="scalar"` or `kind="positional"` with `:nth-of-type(k)`), or `css-all "<css>"` when `kind="array"` (`[array min..max items]`). When `optional: true` (`[k/N, optional]`), append `fallback #null`. Ignore `outliers` (inline ad banners) and `navigation_lists`. |
| `kv_blocks` (`=== KEY-VALUE & TABLES ===`) with `kind` in `kv_table \| dl \| kv_rows` (fixed keys) | `(table)struct Name` | Populate `@table { css "<container_selector>" }`, `@rows { css-all "<rows_selector>" }`, `@match { css "<key_selector>"; text; trim; lower }`, `@value { css "<value_selector>"; text; trim }`, and map `entries[].key` to fields starting with `match { eq "<key>" }` (or `starts`/`contains`). |
| `kv_blocks` (`=== KEY-VALUE & TABLES ===`) with dynamic/open-ended keys | `(dict)struct Name` | Populate `@split-doc { css-all "<container_selector> <rows_selector>" }`, `@key { css "<key_selector>"; text; trim }`, `@value { css "<value_selector>"; text; trim }` (no regular fields). |
| `kv_blocks` with `kind == "table_list"` (horizontal `<th>` headers) | `(list)struct Name` | Populate `@split-doc { css-all "<container_selector> <rows_selector>" }` and extract each column via `columns[i].css` (`css "td:nth-of-type(k)"; text; trim`). |
| `zoom_matches` (`=== ZOOM MATCHES ===`) | `struct Name` (`(item)struct` / `struct Name type=item`) | Single-item detail block expanded around `<-- MATCH` (`"matched": true`). Use `match_selector` directly from document root, or scope via `@init` to `container_selector` and use relative `fields[].css` paths. |
| `embedded_json` (`=== EMBEDDED JSON ===`) | `struct Name` + `json Schema` (`jsonify`) | Copy `kdl_hint` into the field pipeline and pass `collections[i].path` as `jsonify Schema path="<path>"` (omit `path=` when `path == ""`). Define `json Schema` above the struct using `collections[i].fields` (`name`, inferred `type`, and `samples`). |

### 4.2 `(raw)struct` — Plain-Text Parsing (JS, URLs, m3u8, CSV)
Starts with `STR` (HTML ops forbidden, `E203`). Auto-selects `LIST` when `@split-doc` is present, else `ITEM`.

```kdl
(raw)struct PlayerScript {
    @request "curl '{{script_url}}'"
    stream_url { re #"file:\s*[\"']([^\"']+)[\"']"# }
}

(raw)struct CsvRows {
    @split-doc { split "\n" }
    @init { cols { split "," } }
    col_0 { @cols; index 0 }
    col_1 { @cols; index 1 }
}
```

### 4.3 `(table)struct` on Non-Table Label+Value Containers (`kv_rows` / `dl`)
For `kv_blocks` (`kv_table`, `dl`, `kv_rows`), use the reported `container_selector`, `rows_selector`, `key_selector`, and `value_selector` (or strip inline label prefixes when key and value share a container):

```kdl
(table)struct ProfileInfo {
    @table { css ".profile-data" }
    @rows  { css-all ".info-row" }
    @match { css "strong"; text; trim; lower }
    @value { text; re-sub #"^[^:]+:\s*"# ""; trim }

    registered   { match { starts "registered" } }
    publications { match { starts "publications" }; re #"(\d+)"#; to-int; fallback 0 }
}
```

### 4.4 Extracting `embedded_json` from `ssc-gen scout`

Each entry in `embedded_json` (`=== EMBEDDED JSON ===`) provides a verified `selector`, `kdl_hint`, and `collections` (with GJSON `path`, `kind`, `count`, and typed `fields`):

| `subtype` | Source Pattern | Extraction Pipeline (`kdl_hint` + `collections[].path`) |
|---|---|---|
| `json-ld` | `<script type="application/ld+json">` | `css "script[type='application/ld+json']"; raw inner; jsonify SchemaName` |
| `json-mime` | `<script id="__NEXT_DATA__" type="application/json">` | `css "script#__NEXT_DATA__"; raw inner; jsonify SchemaName path="props.pageProps.items"` |
| `js-var` / `js-push` / `json-parse` | `var data = {...};` / `.push({...})` / `JSON.parse("...")` in `<script>` | `css "script..."; raw inner; re #"(?s)..."#; [unescape;] jsonify SchemaName [path="..."]` |
| `attr-json` | `<div id="app" data-state="{...}">` | `css "#app"; attr "data-state"; unescape; jsonify SchemaName [path="..."]` |

---

## 5. Module Declarations (`import`, `define`, `extension`) & CSS Selectors

```kdl
import "./shared.kdl" { (extension)Utils; (struct)BookCard; (json)OfferPayload; (define)BASE-URL; (fn)clean-title }
define BASE-URL="https://example.com"
define EXTRACT-HREF { css "a"; attr "href"; trim }

extension Utils {
    slugify {
        sig str str
        py { emit #"{{out}} = {{in}}.lower().replace(' ', '-')"# }
        js { emit #"const {{out}} = {{in}}.toLowerCase().replace(/ /g, '-');"# }
        go { import "strings"; emit #"{{out}} := strings.ToLower({{in}})"# }
        rust { emit #"let {{out}}: String = {{in}}.to_lowercase();"# }
    }
}
```

- **CSS3 (default)**: `[attr]`, `[attr=val]`, `[attr^=val]`, `[attr$=val]`, `[attr*=val]`, `[attr~=word]`, `A > B`, `A + B`, `A ~ B`, `:first-child`, `:last-child`, `:nth-child(n)`, `:nth-of-type(n)`, `:empty`.
- **CSS4 (opt-in only)**: `:not(...)`, `:is(...)`, `:where(...)`, `:has(...)` (prefer CSS3 `[attr^=...]` or pipeline `filter {}` when portable across `slax` / JS DOM).
