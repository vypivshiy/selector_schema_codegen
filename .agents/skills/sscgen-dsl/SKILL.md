---
name: sscgen-dsl
version: "2.1"
description: >
  Generate KDL Schema DSL (v2.1) scraper configs for **HTML scraping** from HTML
  pages and skill instructions. Covers struct types (item) / (list) / (flat) / (table) /
  (dict), css selectors, extract / string / regex / array / cast pipelines,
  defines, transforms, jsonify, and the iterative linter loop.
  Use this skill whenever the user wants to: generate a .kdl schema file for HTML
  scraping, write KDL DSL for data extraction from HTML, work with css/css-all/
  text/attr/raw pipelines, fix linter errors in an HTML-scraping .kdl, or iterate
  on a KDL schema based on linter feedback.
  Trigger on mentions of "kdl", "KDL schema", "scraper schema", "DSL для скрапинга",
  "распарсить страницу", "вытащить из HTML", or whenever the user provides an HTML
  page + extraction task.
  **Do NOT use this skill for REST/JSON HTTP API clients (`(rest)struct`,
  `@request`, `@error`, typed placeholders for HTTP) — use the sibling skill
  `sscgen-rest` instead.** The two skills share the same DSL surface but solve
  different problems and should not be mixed.
---

# sscgen-dsl — Skill (HTML scraping)

Generate valid **KDL Schema DSL v2.1** configs for HTML scraping from:
- A **skill instruction** (what to extract and how)
- An **HTML page** (structure to inspect)
- Optionally: **linter output** (text or JSON) to fix errors

> **Scope: HTML only.** This skill covers `(item)struct / (list)struct / (flat)struct / (table)struct / (dict)struct`
> with CSS-selector pipelines. For REST/JSON HTTP APIs (`(rest)struct`,
> `@request`/`@error`, typed `{{id:int}}` placeholders) → use the **`sscgen-rest`**
> skill, not this one. Don't mix REST endpoints into HTML schemas.

## Constraints (always apply)

- **CSS selectors only** — never use `xpath`, `xpath-all`, `xpath-remove`
- **No removal operations** — never use `css-remove`, `xpath-remove`. Also `css-remove`/`xpath-remove` do not support the block pattern-match form
- **No advanced operations** — never use `transform`, `dsl`, `json`/`jsonify` unless the user explicitly requests them
- **No `(rest)struct`** — that's `sscgen-rest` territory. If the user describes an HTTP/JSON API (endpoints, response schemas, error codes), switch skills.
- **CSS3+ selectors preferred** — use the full set supported by the parser (see CSS Selector Tips below); prefer attribute selectors, pseudo-classes and combinators over writing extra pipeline logic
- Prefer simple, readable pipelines
- If extraction can be done with a smarter CSS selector, do that instead of adding ops to the pipeline

---

## Input Modes

### Mode 1 — Generate from scratch
Inputs: skill instruction + HTML page
-> Analyse the HTML structure, map fields to CSS selectors, generate `.kdl`

### Mode 2 — Fix linter errors
Inputs: existing `.kdl` + linter output (text or JSON format)
-> Parse errors, locate affected fields, fix each one, re-emit corrected `.kdl`

### Mode 3 — Iterate
Inputs: existing `.kdl` + new requirements or HTML changes
-> Diff the requirements, update affected structs/fields only

---

## Generation Workflow

### Step 0 — Recon & Extract via scout (recommended)

Probe HTML with `ssc-gen scout` before writing KDL. Especially useful when
patterns involve regex (prices, dates, IDs) or when you need to extract
ad-hoc data without committing to a full schema.

**Recon mode — discover selectors:**

```bash
ssc-gen scout -i page.html --text '\$\d+\.\d{2}' --fields path -f json
ssc-gen scout -i page.html --attr 'href=~^/product/\d+' --fields path -f json
ssc-gen scout -i page.html --css ".price" --up 2 --fields path -f json
```

