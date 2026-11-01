---
name: sscgen-dsl
version: "2.7"
dsl_version: "2.1"
description: >
  Generate KDL Schema DSL (v2.1) configs for HTML scraping and plain-text parsing (`(item|list|table|dict|flat|raw)struct`, `fn`, `(raw)fn`, `css`/`xpath` pipelines, `re`, `jsonify`, `ssc-gen scout`).
  Use when extracting data from HTML pages, embedded `<script>` JSON, JS files, URLs, or playlists, or fixing linter errors in scraping `.kdl` files.
  For REST/JSON HTTP API clients (`(rest)struct`, `@error[:<suffix>]`), use `sscgen-rest`.
---

# sscgen-dsl — HTML Scraping & Plain-Text Parsing (DSL v2.1)

Generate valid KDL Schema DSL v2.1 parsers for HTML pages (`struct`, `(list|table|dict|flat)struct`, `fn`), plain-text inputs (`(raw)struct`, `(raw)fn`), and HTML-embedded JSON (`jsonify`).

> **HTML Inspection Contract:** Never use `Read` on raw `.html` files. When an HTML file or URL is available, your **first** step must be `ssc-gen scout -i <page.html> --discover -f json` (after `curl -sL <URL> -o <page.html>` if given a URL).

---

## Hard Rules

1. **CLI version check**: run `ssc-gen version` (subcommand). Never run `ssc-gen --version` (flag does not exist and errors out).
2. **`ssc-gen scout` for HTML recon**: never read raw `.html` into context; use `ssc-gen scout --discover -f json` and targeted probes.
3. **Scope boundary**: use `sscgen-dsl` for HTML DOM, embedded `<script>` / attribute JSON (`jsonify`), and plain text (`(raw)struct`). If the endpoint itself returns `application/json` (`{` or `[` at root), switch to `sscgen-rest`. (If a site exposes both HTML and JSON API, ask the user which to target.)
4. **Top-down declaration order (`E302`)**: declare helper `struct` and `json` schemas **above** the structs/fields that reference them via `nested` or `jsonify`.
5. **Selectors & indexing**: default to **CSS3** (`[attr^=val]`, `:nth-of-type(N)`, `:first-child`, combinators). Prefer `css "sel:nth-of-type(N)"` over `css-all "sel"; index N` for DOM element selection (`index` is best used after `split` or `re-all`). Use CSS4 (`:not()`, `:is()`, `:where()`, `:has()`) or `xpath` only when explicitly requested.
6. **Regex capture groups (`E002`)**: `re #"..."#` and `re-all #"..."#` as pipeline ops require **exactly 1** capturing group `(...)` (use `(?:...)` for non-capturing groups). `re` raises `SscRegexError` on no-match — add `fallback` when optional. Inside `assert {}` / `filter {}` / `match {}`, `re` is a boolean predicate and requires 0 capture groups.
7. **Struct invariants (`E203`, `E401`)**:
   - `(raw)struct` / `(raw)fn` start with `STR` and **forbid** all HTML ops (`css*`, `xpath*`, `text`, `attr`, `raw`).
   - `(table)struct` requires `@table`, `@rows`, `@match`, `@value`, and every regular field **must** begin with `match { <string-predicates> }`.
   - `(dict)struct` requires `@split-doc`, `@key`, `@value` and forbids regular fields.
   - `@check <name>` pipeline must return `BOOL` (end with `to-bool`, optionally followed by `fallback #false`).
8. **KDL `\` line continuation (`E000`/`E203`)**: never place a `//` single-line comment immediately after `\`.

---

## Workflow

### Step 1 — Recon with `ssc-gen scout` (HTML sources)

```bash
# 1a. Full structural overview (ALWAYS first call on HTML)
ssc-gen scout -i page.html --discover -f json

# 1b. Targeted probes (only when --discover is not enough)
ssc-gen scout -i page.html --text '\$\d+\.\d{2}' --fields path -f json
ssc-gen scout -i page.html --attr 'href=~^/product/\d+' --fields path -f json
ssc-gen scout -i page.html --css ".price" --up 2 --fields path,text -f json
```

