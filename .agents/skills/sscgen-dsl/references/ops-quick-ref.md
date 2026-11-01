# KDL Operations, Patterns & Codegen Reference (DSL v2.1)

## 1. Unified `TypeInfo` Model

- **Scalar Base Types**: `DOC` (`DOCUMENT`), `STR` (`STRING`), `INT` (64-bit), `FLOAT` (64-bit), `BOOL`, `NULL`, `NESTED` (terminal), `JSON` (terminal).
- **Modifiers**: `T[]` (`is_array=True`), `T?` (`is_optional=True`, produced by `fallback #null` on `STR`/`INT`/`FLOAT` or `?` in `json`), `dict[K, V]` (in `json`).
- **Pipeline Start Type**: `DOC` in HTML structs/`fn`; `STR` in `(raw)struct`/`(raw)fn`; or `TypeOf(name)` when starting with `@<name>`.

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
| **Regex** | `re "<pattern>" : STR -> STR, STR[] -> STR[]` | Requires **exactly 1** capture group (`E002`). Raises `SscRegexError` on no-match (caught by `fallback`) |
| | `re-all "<pattern>" : STR -> STR[]` | Scalar `STR` only; requires **exactly 1** capture group (`E002`) |
| | `re-sub "<pattern>" "<repl>" : STR -> STR, STR[] -> STR[]` | Regex substitution (no capture group requirement) |
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

## 3. Structural Recipes (`(raw)struct`, Non-Table `(table)struct`, `json_signals`)

### 3.1 `(raw)struct` — Plain-Text Parsing (JS, URLs, m3u8, CSV)
Starts with `STR` (HTML ops forbidden, `E203`). Auto-selects `LIST` when `@split-doc` is present, else `ITEM`.

```kdl
// Extract stream URL from inline/remote JS script
(raw)struct PlayerScript {
    @request "curl '{{script_url}}'"
    stream_url { re #"file:\s*[\"']([^\"']+)[\"']"# }
}

// Parse URL query parameter
(raw)struct QueryParams {
    dubbing_code {
        split "?"; index 1; split "&"
        filter { starts "dubbing_code=" }
        first; rm-prefix "dubbing_code="
    }
}

// Split text into lines + cache row columns via @init (auto-LIST)
(raw)struct CsvRows {
    @split-doc { split "\n" }
    @init { cols { split "," } }
    col_0 { @cols; index 0 }
    col_1 { @cols; index 1 }
}
```

### 3.2 `(table)struct` on Non-Table Label+Value Containers
For repeated `<div><strong>Label:</strong> Value</div>` rows, extract the label in `@match` and strip the prefix in `@value`:

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

### 3.3 Extracting `json_signals` from `scout --discover`

| `subtype` | Source Pattern | Extraction Pipeline |
|---|---|---|
| `json-ld` | `<script type="application/ld+json">` | `css "script[type='application/ld+json']"; raw inner; jsonify SchemaName` |
| `json-mime` | `<script id="__NEXT_DATA__" type="application/json">` | `css "script#__NEXT_DATA__"; raw inner; jsonify SchemaName path="props.pageProps"` |
| `js-var` | `var data = [...];` inside `<script>` | `raw; re #"(?xs)var\s+data\s*=\s*(\[.*?\]);"#; jsonify SchemaName` |
| `attr-json` | `<div id="app" data-state="{...}">` | `css "#app"; attr "data-state"; unescape; jsonify SchemaName` |

> Bootstrap complex embedded JSON payloads via `ssc-gen json-to-kdl sample.json -o schema.kdl --name SchemaName --force`. Prefer inline `json` blocks (`field { ... }`, `field (array)ItemModel { ... }`, `field (dict) { @key str; @value ... }`) and GJSON `from="..."` paths (`a.b.0`, `#"a\.b"#`, `items.#`, `tags.#.name`).

---

## 4. Module Declarations (`import`, `define`, `extension`)

```kdl
import "./shared.kdl" {
    (extension)Utils
    (struct)BookCard
    (json)OfferPayload
    (define)BASE-URL
    (fn)clean-title
}

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

---

## 5. CSS3 & CSS4 Selector Reference

- **Attribute**: `[attr]`, `[attr=val]`, `[attr^=val]` (starts), `[attr$=val]` (ends), `[attr*=val]` (contains), `[attr~=word]`, `[attr|=prefix]`.
- **Combinators**: `A B` (descendant), `A > B` (direct child), `A + B` (adjacent sibling), `A ~ B` (following sibling), `A, B` (union).
- **CSS3 Structural**: `:first-child`, `:last-child`, `:only-child`, `:nth-child(n)`, `:nth-last-child(n)`, `:first-of-type`, `:last-of-type`, `:nth-of-type(n)`, `:empty`.
- **CSS4 (opt-in only)**: `:not(...)`, `:is(...)`, `:where(...)`, `:has(...)` (supported in `bs4`/`lxml`/`parsel`; partial in JS DOM / `slax` — prefer CSS3 `[attr^=...]` or pipeline `filter {}` when portable).

---

## 6. CLI & Codegen Targets

```bash
# Check CLI version (subcommand `version`, NEVER `--version`)
ssc-gen version

# Lint, run, and check selector health
ssc-gen check schema.kdl -f json
ssc-gen run schema.kdl:StructName -L bs4 -i page.html
ssc-gen health schema.kdl:StructName -i page.html -f json

# Generate standalone parser code
ssc-gen generate python schema.kdl -L bs4 -o out/   # -L bs4|lxml|parsel|slax [--bs4-parser lxml|html.parser|html5lib] [-R] [--http-client httpx|httpx2|requests|aiohttp]
ssc-gen generate js     schema.kdl -o out/          # [--http-client fetch|axios]
ssc-gen generate go     schema.kdl -o out/          # emits schema.go + sscgen_runtime.go
ssc-gen generate rust   schema.kdl -o out/          # emits schema.rs + sscgen_runtime.rs [--http-client reqwest]
```