Output JSON gives computed CSS paths — reuse them directly in `.kdl` selectors.

**Extract mode — pull data without writing .kdl:**

```bash
ssc-gen scout -i page.html --css ".product-card" \
    --fields attr.data-id,text -f json
ssc-gen scout -i page.html --css "a[href]" --fields attr.href,text -f json
```

Useful for one-off extraction, content audit, or feeding sample data back
into LLM context for schema design.

**Navigation — find anchor → climb to container:**

```bash
ssc-gen scout -i page.html --css ".price" --up 2 --fields path,attr.data-id -f json
ssc-gen scout -i page.html --css ".thumb" --up 1 --fields attr.href -f json
```

Filters (AND-combine): `--text REGEX`, `--attr NAME[=VAL|=~REGEX]`, `--tag NAME`, `--css SEL`.
Modifiers: `-I` ignore-case, `-F` fixed strings, `-v` invert.
Pagination: `--limit N` (default 50), `--offset N`, `--snippet LEN` (default 200).
Exit codes: 0 on match, 1 on no match, 2 on error.

### Step 1 — Analyse the HTML

Before writing any KDL:
1. Identify the **page type**: single item, list of items, table, or mixed
2. Find **repeating patterns** (cards, rows, list items) -> these become `(list)struct` structs
3. Find **key-value tables** -> `(table)struct` structs
4. Note attribute-rich selectors: use `[attr^=...]`, `[attr$=...]` etc. in CSS for precision
5. Note what data is available: text content, attributes, nested structures

### Step 2 — Plan the struct hierarchy

```
Main struct (type=item or entry point)
|-- @doc with page URL examples
|-- nested ListStruct   (if page has a list)
\-- nested TableStruct  (if page has a table)

ListStruct (type=list)
|-- @split-doc { css-all "<card selector>" }
|-- @pre-validate (optional, for robustness)
\-- fields...

TableStruct (type=table)
|-- @table / @rows / @match / @value
\-- fields with match { ... }
```

### Step 3 — Write fields

For each field, build the pipeline:
```
selector -> extract -> [string ops] -> [regex] -> [type conv] -> [fallback]
```

#### Field pipeline rules
1. **Start with a selector**: `css "..."` or `css-all "..."`
2. **Then extract**: `text`, `attr "name"`, or `raw`
3. **String ops** (optional, in order): `trim`, `lower`, `upper`, `normalize-space`, `rm-prefix`, `rm-suffix`, `rm-prefix-suffix`, `fmt`, `re-sub`, `repl`, `unescape`
4. **Type conversion** (optional): `to-int`, `to-float`, `to-bool`
5. **URL normalization** (if path may be relative): `fmt FMT-NAME` where `define FMT-NAME="https://site.com{{}}"` — always convert relative paths to absolute URLs
6. **Fallback** (last): `fallback #null`, `fallback 0`, `fallback ""`

#### Inline vs block syntax
Both are valid — prefer **inline** for simple 1-3 op fields:
```kdl
// inline (preferred for short pipelines)
title { css "h1"; text }
date { css ".age[title]"; attr "title"; fallback #null }

// block (preferred for 4+ ops or when readability matters)
price {
    css ".price_color"
    text
    re #"(\d+(?:\.\d+)?)"#
    to-float
}
```

---

## Struct Types Reference

### `(item)` (default) — single object
```kdl
struct Page {
    @doc "..."
    title { css "h1"; text }
    url   { css "link[canonical]"; attr "href" }
}
```

### `(list)` — list of objects
```kdl
(list)struct Product {
    @split-doc { css-all ".product-card" }

    name  { css ".title"; text }
    price { css ".price"; text; re #"(\d+\.?\d*)"#; to-float }
    url   { css "a[href]"; attr "href"; fallback #null }
}
```

### `(flat)` — list of scalar values
```kdl
(flat)struct Tags {
    // should be returns STRING or LIST_STRING
    value { text }
}
```