Key `--discover` fields:
- `repeat_containers`: candidate `(list)struct` items (`item_selector` $\to$ `@split-doc { css-all "..." }`; `common_descendants` $\to$ field selectors, `attrs`, `max_per_item`, `sample` / `sample_tail` values; note `sample_normalized: true` collapses whitespace).
- `table_candidates`: `<table>` elements with pre-extracted row keys for `(table)struct`.
- `json_signals`: embedded JSON (`json-ld`, `json-mime`, `js-var`, `bare-json`, `attr-json`) with `selector` and `top_level_keys` $\to$ extract with `raw inner` / `attr` (+ `unescape` if attribute-encoded) + `jsonify <Schema>`.

### Step 2 — Choose Struct / Function Type

| Declaration | Input $\to$ Output | Required Directives (`E401`) | Key Rules |
|---|---|---|---|
| `struct Name` / `(item)struct` | `DOC -> dict` | *(none)* | Default; 1+ regular fields |
| `(list)struct Name` | `DOC -> list[dict]` | `@split-doc` | Splits `DOC` into item nodes; runs fields per item |
| `(table)struct Name` | `DOC -> dict` | `@table`, `@rows`, `@match`, `@value` | Every regular field must start with `match { ... }` (`E203`). Also works on non-`<table>` label+value rows |
| `(dict)struct Name` | `DOC -> dict[str, V]` | `@split-doc`, `@key`, `@value` | Dynamic key-value map; no regular fields (`E203`) |
| `(flat)struct Name` | `DOC -> list[str]` | *(none)* | Optional `keep-order=#true`; fields must return `STR` or `STR[]` |
| `(raw)struct Name` | `STR -> dict \| list[dict]` | *(none)* (`@split-doc` optional) | Plain text (JS, URLs, m3u8, CSV). Auto-selects `LIST` if `@split-doc` present, else `ITEM`. HTML ops forbidden |
| `fn name` / `(raw)fn name` | `DOC\|STR -> Inferred` | *(none)* | Standalone single-value function; only `@doc` + pipeline ops allowed (`E203`) |

**Struct Directives:**
- `@init { <name> { <pipeline> }; ... }`: precomputes & caches values on instance; reference as the **first op** in a field via `@<name>` (`E301` if undeclared; `self <name>` is deprecated).
- `@pre-validate { assert ["msg"] { <predicates> } }`: validates input before `parse()`; raises `SscAssertionError`.
- `@check <name> { <pipeline>; to-bool; [fallback #false] }`: emits boolean method (`is_ok()` / `isOk()` / `IsOk()`).
- `@request [response-path="..."] [response-join="\n"] "<curl_or_http>"`: emits `fetch` / `async_fetch` constructor (requires `--http-client` at `generate`).

### Step 3 — Write Field Pipelines & Predicates

Pipeline flow: `selector / @<init> -> extract -> [string / regex / array ops] -> [cast] -> [assert] -> [fallback]`

- **Selectors**: `css "<sel>"`, `css-all "<sel>"`, pattern-match block `css { "<q1>"; "<q2>" }` ($\ge 2$ queries, first match wins), `css-remove "<sel>"`.
- **Extract**: `text`, `attr "<k>"` (or multi-attr `attr "k1" "k2"` $\to$ `STR[]`), `raw [outer|inner]`.
- **String** *(map over `STR` & `STR[]`)*: `trim ["chars"]`, `ltrim`, `rtrim`, `normalize-space`, `lower`, `upper`, `unescape`, `rm-prefix "s"`, `rm-suffix "s"`, `rm-prefix-suffix "s"`, `fmt "https://site.com{{}}"` (requires `{{}}`), `repl "old" "new"` or `repl { "k" "v"; ... }`, `split "sep"` (`STR -> STR[]`), `join "sep"` (`STR[] -> STR`).
- **Regex**: `re #"(group)"#`, `re-all #"(group)"#`, `re-sub #"pat"# "repl"`. Portable flags: `(?i)`, `(?m)`, `(?s)`, `(?x)`, `(?xs)`.
- **Array & Casts**: `first`, `last`, `index <i:int>`, `slice <start:int> <end:int>`, `len`, `unique [keep-order=#true]`; `to-int`, `to-float`, `to-bool`.
- **Structured (terminal)**: `nested <StructName>`, `jsonify <SchemaName> [path="<gjson>"]`.
- **Fallback (must be last op)**: `fallback #null` (marks `STR`/`INT`/`FLOAT` optional `T?`), `fallback ""`, `fallback 0`, `fallback 0.0`, `fallback #false`, `fallback {}` (empty list for `T[]`).

