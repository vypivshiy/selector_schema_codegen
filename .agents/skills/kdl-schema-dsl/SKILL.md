---
name: kdl-schema-dsl
description: >
  Generate KDL Schema DSL (v2.1) scraper configs from HTML pages and skill instructions.
  Use this skill whenever the user wants to: generate a .kdl schema file for HTML scraping,
  write KDL DSL for data extraction, work with KDL struct/field/pipeline syntax,
  fix linter errors in a .kdl file, or iterate on a KDL schema based on linter feedback.
  Trigger on any mention of "kdl", "KDL schema", "scraper schema", "DSL для скрапинга",
  or when the user provides an HTML page + extraction task.
---

# KDL Schema DSL — Skill

Generate valid **KDL Schema DSL v2.1** configs for HTML scraping from:
- A **skill instruction** (what to extract and how)
- An **HTML page** (structure to inspect)
- Optionally: **linter output** (text or JSON) to fix errors

## Constraints (always apply)

- **CSS selectors only** — never use `xpath`, `xpath-all`, `xpath-remove`
- **No removal operations** — never use `css-remove`, `xpath-remove`
- **No advanced operations** — never use `transform`, `dsl`, `json`/`jsonify`, `re-all` unless the user explicitly requests them
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

### Step 1 — Analyse the HTML

Before writing any KDL:
1. Identify the **page type**: single item, list of items, table, or mixed
2. Find **repeating patterns** (cards, rows, list items) -> these become `type=list` structs
3. Find **key-value tables** -> `type=table` structs
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
5. **Fallback** (last): `fallback #null`, `fallback 0`, `fallback ""`

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

### `type=item` (default) — single object
```kdl
struct Page {
    @doc "..."
    title { css "h1"; text }
    url   { css "link[canonical]"; attr "href" }
}
```

### `type=list` — list of objects
```kdl
struct Product type=list {
    @split-doc { css-all ".product-card" }

    name  { css ".title"; text }
    price { css ".price"; text; re #"(\d+\.?\d*)"#; to-float }
    url   { css "a[href]"; attr "href"; fallback #null }
}
```

### `type=flat` — list of scalar values
```kdl
struct Tags type=flat {
    @split-doc { css-all ".tag" }
    value { text }
}
```

### `type=table` — key-value HTML table
```kdl
struct Info type=table {
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

### `type=dict` — dynamic key-value map
```kdl
struct MetaTags type=dict {
    @split-doc {
        css-all "meta[property]"
        match { has-attr "property" "content" }
    }
    @key   { attr "property" }
    @value { attr "content" }
}
```

---

## Key Operations (CSS-only subset)

### Selectors
| Operation | Type | Notes |
|-----------|------|-------|
| `css "sel"` | DOC->DOC | First match |
| `css-all "sel"` | DOC->LIST_DOC | All matches |

### Extract
| Operation | Type | Notes |
|-----------|------|-------|
| `text` | DOC->STR / LIST_DOC->LIST_STR | Inner text |
| `attr "name"` | DOC->STR / LIST_DOC->LIST_STR | Attribute value |
| `raw` | DOC->STR | Raw HTML string |

### String ops
`trim` . `ltrim` . `rtrim` . `normalize-space` . `lower` . `upper`
`rm-prefix "x"` . `rm-suffix "x"` . `rm-prefix-suffix "x"`
`fmt DEFINE-NAME` . `re-sub #"pat"# "repl"` . `repl "from" "to"` . `split "delim"` . `join "delim"` . `unescape`

### Regex
`re #"(group)"#` -> STR->STR (first capture group)
`re-all #"pat"#` -> STR->LIST_STR
`re-sub #"pat"# "repl"` -> STR->STR

### Type conversions
`to-int` . `to-float` . `to-bool`

### Array ops
`first` . `last` . `index N` . `slice N M` . `len` . `unique`

### Control
`fallback <val>` — `#null` / `#true` / `#false` / `0` / `"str"` / `{}` (empty list)
`filter { <predicate> }` — filter LIST in place
`assert { <predicate> }` — raise if false
`nested StructName` — call another struct

---

## Defines

Use `define` for reusable constants and block operations:

### Scalar defines
```kdl
define BASE-URL="https://example.com"
define FMT-URL="https://example.com/{{}}"      // {{}} = placeholder
define RE-PRICE=#"(\d+(?:\.\d+)?)"#            // inline regex
```

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
# test schema against HTML file
ssc-gen run schema.kdl:StructName -t py-bs4 -i page.html

# test from stdin (pipe HTML)
curl https://example.com | ssc-gen run schema.kdl:StructName -t py-bs4

# health check — verify selectors match elements
ssc-gen health schema.kdl:StructName -i page.html

# health check from stdin
curl https://example.com | ssc-gen health schema.kdl:StructName
```

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
6. Run: ssc-gen run schema.kdl:StructName -t py-bs4 -i page.html
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

---

### Common linter errors and fixes

| Error message | Cause | Fix |
|---------------|-------|-----|
| `type mismatch: expected STRING, got LIST_STRING` | `css-all` feeds into op that needs single value | Add `first` / `last` / `index N` after selector, or switch to `css` |
| `type mismatch: expected DOCUMENT, got STRING` | Selector used after `text`/`attr` | Reorder — selector must come before extract ops |
| `type mismatch: expected STRING, got INT` | e.g. `re` after `to-int` | Apply `re` before `to-int` |
| `unknown operation '...'` | Unknown op name or typo | Check spelling against operations list |
| `missing @split-doc` | `type=list` or `type=flat` struct without split | Add `@split-doc { css-all "..." }` |
| `missing match{}` | `type=table` field has no predicate | Add `match { eq "key" }` as first statement in field |
| `fallback value type mismatch` | `to-int` then `fallback "x"` | Use typed fallback: INT->`0`, FLOAT->`0.0`, BOOL->`#false`, any->`#null` |
| `define not found: NAME` | Typo or define declared after use | Check spelling; move define above the struct |
| `filter requires list type` | `filter` used on scalar | Use `assert` instead, or ensure pipeline produces LIST_* |
| `match must be first operation` | `match {}` not at start of table field | Move `match { ... }` to first position |
| `'re' must have exactly 1 capture group` | Regex has 0 or 2+ groups | Ensure pattern has exactly one `(...)` group |
| `'fmt' template missing '{{}}' placeholder` | fmt value lacks `{{}}` | Add `{{}}` where the value should be inserted |

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

## Reference Files

For detailed operation signatures and type compatibility tables:
-> See `references/ops-quick-ref.md`

For full KDL examples (HackerNews, Books, Quotes, IMDB):
-> See `references/examples/`