With `keep-order=#true` the struct preserves insertion order (no deduplication sort):
```kdl
(flat)struct OrderedTags keep-order=#true {
    value { text }
}
```

### `(table)` — key-value HTML table
```kdl
(table)struct Info {
    @table { css "table.product-info" }
    @rows  { css-all "tr" }
    @match { css "th"; text; trim; lower }
    @value { css "td"; text }

    upc   { match { eq "upc" } }
    price {
        match { starts "price" }
        re #"(\d+\.\d+)"#
        to-float
    }
    stock {
        match { eq "availability" }
        assert { contains "In stock" }
        to-bool
        fallback #false
    }
}
```

### `(table)` — non-table HTML (label+value in same element)

`(table)` also works for repeated elements where the label and value live inside the same container (e.g. `<div><strong>Label:</strong> value</div>`). Use `@match` to extract the label from a child element and `@value` with `re-sub` to strip the label prefix from the full text.

```kdl
// HTML structure:
// <div class="info-row"><strong>Registered: </strong>7 March 2015</div>
// <div class="info-row"><strong>Gender: </strong>Female</div>
// <div class="info-row"><strong>Publications: </strong>28</div>

(table)struct ProfileInfo {
    @table { css ".profile-data" }
    @rows  { css-all ".info-row" }
    @match { css "strong"; text; trim; lower }
    @value { text; re-sub #"^[^:]+:\s*"# ""; trim }

    registered {
        match { starts "registered" }
    }
    gender {
        match { starts "gender" }
        fallback #null
    }
    publications {
        match { starts "publications" }
        re #"(\d+)"#
        to-int
        fallback 0
    }
}
```

Use `nested` to compose with an `(item)` struct that extracts non-table fields (avatar, title, etc.):

```kdl
struct MainPage {
    display_name { css "h2"; text; trim }
    avatar { css ".avatar img"; attr "src"; fallback #null }
    info { nested ProfileInfo }
}
```

### `(dict)` — dynamic key-value map
```kdl
(dict)struct MetaTags {
    @split-doc {
        css-all "meta[property]"
        match { has-attr "property" "content" }
    }
    @key   { attr "property" }
    @value { attr "content" }
}
```

### `@check` — boolean check method

`@check` creates a public method that returns `bool` to verify the document matches expected structure. Pipeline must contain `to-bool`. Called manually before `parse()`.

```kdl
struct ProductPage {
    @check is-in-stock {
        assert { css ".add-to-cart" }
        to-bool
        fallback #false
    }

    title { css "h1"; text }
    price { css ".price"; text; to-float }
}
```

Generated as: `is_in_stock(self) -> bool` (Python) / `isInStock()` (JS).

---

## Key Operations (CSS-only subset)

### Selectors
| Operation | Type | Notes |
|-----------|------|-------|
| `css "sel"` | DOC->DOC | First match |
| `css-all "sel"` | DOC->LIST_DOC | All matches |
| `css { "q1"; "q2"; ... }` | DOC->DOC | Pattern-match: try selectors in order, use first non-empty result (2+ required) |
| `css-all { "q1"; "q2"; ... }` | DOC->LIST_DOC | Pattern-match: try selectors in order, use first non-empty result (2+ required) |

### Extract
| Operation | Type | Notes |
|-----------|------|-------|
| `text` | DOC->STR / LIST_DOC->LIST_STR | Inner text |
| `attr "name"` | DOC->STR / LIST_DOC->LIST_STR | Single attribute value (error if missing) |
| `attr "n1" "n2" ...` | DOC->LIST_STR | Multiple attributes (missing attrs skipped silently) |
| `raw` | DOC->STR | Raw HTML string |

### String ops
All string ops support **map semantics**: STRING -> STRING and LIST_STRING -> LIST_STRING.

`trim` . `ltrim` . `rtrim` . `normalize-space` . `lower` . `upper`
`rm-prefix "x"` . `rm-suffix "x"` . `rm-prefix-suffix "x"`
`fmt DEFINE-NAME` . `re-sub #"pat"# "repl"` . `repl "from" "to"` . `repl { "from1" "to1"; "from2" "to2" }` . `split "delim"` . `join "delim"` . `unescape`