#### Predicate Context Matrix (implicit `AND`; combine with `and {}`, `or {}`, `not {}`)

| Predicate Category | Signatures | `match {}` | `filter {}` | `assert {}` |
|---|---|:---:|:---:|:---:|
| **String** | `eq`, `ne`, `starts`, `ends`, `contains`, `in`, `re #"pat"#` | ✓ | ✓ | ✓ |
| **Attribute** | `has-attr`, `attr-eq`, `attr-ne`, `attr-starts`, `attr-ends`, `attr-contains`, `attr-re` | ✗ | ✓ | ✓ |
| **Text / DOM** | `text-starts`, `text-ends`, `text-contains`, `text-re`, `css`, `xpath` | ✗ | ✓ | ✓ |
| **Length / Numeric / List Regex** | `len-eq`, `len-ne`, `len-gt`, `len-lt`, `len-ge`, `len-le`, `len-range`, `gt`, `lt`, `ge`, `le`, `re-any`, `re-all` | ✗ | ✗ | ✓ (`E203` elsewhere) |

#### Canonical Example

```kdl
@doc "https://example.com/catalog"

define BASE-URL="https://example.com"

json OfferData {
    sku str
    tags (array)str from="meta.tags.#.name"
}

(table)struct SpecsTable {
    @table { css "table.specs" }
    @rows  { css-all "tr" }
    @match { css "th"; text; trim; lower }
    @value { css "td"; text; trim }

    weight { match { eq "weight" }; fallback #null }
}

(list)struct CatalogCards {
    @split-doc { css-all ".product-card" }

    title { css "h3.card-title"; text; normalize-space }
    url   { css "a.card-link"; attr "href"; fmt "{{BASE-URL}}{{}}" }
    price { css ".price"; text; re #"(\d+(?:\.\d+)?)"#; to-float; fallback #null }
}

struct ProductPage {
    @init { raw_offer { css "script#offer-json"; raw inner } }
    @check has-specs { css "table.specs"; to-bool; fallback #false }

    specs   { nested SpecsTable }
    related { nested CatalogCards }
    offer   { @raw_offer; jsonify OfferData path="data.offer" }
}
```

### Step 4 — Iterative Lint & Runtime Verification

```bash
# 1. Lint until exit 0 (mandatory before presenting .kdl to user; cap 5 retries per line)
ssc-gen check schema.kdl -f json

# 2. Test extraction & selector health against sample HTML (when HTML file is available)
ssc-gen run schema.kdl:ProductPage -L bs4 -i page.html
ssc-gen health schema.kdl:ProductPage -i page.html -f json
```

---

## Reference Pointers (Load on Demand)

- **Full op signatures, CSS3/CSS4 tables, `(raw)struct` / non-table `(table)struct` / `json_signals` recipes, `import`/`define`/`extension`, and `ssc-gen generate` CLI** → read `references/ops-quick-ref.md`
- **Disambiguating `re`, `re-all`, `css`, `xpath` between pipeline ops and predicates** → read `references/predicate-vs-op.md`
- **Linter `ErrorCode` (`E000`–`E403`, `W011`–`W041`) fix table** → read `references/linter-errors.md`
- **Safe incremental syntax & repair loop** → read `references/model-friendly.md`
- **Complete `.kdl` examples** → read `references/examples/` (`booksToScrape.kdl`, `hackernews.kdl`, `imdbcom.kdl`, `quotesToScrape.kdl`, `rawParser.kdl`, `regexFallback.kdl`)