### Regex

| Op | Signature | Notes |
|----|-----------|-------|
| `re #"(group)"#` | STRING → STRING | First capture group; **requires exactly 1 capturing group** |
| `re #"(group)"#` | LIST_STRING → LIST_STRING | Map semantics — per element |
| `re-all #"(group)"#` | STRING → LIST_STRING | All matches; **requires exactly 1 capturing group** |
| `re-sub #"pat"# "repl"` | STRING → STRING | Replace all matches; no group requirement |
| `re-sub #"pat"# "r"` | LIST_STRING → LIST_STRING | Map semantics |

**Capture group requirement**: `re` and `re-all` require exactly one `(...)` capturing group. Non-capturing `(?:...)` is allowed for grouping. The linter rejects patterns with 0 or 2+ groups.

**No-match behaviour**: `re` raises `SscRegexError` if the pattern doesn't match. The default message is language-agnostic and includes source location for debugging:
```
<file.kdl>:<line>:<col> re-match failed at <Struct>.<field> pattern=<pat>
```

Caught by `fallback` — common pattern for "regex may not match":
```kdl
struct Page type=item {
    year {
        css ".title"
        text
        re #"\((\d{4})\)"#   // extract 4-digit year from "(2024)"
        fallback ""          // SscRegexError suppressed if no year in title
    }
}
```

> **Predicate vs pipeline op**: `re #"pat"#` and `re-all #"pat"#` have dual meaning.
> Inside `assert {}`/`filter {}`/`match {}` they are **predicates** returning `bool`.
> At the top level of a field pipeline they are **ops** transforming values.
> See `references/predicate-vs-op.md` for full disambiguation.

### Type conversions
`to-int` . `to-float` . `to-bool`

### Array ops
`first` . `last` . `index N` . `slice N M` . `len` . `unique`

> **Prefer `:nth-of-type(N)` over `index N`** — when selecting specific elements from a list of siblings, use CSS `:nth-of-type(N)` (1-based) directly in the selector instead of `css-all "..." ; index N`. The `index` operator has a known issue in ssc-gen where values beyond index 0 may silently fall back to the first element's result. Use `css "selector:nth-of-type(N)"` to reliably target the Nth element.

### Control
`fallback <val>` — `#null` / `#true` / `#false` / `0` / `"str"` / `{}` (empty list)
`filter { <predicate> }` — filter LIST in place
`assert { <predicate> }` — validate without changing value; raises `SscAssertionError` on failure (caught by `fallback` if present)
`assert "message" { <predicate> }` — assert with custom error message; default message is `<file.kdl>:<line>:<col> assertion failed at <Struct>.<field>` (or `<Struct>.@pre-validate` inside `@pre-validate`)
`nested StructName` — call another struct (DOCUMENT -> NESTED, terminal)
`jsonify SchemaName [path="dotted.path"]` — deserialize JSON string (STRING -> JSON, terminal)

> **assert implementation**: emitted as `std_assert(cond, msg)` helper in Python, `_stdAssert(cond, msg)` in JS. Raises `SscAssertionError` — **not** the Python `assert` keyword, so it survives `python -O`. Caught by `fallback` when present. Multiple `assert` blocks can appear anywhere in a pipeline.

**Example: assert + fallback for robustness:**
```kdl
struct Product {
    price {
        css ".price"
        text
        assert { contains "$" }       // verify currency symbol present
        re #"(\d+\.\d+)"#
        to-float
        fallback 0.0                  // SscAssertionError or SscRegexError suppressed
    }
}
```

---

## @init — precompute shared values

`@init` caches values once per struct that can be referenced by multiple fields
via `@<name>` (preferred) or `self.<name>` (deprecated). Useful when several
fields need the same expensive selector or raw HTML.

```kdl
struct Page {
    @init {
        // precompute raw HTML of the main content
        content-html { css ".main"; raw }
    }

    // multiple fields reference the same @init value
    word-count {
        @content-html
        re #"<p>(.*?)</p>"#        // first paragraph
    }

    full-text {
        @content-html
        re-sub #"<[^>]+>"# " "     // strip tags
        normalize-space
    }
}
```

`@init` fields are computed once and cached. Each `@<name>` reference reuses
the cached value — no selector re-evaluation.

---

## Defines

Use `define` for reusable constants and block operations:

### Scalar defines
```kdl
define BASE-URL="https://example.com"
define FMT-URL="https://example.com/{{}}"      // {{}} = placeholder
define RE-PRICE=#"(\d+(?:\.\d+)?)"#            // inline regex
```

Scalar defines can reference other defines via `{{NAME}}` (UPPER_CASE) — resolved at parse time:
```kdl
define BASE-URL="https://example.com"
define API-URL="{{BASE-URL}}/api/v1"           // resolves to "https://example.com/api/v1"
```

Lowercase `{{name}}` in define values are left as-is — they become `@request` placeholders at runtime.

### Block defines
```kdl
define REPL-RATING {
    repl { One "1"; Two "2"; Three "3"; Four "4"; Five "5" }
}

define EXTRACT-HREF {
    css "a"
    attr "href"
}
```

Block defines are used as pipeline operations:
```kdl
link { EXTRACT-HREF; trim }
// or explicitly:
link { expr EXTRACT-HREF; trim }
```

Place defines **before structs** that reference them.

### Define as @request argument

A scalar define can be used as the `@request` argument:
```kdl
define HNEWS-REQ="""
GET /?p={{page-num}} HTTP/1.1
Host: news.ycombinator.com
Accept: text/html
"""

struct MainPage {
    @request HNEWS-REQ
    news { css-all ".athing"; text }
}
```

---

## Imports

Split schemas across multiple files:

```kdl
import "./shared_defines.kdl"
import "./shared_struct.kdl"
```

Imports bring in `define`, `struct`, `json`, `transform`, `dsl` definitions from other files. Paths are relative to the current file. Transitive imports are supported.

---

## Advanced: dsl + expr (single-language code)

For simple inline code blocks when `transform` is overkill:

```kdl
dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

struct Main {
    title { css "h1"; text; expr upper-py }
}
```

**Only use when the user explicitly requests custom code operations.**

---

## Iterative Lint Loop

After generating or editing a `.kdl` file, **always run the linter and iterate until clean**.

### Linter CLI

```bash
# text output (human-readable, default)
ssc-gen check schema.kdl

# JSON output (preferred for automated fixing)
ssc-gen check schema.kdl -f json

# multiple files or directory
ssc-gen check -f json schemas/
```

### Validation CLI (test against real HTML)

```bash
# test schema against HTML file (Python targets)
ssc-gen run schema.kdl:StructName -l python -L bs4 -i page.html
ssc-gen run schema.kdl:StructName -l python -L lxml -i page.html

# test from stdin (pipe HTML)
curl https://example.com | ssc-gen run schema.kdl:StructName -l python -L bs4

# health check — verify selectors match elements
ssc-gen health schema.kdl:StructName -i page.html

# health check from stdin
curl https://example.com | ssc-gen health schema.kdl:StructName
```

> Languages: `-l python` (default) | `-l js`
> Python libs (`-L`): `bs4` (default) | `lxml` | `parsel` | `slax`

### Loop algorithm

```
1. Write/update the .kdl file
2. Run: ssc-gen check -f json <file>
3. If output is empty / exit 0 -> DONE
4. If errors present -> fix all errors -> go to step 2
5. Repeat until no errors remain
```

**Never present the .kdl to the user until the linter reports zero errors.**
If after 5 iterations errors persist in the same location, explain the issue to the user and ask for clarification.

### Optional: runtime validation

After linting passes, if an HTML file is available:
```
6. Run: ssc-gen run schema.kdl:StructName -l python -L bs4 -i page.html
7. Inspect output — verify fields are extracted correctly
8. If selectors miss elements: ssc-gen health schema.kdl:StructName -i page.html
```

---

### Parsing linter output

#### Text format
```
Error at line 12: type mismatch: expected STRING, got LIST_STRING
Warning at line 8: unused define 'BASE-URL'
```
-> Map line numbers to the current file, fix errors (warnings are optional).

#### JSON format
```json
[
  { "line": 12, "col": 4, "level": "error", "message": "type mismatch: expected STRING, got LIST_STRING" },
  { "line": 8,  "col": 1, "level": "warning", "message": "unused define 'BASE-URL'" }
]
```
-> Filter `"level": "error"`, sort by line ascending, fix top-to-bottom (avoids line-number drift).

> Full error-to-fix table: see `references/linter-errors.md`.

---

## CSS Selector Tips

Prefer a more precise selector over adding pipeline operations. The parser supports CSS3+ including:

### Attribute selectors
```css
[attr]              /* has attribute */
[attr="val"]        /* exact match */
[attr^="val"]       /* starts with */
[attr$="val"]       /* ends with */
[attr*="val"]       /* contains */
[attr~="val"]       /* word in space-separated list */
[attr|="val"]       /* val or val-* (language codes) */
```

### Combinators
```css
.parent > .child          /* direct child only */
.ancestor .descendant     /* any depth */
.prev + .next             /* immediately adjacent sibling */
.prev ~ .siblings         /* all following siblings */
```

### Pseudo-classes (structural)
```css
:first-child   :last-child   :nth-child(N)   :nth-child(odd/even)
:first-of-type :last-of-type :nth-of-type(N)
:only-child    :only-of-type
:not(.excluded)             /* negation */
```

### Combining for precision (examples)
```css
span.score[id^="score_"]
meta[property^="og:"][content]
a[href^="http"]:not([href*="mysite.com"])
tr:nth-child(n+2)
input:not([type="hidden"])
```

**Rule of thumb:** if you're about to write `re-sub` just to strip a known prefix/suffix from an attribute value, check first if a smarter `[attr^=...]` or `[attr$=...]` selector can filter at the selection stage instead.

---

## Output Format

Always emit a complete, lintable `.kdl` file:
1. `import` statements (if splitting across files)
2. `@doc` module docstring (page URL, usage notes)
3. `define` block (constants, URL formats, regex patterns)
4. Nested/helper structs (referenced by main)
5. Main entrypoint struct last

If fixing linter errors: emit the **full corrected file**, not just changed lines.

---

## See also

- **`sscgen-rest`** — for REST/JSON HTTP API clients (`(rest)struct`, `@request`, `@error`, typed placeholders). Share the same DSL surface but a different problem domain.
- **`sscgen-openapi`** — for converting OpenAPI/Swagger specs to `.kdl` REST clients deterministically.

---

## Reference Files

For detailed operation signatures and type compatibility tables:
-> See `references/ops-quick-ref.md`

For disambiguation between pipeline ops and predicates (`re`, `re-all`, `css`):
-> See `references/predicate-vs-op.md`

For the canonical linter error → fix mapping:
-> See `references/linter-errors.md`

For full KDL examples:
-> See `references/examples/`
- `booksToScrape.kdl` — `(list)struct` with price regex extraction, `fallback`, URL normalization via `fmt`
- `hackernews.kdl` — `(list)struct` with `@doc` HTML signature, multi-struct composition, `fmt` URL building
- `imdbcom.kdl` — search results page, `nested` struct composition, `(flat)struct` for genres
- `quotesToScrape.kdl` — `json` schema + `jsonify`, `@init` precompute, verbose-flag regex define, `path="0"` accessor
- `assertRegexFallback.kdl` — `assert` (basic + custom msg), `re` no-match + `fallback` recovery, `re-all` single-group extraction
